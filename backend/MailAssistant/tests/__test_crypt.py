import statistics
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import os


# USED TO GENERATE KEYS (always the same for the same input)
def generate_encryption_key_unsalted():
    # Generate a random AES key
    aes_key = os.urandom(32)  # 32 bytes for AES-256
    # Encode the key as base64 string
    aes_key_base64 = base64.b64encode(aes_key).decode("utf-8")
    return aes_key_base64


def encrypt_unsalted(encryption_key: str, plaintext: str) -> str:
    """Encrypts input plaintext"""

    aes_key = base64.b64decode(encryption_key.encode("utf-8"))
    cipher = Cipher(algorithms.AES(aes_key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    padded_plaintext = plaintext + " " * (16 - len(plaintext) % 16)
    ciphertext = (
        encryptor.update(padded_plaintext.encode("utf-8")) + encryptor.finalize()
    )
    ciphertext_base64 = base64.b64encode(ciphertext).decode("utf-8")
    return ciphertext_base64


def decrypt_unsalted(encryption_key: str, ciphertext_base64: str) -> str:
    """Decrypts input encrypted ciphertext"""

    aes_key = base64.b64decode(encryption_key.encode("utf-8"))
    ciphertext = base64.b64decode(ciphertext_base64.encode("utf-8"))
    cipher = Cipher(algorithms.AES(aes_key), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_text = decryptor.update(ciphertext) + decryptor.finalize()
    unpadded_text = decrypted_text.rstrip()
    return unpadded_text.decode("utf-8")


# USING SALT => not same output for the same input
def generate_encryption_key():
    return Fernet.generate_key()


def encrypt_text(encryption_key: str, plaintext: str) -> str:
    """Encrypts input plaintext with salt"""

    fernet = Fernet(encryption_key)
    encrypted_text = fernet.encrypt(plaintext.encode())
    return encrypted_text.decode()


def decrypt_text(encryption_key: str, encrypted_text: str) -> str:
    """Decrypts input encrypted with salt"""

    fernet = Fernet(encryption_key)
    decrypted_text = fernet.decrypt(encrypted_text.encode())
    return decrypted_text.decode()


key = generate_encryption_key().decode('utf-8')

print(key)
token = ""
print(len(token))
enc = encrypt_text(key, token)
print(enc)
print(len(enc))