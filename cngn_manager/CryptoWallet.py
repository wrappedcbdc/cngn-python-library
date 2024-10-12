from ecdsa import SigningKey, SECP256k1
from mnemonic import Mnemonic
from bip32utils import BIP32Key, BIP32_HARDEN
from tronpy import Tron
from tronpy.keys import PrivateKey, PublicKey
from hashlib import sha3_256
from stellar_sdk import Keypair, StrKey
import coinaddrvalidator
import nacl.signing
import nacl.encoding
from .constants import Network  # Assuming you have a Network class or Enum in constants

class CryptoWallet:

    DERIVATION_PATHS = {
        Network.ETH: "m/44'/60'/0'/0/0",
        Network.BSC: "m/44'/60'/0'/0/0",
        Network.ATC: "m/44'/60'/0'/0/0",
        Network.MATIC: "m/44'/60'/0'/0/0",
        Network.TRX: "m/44'/195'/0'/0/0",  # TRON's derivation path
        Network.XBN: "m/44'/703'/0'/0"     # XBN's derivation path
    }

    @staticmethod
    def generate_wallet_with_mnemonic_details(network: str):
        mnemo = Mnemonic("english")
        mnemonic = mnemo.generate(strength=128)
        return CryptoWallet.generate_wallet_from_mnemonic(mnemonic, network)

    @staticmethod
    def generate_wallet_from_mnemonic(mnemonic: str, network: str):
        if network == Network.XBN:
            return CryptoWallet.generate_xbn_wallet(mnemonic)
        elif network == Network.TRX:
            return CryptoWallet.generate_trx_wallet(mnemonic)

        private_key = CryptoWallet.get_private_key_from_mnemonic(mnemonic, network)
        public_key = CryptoWallet.get_public_key(private_key, network)
        address = CryptoWallet.get_address_from_public_key(public_key, network)
        
        return {'mnemonic': mnemonic, 'privateKey': private_key, 'address': address, 'network': network}

    @staticmethod
    def get_public_key(private_key: str, network: str):
        if network == Network.XBN:
            seed = nacl.signing.SigningKey(bytes.fromhex(private_key))
            return seed.verify_key.encode().hex()
        sk = SigningKey.from_string(bytes.fromhex(private_key), curve=SECP256k1)
        return sk.verifying_key.to_string().hex()

    @staticmethod
    def get_private_key_from_mnemonic(mnemonic: str, network: str):
        seed = Mnemonic.to_seed(mnemonic)
        derivation_path = CryptoWallet.DERIVATION_PATHS[network]
        # Use BIP32Key derivation according to the provided network path
        key = BIP32Key.fromEntropy(seed)
        for index in derivation_path.split("/")[1:]:
            if index.endswith("'"):
                index = int(index[:-1]) + 0x80000000
            else:
                index = int(index)
            key = key.ChildKey(index)
        return key.PrivateKey().hex()

    @staticmethod
    def get_address_from_public_key(public_key: str, network: str):
        if network in [Network.ETH, Network.BSC, Network.MATIC, Network.ATC]:
            return CryptoWallet.get_ethereum_style_address(public_key)
        elif network == Network.TRX:
            return CryptoWallet.get_tron_address_from_public_key(public_key)
        raise ValueError(f'Unsupported network: {network}')

    @staticmethod
    def get_ethereum_style_address(public_key: str):
        clean_public_key = public_key[2:] if public_key.startswith('04') else public_key
        hash = sha3_256(bytes.fromhex(clean_public_key)).digest()
        return '0x' + hash[-20:].hex()

    @staticmethod
    def generate_trx_wallet(mnemonic: str):
        private_key = CryptoWallet.get_private_key_from_mnemonic(mnemonic, Network.TRX)
        tron_private_key = PrivateKey(bytes.fromhex(private_key))
        address = tron_private_key.public_key.to_base58check_address()

        return {
            'mnemonic': mnemonic,
            'privateKey': tron_private_key.hex(),
            'address': address,
            'network': Network.TRX
        }

    @staticmethod
    def get_tron_address_from_public_key(public_key: str):
        public_key_bytes = bytes.fromhex(public_key)
        if len(public_key_bytes) != 64:
            raise ValueError("Invalid public key length")

        tron_address = PublicKey(public_key_bytes).to_base58check_address()
        return tron_address
    
    @staticmethod
    def generate_xbn_wallet(mnemonic: str):
        # Derive BIP32 seed from mnemonic
        seed = Mnemonic.to_seed(mnemonic)
        derivation_path = CryptoWallet.DERIVATION_PATHS[Network.XBN]
        master_key = BIP32Key.fromEntropy(seed)
        
        for index in derivation_path.split("/")[1:]:
            if index.endswith("'"):
                index = int(index[:-1]) + BIP32_HARDEN # Hardened key
            else:
                index = int(index)
            key = master_key.ChildKey(index)

        raw_secret_key = key.PrivateKey()
        secret_key = StrKey.encode_ed25519_secret_seed(raw_secret_key)
        keypair = Keypair.from_secret(secret_key)

        return {
            'mnemonic': mnemonic,
            'privateKey': keypair.secret,
            'address': keypair.public_key,
            'network': Network.XBN
        }

    @staticmethod
    def validate_address(address: str, network: str):
        if network in [Network.ETH, Network.BSC, Network.MATIC, Network.ATC]:
            result = coinaddrvalidator.validate(network, address)
            print(f'Validation result for {network}: {result}')
            return result
        elif network == Network.TRX:
            tron = Tron()
            return tron.is_address(address)
        elif network == Network.XBN:
            result = coinaddrvalidator.validate(network, address)
            print(f'Validation result for {network}: {result}')
            return result
        raise ValueError(f'Unsupported network: {network}')