"""Wallet tests — gated on the optional [wallet] extra dependencies."""

from __future__ import annotations

import pytest

pytest.importorskip("mnemonic")
pytest.importorskip("bip32utils")
pytest.importorskip("tronpy")
pytest.importorskip("stellar_sdk")

from cngn.wallet import Network, generate_wallet_address, validate_address

# Well-known BIP-39 test mnemonic (abandon x11 + about) used across the
# ecosystem; its m/44'/60'/0'/0/0 address is a documented known-answer.
TEST_MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
)
ETH_KNOWN_ADDRESS = "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"


def test_base_address_generation_known_answer() -> None:
    wallet = generate_wallet_address(Network.BASE, mnemonic=TEST_MNEMONIC)
    assert wallet.address == ETH_KNOWN_ADDRESS
    assert validate_address(wallet.address, Network.BASE)


def test_base_matches_ethereum_derivation() -> None:
    eth = generate_wallet_address("ethereum", mnemonic=TEST_MNEMONIC)
    base = generate_wallet_address("base", mnemonic=TEST_MNEMONIC)
    assert eth.address == base.address  # same path m/44'/60'/0'/0/0


def test_fresh_mnemonic_generation() -> None:
    wallet = generate_wallet_address(Network.BASE)
    assert len(wallet.mnemonic.split()) == 12
    assert wallet.address.startswith("0x") and len(wallet.address) == 42
    # deterministic from its own mnemonic
    assert generate_wallet_address(Network.BASE, mnemonic=wallet.mnemonic).address == wallet.address


def test_validate_evm_addresses() -> None:
    assert validate_address(ETH_KNOWN_ADDRESS, "ethereum")  # checksummed
    assert validate_address(ETH_KNOWN_ADDRESS.lower(), "ethereum")  # all-lower OK
    assert not validate_address("0x123", "ethereum")
    assert not validate_address("not-an-address", "ethereum")
    bad_checksum = ETH_KNOWN_ADDRESS.replace("Ef", "ef", 1)  # flips a checksummed char
    assert not validate_address(bad_checksum, "ethereum")


def test_tron_generation_and_validation() -> None:
    wallet = generate_wallet_address(Network.TRON, mnemonic=TEST_MNEMONIC)
    assert wallet.address.startswith("T")
    assert validate_address(wallet.address, Network.TRON)
    assert not validate_address(wallet.address, "ethereum")


def test_stellar_generation_and_validation() -> None:
    wallet = generate_wallet_address(Network.STELLAR, mnemonic=TEST_MNEMONIC)
    assert wallet.address.startswith("G")
    assert validate_address(wallet.address, Network.STELLAR)
    assert not validate_address("GINVALID", Network.STELLAR)


def test_invalid_mnemonic_raises() -> None:
    with pytest.raises(ValueError, match="Invalid BIP-39"):
        generate_wallet_address(Network.BASE, mnemonic="abandon abandon abandon")


def test_validate_unknown_network_returns_false() -> None:
    assert validate_address("0x" + "ab" * 20, "dogecoin") is False
