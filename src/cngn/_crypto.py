"""Cryptographic primitives for the cNGN API.

Request bodies are AES-256-CBC encrypted (PKCS7 padding, random IV per
request) with a key derived as ``sha256(encryption_key.encode())``.
Encrypted responses are NaCl Box (X25519-XSalsa20-Poly1305) blobs sealed
to the merchant's Ed25519 key converted to Curve25519.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import struct
from typing import Any

from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519
from nacl.public import Box, PrivateKey, PublicKey
from nacl.signing import SigningKey

from ._exceptions import DecryptionError, EncryptionError

_OPENSSH_MAGIC = b"openssh-key-v1\x00"
_OPENSSH_PEM_HEADER = "-----BEGIN OPENSSH PRIVATE KEY-----"
_OPENSSH_PEM_FOOTER = "-----END OPENSSH PRIVATE KEY-----"
_NONCE_LEN = 24
_EPHEMERAL_PUBKEY_LEN = 32


def derive_aes_key(encryption_key: str) -> bytes:
    """Derive the 32-byte AES key from the dashboard encryption-key string."""
    return hashlib.sha256(encryption_key.encode()).digest()


def aes_encrypt(plaintext: bytes, key: bytes) -> dict[str, str]:
    """AES-256-CBC encrypt ``plaintext`` with PKCS7 padding and a random IV.

    Returns the wire envelope ``{"content": base64, "iv": base64}``.
    """
    import os

    if len(key) != 32:
        raise EncryptionError(f"AES-256 requires a 32-byte key, got {len(key)} bytes")
    iv = os.urandom(16)
    padder = sym_padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return {
        "content": base64.b64encode(ciphertext).decode(),
        "iv": base64.b64encode(iv).decode(),
    }


def aes_decrypt(content: bytes, iv: bytes, key: bytes) -> bytes:
    """Reverse :func:`aes_encrypt`; raises EncryptionError on bad input."""
    if len(key) != 32:
        raise EncryptionError(f"AES-256 requires a 32-byte key, got {len(key)} bytes")
    if len(iv) != 16:
        raise EncryptionError(f"AES-CBC requires a 16-byte IV, got {len(iv)} bytes")
    try:
        decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        padded = decryptor.update(content) + decryptor.finalize()
        unpadder = sym_padding.PKCS7(algorithms.AES.block_size).unpadder()
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as exc:
        raise EncryptionError(f"AES decryption failed: {exc}") from exc


def _read_string(buf: io.BytesIO) -> bytes:
    raw_len = buf.read(4)
    if len(raw_len) != 4:
        raise DecryptionError("Truncated OpenSSH key: expected a length prefix")
    (length,) = struct.unpack(">I", raw_len)
    data = buf.read(length)
    if len(data) != length:
        raise DecryptionError("Truncated OpenSSH key: declared length exceeds key data")
    return data


def _read_uint32(buf: io.BytesIO) -> int:
    raw = buf.read(4)
    if len(raw) != 4:
        raise DecryptionError("Truncated OpenSSH key: expected a uint32")
    (value,) = struct.unpack(">I", raw)
    return value


def parse_openssh_ed25519_private_key(pem: str) -> bytes:
    """Parse an unencrypted ``openssh-key-v1`` Ed25519 PEM and return the 32-byte seed.

    The format is parsed structurally (length-prefixed fields), not by marker
    slicing. Encrypted private keys (``ciphername != "none"``) are rejected
    with a clear error.
    """
    lines = [line.strip() for line in pem.strip().splitlines() if line.strip()]
    if not lines or lines[0] != _OPENSSH_PEM_HEADER or lines[-1] != _OPENSSH_PEM_FOOTER:
        raise DecryptionError(
            "Private key must be an OpenSSH PEM "
            "(-----BEGIN OPENSSH PRIVATE KEY-----); generate one with "
            "'ssh-keygen -t ed25519'"
        )
    b64_body = "".join(lines[1:-1])
    try:
        blob = base64.b64decode(b64_body, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DecryptionError(f"OpenSSH private key is not valid base64: {exc}") from exc
    if not blob.startswith(_OPENSSH_MAGIC):
        raise DecryptionError("Missing 'openssh-key-v1' magic; not an OpenSSH private key")

    buf = io.BytesIO(blob[len(_OPENSSH_MAGIC) :])
    ciphername = _read_string(buf).decode("utf-8", errors="replace")
    if ciphername != "none":
        raise DecryptionError(
            f"Encrypted OpenSSH private keys (cipher '{ciphername}') are not supported; "
            "export an unencrypted key or decrypt it with 'ssh-keygen -p'"
        )
    _read_string(buf)  # kdfname
    _read_string(buf)  # kdfoptions
    nkeys = _read_uint32(buf)
    if nkeys != 1:
        raise DecryptionError(f"Expected exactly 1 key in the OpenSSH blob, found {nkeys}")
    _read_string(buf)  # public key blob (already known to the merchant)

    private_block = io.BytesIO(_read_string(buf))
    checkint_1 = _read_uint32(private_block)
    checkint_2 = _read_uint32(private_block)
    if checkint_1 != checkint_2:
        raise DecryptionError("OpenSSH checkints do not match; the key is corrupt")

    key_type = _read_string(private_block)
    if key_type != b"ssh-ed25519":
        raise DecryptionError(
            f"Expected an 'ssh-ed25519' key, got '{key_type.decode('utf-8', errors='replace')}'"
        )
    _read_string(private_block)  # public key
    private_key = _read_string(private_block)  # public key (32) || seed (32)
    if len(private_key) != 64:
        raise DecryptionError(f"Ed25519 private key must be 64 bytes, found {len(private_key)}")
    _read_string(private_block)  # comment
    padding = private_block.read()
    if any(padding[i] != i + 1 for i in range(len(padding))):
        raise DecryptionError("OpenSSH private block padding is malformed")
    return private_key[32:]


def decrypt_response_data(b64_blob: str, openssh_pem: str) -> Any:
    """Decrypt the base64 ``data`` field of a cNGN success response.

    Blob layout: ``nonce (24) || NaCl Box ciphertext || ephemeral pubkey (32)``.
    Returns the decrypted JSON value — an object for most endpoints, a list
    for collection endpoints such as ``/balance``.
    """
    try:
        blob = base64.b64decode(b64_blob, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DecryptionError(f"Response data is not valid base64: {exc}") from exc
    min_len = _NONCE_LEN + 16 + _EPHEMERAL_PUBKEY_LEN  # ciphertext at least the MAC
    if len(blob) < min_len:
        raise DecryptionError(
            f"Response data blob is too short ({len(blob)} bytes, minimum {min_len})"
        )
    nonce = blob[:_NONCE_LEN]
    ephemeral_pubkey = blob[-_EPHEMERAL_PUBKEY_LEN:]
    ciphertext = blob[_NONCE_LEN:-_EPHEMERAL_PUBKEY_LEN]

    seed = parse_openssh_ed25519_private_key(openssh_pem)
    # libsodium's converter expects the 64-byte secret key (seed || public key).
    public_key = SigningKey(seed).verify_key.encode()
    curve_seed = crypto_sign_ed25519_sk_to_curve25519(seed + public_key)
    box = Box(PrivateKey(curve_seed), PublicKey(ephemeral_pubkey))
    try:
        plaintext = box.decrypt(ciphertext, nonce)
    except Exception as exc:
        raise DecryptionError(
            "Failed to decrypt response data with the configured private key; "
            "verify the key matches the one uploaded to the dashboard"
        ) from exc
    try:
        parsed = json.loads(plaintext)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DecryptionError(f"Decrypted response payload is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict | list):
        raise DecryptionError("Decrypted response payload is not a JSON object or array")
    return parsed
