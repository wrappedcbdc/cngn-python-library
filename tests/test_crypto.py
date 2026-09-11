"""Crypto tests: AES round-trips cross-checked against an independent
implementation, NaCl Box known-answer, and OpenSSH parsing failures."""

from __future__ import annotations

import base64
import hashlib
import json
import struct

import pytest
from nacl.bindings import (
    crypto_sign_ed25519_pk_to_curve25519,
    crypto_sign_ed25519_sk_to_curve25519,
)
from nacl.public import Box, PrivateKey, PublicKey
from nacl.signing import SigningKey

from cngn._crypto import (
    aes_decrypt,
    aes_encrypt,
    decrypt_response_data,
    derive_aes_key,
    parse_openssh_ed25519_private_key,
)
from cngn._exceptions import DecryptionError, EncryptionError
from conftest import _openssh_string, aes_encrypt_independent


def test_derive_aes_key() -> None:
    assert derive_aes_key("k") == hashlib.sha256(b"k").digest()


def test_aes_round_trip(aes_key: bytes) -> None:
    plaintext = json.dumps({"amount": 1500, "bankCode": "058"}).encode()
    envelope = aes_encrypt(plaintext, aes_key)
    content = base64.b64decode(envelope["content"])
    iv = base64.b64decode(envelope["iv"])
    assert len(iv) == 16
    assert aes_decrypt(content, iv, aes_key) == plaintext


def test_aes_matches_independent_computation(aes_key: bytes) -> None:
    plaintext = b'{"reference":"abc"}'
    envelope = aes_encrypt(plaintext, aes_key)
    iv = base64.b64decode(envelope["iv"])
    expected = aes_encrypt_independent(plaintext, aes_key, iv)
    assert base64.b64decode(envelope["content"]) == expected


def test_aes_decrypt_bad_key_length() -> None:
    with pytest.raises(EncryptionError, match="32-byte key"):
        aes_encrypt(b"x", b"short")
    with pytest.raises(EncryptionError, match="32-byte key"):
        aes_decrypt(b"x" * 16, b"0" * 16, b"short")


def test_aes_decrypt_bad_iv_length(aes_key: bytes) -> None:
    with pytest.raises(EncryptionError, match="16-byte IV"):
        aes_decrypt(b"x" * 16, b"0" * 8, aes_key)


def test_aes_decrypt_corrupted_ciphertext(aes_key: bytes) -> None:
    envelope = aes_encrypt(b"hello world, this is padded", aes_key)
    content = bytearray(base64.b64decode(envelope["content"]))
    content[-1] ^= 0xFF
    iv = base64.b64decode(envelope["iv"])
    with pytest.raises(EncryptionError, match="AES decryption failed"):
        aes_decrypt(bytes(content), iv, aes_key)


def test_openssh_key_round_trip(ed25519_seed: bytes, openssh_pem: str) -> None:
    assert parse_openssh_ed25519_private_key(openssh_pem) == ed25519_seed


def test_openssh_rejects_wrong_pem_armor() -> None:
    with pytest.raises(DecryptionError, match="OpenSSH PEM"):
        parse_openssh_ed25519_private_key(
            "-----BEGIN RSA PRIVATE KEY-----\nAAAA\n-----END RSA PRIVATE KEY-----"
        )


def test_openssh_rejects_bad_base64() -> None:
    pem = "-----BEGIN OPENSSH PRIVATE KEY-----\n!!!not-base64!!!\n-----END OPENSSH PRIVATE KEY-----"
    with pytest.raises(DecryptionError, match="not valid base64"):
        parse_openssh_ed25519_private_key(pem)


def test_openssh_rejects_missing_magic() -> None:
    blob = base64.b64encode(b"not-openssh-at-all-payload")
    pem = f"-----BEGIN OPENSSH PRIVATE KEY-----\n{blob.decode()}\n-----END OPENSSH PRIVATE KEY-----"
    with pytest.raises(DecryptionError, match="openssh-key-v1"):
        parse_openssh_ed25519_private_key(pem)


def _build_blob(ciphername: bytes, private_block: bytes) -> str:
    blob = b"openssh-key-v1\x00"
    blob += _openssh_string(ciphername)
    blob += _openssh_string(b"none")
    blob += _openssh_string(b"")
    blob += struct.pack(">I", 1)
    blob += _openssh_string(_openssh_string(b"ssh-ed25519") + _openssh_string(b"\x00" * 32))
    blob += _openssh_string(private_block)
    b64 = base64.b64encode(blob).decode()
    return "-----BEGIN OPENSSH PRIVATE KEY-----\n" + b64 + "\n-----END OPENSSH PRIVATE KEY-----"


def test_openssh_rejects_encrypted_keys(ed25519_seed: bytes) -> None:
    # An encrypted key would have ciphername "aes256-ctr"; the private block
    # content is irrelevant because parsing stops at the ciphername.
    pem = _build_blob(b"aes256-ctr", b"\x00" * 16)
    with pytest.raises(DecryptionError, match="Encrypted OpenSSH private keys"):
        parse_openssh_ed25519_private_key(pem)


def test_openssh_rejects_checkint_mismatch(ed25519_seed: bytes) -> None:
    seed = ed25519_seed
    verify_key = SigningKey(seed).verify_key.encode()
    block = struct.pack(">I", 0x11111111)
    block += struct.pack(">I", 0x22222222)
    block += _openssh_string(b"ssh-ed25519")
    block += _openssh_string(verify_key)
    block += _openssh_string(verify_key + seed)
    block += _openssh_string(b"")
    block += bytes(range(1, 8 - (len(block) % 8) + 1))
    pem = _build_blob(b"none", block)
    with pytest.raises(DecryptionError, match="checkints do not match"):
        parse_openssh_ed25519_private_key(pem)


def test_openssh_rejects_truncated_blob() -> None:
    blob = base64.b64encode(b"openssh-key-v1\x00\x00")
    pem = f"-----BEGIN OPENSSH PRIVATE KEY-----\n{blob.decode()}\n-----END OPENSSH PRIVATE KEY-----"
    with pytest.raises(DecryptionError, match=r"[Tt]runcated"):
        parse_openssh_ed25519_private_key(pem)


def test_decrypt_response_data_known_answer(ed25519_seed: bytes, openssh_pem: str) -> None:
    """Encrypt with an independent pynacl Box; the library must decrypt it."""
    data = {"balance": "150000.00", "asset_code": "CNGN"}
    merchant_curve_pub = crypto_sign_ed25519_pk_to_curve25519(
        SigningKey(ed25519_seed).verify_key.encode()
    )
    ephemeral = PrivateKey.generate()
    box = Box(ephemeral, PublicKey(merchant_curve_pub))
    nonce = b"\x01" * 24
    ciphertext = box.encrypt(json.dumps(data).encode(), nonce).ciphertext
    blob = base64.b64encode(nonce + ciphertext + bytes(ephemeral.public_key)).decode()

    assert decrypt_response_data(blob, openssh_pem) == data


def test_decrypt_response_data_key_derivation_matches_libsodium(
    ed25519_seed: bytes, openssh_pem: str
) -> None:
    """The converted Curve25519 key must equal libsodium's conversion."""
    seed = parse_openssh_ed25519_private_key(openssh_pem)
    public_key = SigningKey(seed).verify_key.encode()
    curve_sk = crypto_sign_ed25519_sk_to_curve25519(seed + public_key)
    # Sanity: converting to a box and self-encrypting round-trips.
    box = Box(PrivateKey(curve_sk), PublicKey(crypto_sign_ed25519_pk_to_curve25519(public_key)))
    ct = box.encrypt(b"ping", b"\x02" * 24)
    assert (
        Box(
            PrivateKey(curve_sk), PublicKey(crypto_sign_ed25519_pk_to_curve25519(public_key))
        ).decrypt(ct)
        == b"ping"
    )


def test_decrypt_response_data_rejects_bad_base64(openssh_pem: str) -> None:
    with pytest.raises(DecryptionError, match="not valid base64"):
        decrypt_response_data("!!!", openssh_pem)


def test_decrypt_response_data_rejects_short_blob(openssh_pem: str) -> None:
    blob = base64.b64encode(b"\x00" * 20).decode()
    with pytest.raises(DecryptionError, match="too short"):
        decrypt_response_data(blob, openssh_pem)


def test_decrypt_response_data_wrong_key(openssh_pem: str) -> None:
    other_seed = b"\xaa" * 32
    other_curve_pub = crypto_sign_ed25519_pk_to_curve25519(
        SigningKey(other_seed).verify_key.encode()
    )
    ephemeral = PrivateKey.generate()
    box = Box(ephemeral, PublicKey(other_curve_pub))
    nonce = b"\x03" * 24
    ciphertext = box.encrypt(b'{"a": 1}', nonce).ciphertext
    blob = base64.b64encode(nonce + ciphertext + bytes(ephemeral.public_key)).decode()
    with pytest.raises(DecryptionError, match="Failed to decrypt response data"):
        decrypt_response_data(blob, openssh_pem)
