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

    @staticmethod
    def prepare_key(key: str) -> bytes:
        # Hash the key using SHA-256 to ensure it's always the correct length (32 bytes)
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(key.encode('utf-8'))
        return digest.finalize()

    @staticmethod
    def encrypt(data: str, key: str) -> dict:
        # Generate a random Initialization Vector (IV)
        iv = os.urandom(AESCrypto.IV_LENGTH)
        key_buffer = AESCrypto.prepare_key(key)

        # Create cipher and encrypt the data
        cipher = Cipher(AESCrypto.ALGORITHM(key_buffer), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # Pad data to be multiple of 16 bytes (block size for AES)
        padding_length = 16 - (len(data) % 16)
        padded_data = data + chr(padding_length) * padding_length
        encrypted = encryptor.update(padded_data.encode('utf-8')) + encryptor.finalize()

        # Return the encrypted content and the IV (both base64 encoded)
        return {
            'content': base64.b64encode(encrypted).decode('utf-8'),
            'iv': base64.b64encode(iv).decode('utf-8')
        }

    @staticmethod
    def decrypt(encrypted_data: dict, key: str) -> str:
        # Decode the base64 encoded IV and content
        iv = base64.b64decode(encrypted_data['iv'])
        encrypted_content = base64.b64decode(encrypted_data['content'])
        key_buffer = AESCrypto.prepare_key(key)

        # Create cipher and decrypt the data
        cipher = Cipher(AESCrypto.ALGORITHM(key_buffer), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        decrypted = decryptor.update(encrypted_content) + decryptor.finalize()

        # Remove padding
        padding_length = decrypted[-1]
        decrypted = decrypted[:-padding_length]

        return decrypted.decode('utf-8')
