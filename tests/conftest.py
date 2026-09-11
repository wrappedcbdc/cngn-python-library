"""Shared fixtures: a real openssh-key-v1 Ed25519 keypair, a respx mock
router, and crypto helpers that independently reproduce the wire formats."""

from __future__ import annotations

import base64
import hashlib
import json
import struct
from typing import Any

import pytest
import respx
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from nacl.bindings import crypto_sign_ed25519_pk_to_curve25519
from nacl.public import Box, PrivateKey, PublicKey
from nacl.signing import SigningKey

from cngn._crypto import aes_decrypt

BASE_URL = "https://api.cngn.co/v1/api"
API_KEY = "cngn_test_" + "a" * 32
ENCRYPTION_KEY = "test-encryption-key-0123456789"


def _openssh_string(data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + data


def serialize_openssh_ed25519_private_key(seed: bytes, comment: bytes = b"cngn-test") -> str:
    """Serialize an unencrypted openssh-key-v1 Ed25519 PEM.

    Produces byte-for-byte the same structure as `ssh-keygen -t ed25519`
    with an empty passphrase.
    """
    verify_key = SigningKey(seed).verify_key.encode()
    public_blob = _openssh_string(b"ssh-ed25519") + _openssh_string(verify_key)
    private_key_64 = verify_key + seed  # OpenSSH layout: public key || seed
    checkint = 0x4C4E474E

    block = struct.pack(">I", checkint)
    block += struct.pack(">I", checkint)
    block += _openssh_string(b"ssh-ed25519")
    block += _openssh_string(verify_key)
    block += _openssh_string(private_key_64)
    block += _openssh_string(comment)
    pad_len = 8 - (len(block) % 8)
    block += bytes(range(1, pad_len + 1))

    blob = b"openssh-key-v1\x00"
    blob += _openssh_string(b"none")  # ciphername
    blob += _openssh_string(b"none")  # kdfname
    blob += _openssh_string(b"")  # kdfoptions
    blob += struct.pack(">I", 1)  # nkeys
    blob += _openssh_string(public_blob)
    blob += _openssh_string(block)

    b64 = base64.b64encode(blob).decode()
    lines = [b64[i : i + 70] for i in range(0, len(b64), 70)]
    return (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        + "\n".join(lines)
        + "\n-----END OPENSSH PRIVATE KEY-----\n"
    )


@pytest.fixture(scope="session")
def ed25519_seed() -> bytes:
    return bytes(range(1, 33))  # deterministic seed


@pytest.fixture(scope="session")
def openssh_pem(ed25519_seed: bytes) -> str:
    return serialize_openssh_ed25519_private_key(ed25519_seed)


@pytest.fixture(scope="session")
def aes_key() -> bytes:
    return hashlib.sha256(ENCRYPTION_KEY.encode()).digest()


def encrypt_response(data: Any, ed25519_seed: bytes) -> str:
    """Encrypt a JSON payload into the documented response blob format."""
    merchant_curve_pub = crypto_sign_ed25519_pk_to_curve25519(
        SigningKey(ed25519_seed).verify_key.encode()
    )
    ephemeral = PrivateKey.generate()
    box = Box(ephemeral, PublicKey(merchant_curve_pub))
    plaintext = json.dumps(data).encode()
    nonce = b"\x07" * 24
    ciphertext = box.encrypt(plaintext, nonce).ciphertext
    blob = nonce + ciphertext + bytes(ephemeral.public_key)
    return base64.b64encode(blob).decode()


def decrypt_request(body: dict[str, str], key: bytes) -> dict[str, Any]:
    """Decrypt an outgoing encrypted request envelope."""
    content = base64.b64decode(body["content"])
    iv = base64.b64decode(body["iv"])
    return json.loads(aes_decrypt(content, iv, key))


def success_payload(data: Any, seed: bytes) -> dict[str, Any]:
    return {"status": 200, "message": "Success", "data": encrypt_response(data, seed)}


@pytest.fixture()
def router() -> respx.MockRouter:
    with respx.MockRouter(base_url=BASE_URL, assert_all_called=False) as router:
        yield router


def aes_encrypt_independent(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    """Independent AES-256-CBC computation used to cross-check the library."""
    padder = sym_padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return encryptor.update(padded) + encryptor.finalize()
