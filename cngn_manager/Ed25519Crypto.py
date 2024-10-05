from nacl.public import PrivateKey, PublicKey, Box
from nacl.encoding import Base64Encoder
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519
import base64
import re

class Ed25519Crypto:
    is_initialized = False

    @staticmethod
    def initialize():
        if not Ed25519Crypto.is_initialized:
            # No explicit initialization is required for PyNaCl, but we keep this as a safeguard.
            Ed25519Crypto.is_initialized = True

    @staticmethod
    def parse_openssh_private_key(private_key: str) -> bytes:
        """
        Parses an OpenSSH Ed25519 private key to extract the 32-byte private key.
        
        :param private_key: The OpenSSH private key string.
        :return: The 32-byte Ed25519 private key as bytes.
        """
        # Remove the key header/footer and decode the base64 content
        private_key_stripped = re.sub(r'-----.* PRIVATE KEY-----', '', private_key).strip()
        private_key_stripped = re.sub(r"\s+", '', private_key_stripped)
        private_key_buffer = base64.b64decode(private_key_stripped)

        # Look for Ed25519 key data (00 00 00 20)
        key_data_start = private_key_buffer.find(b'\x00\x00\x00\x40')
        if key_data_start == -1:
            raise Exception('Unable to find Ed25519 key data')

        # The key starts after 0x00 0x00 0x00 0x20 (32-byte key length marker)
        return private_key_buffer[key_data_start + 4: key_data_start + 68]

    @staticmethod
    def decrypt_with_private_key(ed25519_private_key: str, encrypted_data: str) -> str:
        """
        Decrypts data using an Ed25519 private key (converted to Curve25519).
        
        :param ed25519_private_key: The OpenSSH Ed25519 private key string.
        :param encrypted_data: The encrypted data in base64 format.
        :return: The decrypted plaintext as a string.
        """
        Ed25519Crypto.initialize()

        try:
            # Parse the OpenSSH private key format and extract the Ed25519 private key
            ed25519_private_key_bytes = Ed25519Crypto.parse_openssh_private_key(ed25519_private_key)

            # Convert Ed25519 private key to Curve25519 private key for use with Box
            curve25519_private_key_bytes = crypto_sign_ed25519_sk_to_curve25519(ed25519_private_key_bytes)
            private_key = PrivateKey(curve25519_private_key_bytes)

            # Decode the base64-encoded encrypted data
            encrypted_buffer = base64.b64decode(encrypted_data)

            # Extract nonce (24 bytes), ephemeral public key (32 bytes), and ciphertext
            nonce = encrypted_buffer[:24]
            ephemeral_public_key = PublicKey(encrypted_buffer[-32:])
            ciphertext = encrypted_buffer[24:-32]

            # Create a Box with the recipient's Curve25519 private key and the sender's ephemeral public key
            box = Box(private_key, ephemeral_public_key)

            # Decrypt the ciphertext
            decrypted = box.decrypt(ciphertext, nonce)

            return decrypted.decode('utf-8')

        except Exception as e:
            raise Exception("Failed to decrypt with the provided Ed25519 private key: " + str(e))

