"""HD wallet address generation and validation.

EVM networks (Ethereum, Base, BSC, Polygon) share the derivation path
``m/44'/60'/0'/0/0``. Tron derives at ``m/44'/195'/0'/0/0`` and
Stellar follows SEP-0005 (``m/44'/148'/0'``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Network(str, Enum):
    ETHEREUM = "ethereum"
    BASE = "base"
    BSC = "bsc"
    POLYGON = "polygon"
    TRON = "tron"
    STELLAR = "stellar"


_EVM_NETWORKS = {Network.ETHEREUM, Network.BASE, Network.BSC, Network.POLYGON}

_ETH_COIN_TYPE = 60  # SLIP-44; shared by every EVM network above
_TRON_COIN_TYPE = 195


@dataclass(frozen=True)
class GeneratedWallet:
    network: Network
    address: str
    public_key: str
    private_key: str
    mnemonic: str


def _mnemonic_module():
    from mnemonic import Mnemonic

    return Mnemonic("english")


def _keccak(data: bytes) -> bytes:
    from eth_utils import keccak

    return keccak(data)


def _derive_secp256k1_key(seed: bytes, coin_type: int) -> bytes:
    import bip32utils

    node = (
        bip32utils.BIP32Key.fromEntropy(seed)
        .ChildKey(44 + bip32utils.BIP32_HARDEN)
        .ChildKey(coin_type + bip32utils.BIP32_HARDEN)
        .ChildKey(0 + bip32utils.BIP32_HARDEN)
        .ChildKey(0)
        .ChildKey(0)
    )
    return node.PrivateKey()


def _evm_address(private_key: bytes) -> str:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    key = ec.derive_private_key(int.from_bytes(private_key, "big"), ec.SECP256K1())
    public_bytes = key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return _eip55_checksum(_keccak(public_bytes[1:])[-20:])


def _eip55_checksum(address_bytes: bytes) -> str:
    hex_address = address_bytes.hex()
    hashed = _keccak(hex_address.encode()).hex()
    return "0x" + "".join(
        char.upper() if char.isalpha() and int(hashed[i], 16) >= 8 else char
        for i, char in enumerate(hex_address)
    )


def generate_wallet_address(
    network: Network | str = Network.ETHEREUM, mnemonic: str | None = None
) -> GeneratedWallet:
    """Generate a new HD wallet address for ``network``.

    Pass ``mnemonic`` to restore an existing wallet; a fresh 12-word
    mnemonic is generated otherwise. Base uses the standard EVM path
    ``m/44'/60'/0'/0/0``, identical to Ethereum.
    """
    network = Network(network)
    mnemo = _mnemonic_module()
    phrase = mnemonic or mnemo.generate(strength=128)
    if not mnemo.check(phrase):
        raise ValueError("Invalid BIP-39 mnemonic")

    if network in _EVM_NETWORKS:
        seed = mnemo.to_seed(phrase)
        private_key = _derive_secp256k1_key(seed, _ETH_COIN_TYPE)
        address = _evm_address(private_key)
        return GeneratedWallet(network, address, "", private_key.hex(), phrase)
    if network is Network.TRON:
        seed = mnemo.to_seed(phrase)
        private_key = _derive_secp256k1_key(seed, _TRON_COIN_TYPE)
        from tronpy.keys import PrivateKey as TronPrivateKey

        tron_public_key = TronPrivateKey(private_key).public_key
        if tron_public_key is None:  # tronpy types this Optional; a valid key never is
            raise ValueError("Could not derive Tron public key")
        address = tron_public_key.to_base58check_address()
        return GeneratedWallet(network, address, "", private_key.hex(), phrase)
    if network is Network.STELLAR:
        from stellar_sdk import Keypair

        keypair = Keypair.from_mnemonic_phrase(phrase, passphrase="", index=0)
        return GeneratedWallet(
            network, keypair.public_key, keypair.public_key, keypair.secret, phrase
        )
    raise ValueError(f"Unsupported network: {network}")


def validate_address(address: str, network: Network | str = Network.ETHEREUM) -> bool:
    """Validate an address for ``network``; returns False (never raises)."""
    try:
        network = Network(network)
        if network in _EVM_NETWORKS:
            return _validate_evm(address)
        if network is Network.TRON:
            from tronpy.keys import is_base58check_address

            return bool(is_base58check_address(address))
        if network is Network.STELLAR:
            from stellar_sdk.strkey import StrKey

            return bool(StrKey.is_valid_ed25519_public_key(address))
    except Exception:
        return False
    return False


def _validate_evm(address: str) -> bool:
    if not address.startswith("0x") or len(address) != 42:
        return False
    hex_part = address[2:]
    try:
        raw = bytes.fromhex(hex_part)
    except ValueError:
        return False
    if hex_part.islower() or hex_part.isupper():
        return True  # all-lower/all-upper addresses carry no checksum
    return _eip55_checksum(raw) == address
