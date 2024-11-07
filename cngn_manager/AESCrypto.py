from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import base64
class AESCrypto:
    ALGORITHM = algorithms.AES
    IV_LENGTH = 16
    KEY_LENGTH = 32  # 256 bits
    BLOCK_SIZE = 16  # AES block size
    class InvalidPaddingError(Exception):
        pass
    @staticmethod
    def prepare_key(key: str) -> bytes:
        # Hash the key using SHA-256 to ensure it's always the correct length (32 bytes)
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(key.encode('utf-8'))
        return digest.finalize()
    @staticmethod
    def pkcs7_pad(data: bytes) -> bytes:
        """Apply PKCS7 padding to the data."""
        padding_length = AESCrypto.BLOCK_SIZE - (len(data) % AESCrypto.BLOCK_SIZE)
        padding = bytes([padding_length] * padding_length)
        return data + padding
    @staticmethod
    def pkcs7_unpad(data: bytes) -> bytes:
        """
        Remove and validate PKCS7 padding.
        Raises InvalidPaddingError if padding is incorrect.
        """
        if len(data) == 0:
            raise AESCrypto.InvalidPaddingError("Empty data")
        if len(data) % AESCrypto.BLOCK_SIZE != 0:
            raise AESCrypto.InvalidPaddingError("Data length not multiple of block size")
        padding_length = data[-1]
        if padding_length == 0 or padding_length > AESCrypto.BLOCK_SIZE:
            raise AESCrypto.InvalidPaddingError("Invalid padding length")
        if len(data) < padding_length:
            raise AESCrypto.InvalidPaddingError("Padding length larger than data")
        # Check all padding bytes are correct
        padding = data[-padding_length:]
        if not all(x == padding_length for x in padding):
            raise AESCrypto.InvalidPaddingError("Invalid padding values")
        return data[:-padding_length]
    @staticmethod
    def encrypt(data: str, key: str) -> dict:
        # Generate a random Initialization Vector (IV)
        iv = os.urandom(AESCrypto.IV_LENGTH)
        key_buffer = AESCrypto.prepare_key(key)
        # Create cipher and encrypt the data
        cipher = Cipher(AESCrypto.ALGORITHM(key_buffer), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        # Properly pad data using PKCS7
        padded_data = AESCrypto.pkcs7_pad(data.encode('utf-8'))
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        # Return the encrypted content and the IV (both base64 encoded)
        return {
            'content': base64.b64encode(encrypted).decode('utf-8'),
            'iv': base64.b64encode(iv).decode('utf-8')
        }
    @staticmethod
    def decrypt(encrypted_data: dict, key: str) -> str:
        try:
            # Decode the base64 encoded IV and content
            iv = base64.b64decode(encrypted_data['iv'])
            encrypted_content = base64.b64decode(encrypted_data['content'])
            key_buffer = AESCrypto.prepare_key(key)
            # Create cipher and decrypt the data
            cipher = Cipher(AESCrypto.ALGORITHM(key_buffer), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(encrypted_content) + decryptor.finalize()
            # Remove padding with validation
            unpadded = AESCrypto.pkcs7_unpad(decrypted)
            return unpadded.decode('utf-8')
        except AESCrypto.InvalidPaddingError as e:
            # Handle padding errors uniformly to prevent timing attacks
            raise AESCrypto.InvalidPaddingError("Decryption failed")
        except Exception as e:
            # Handle all other errors uniformly
            raise AESCrypto.InvalidPaddingError("Decryption failed")