"""InevioNet Cryptography. AES-256-GCM + Ed25519 + X25519."""
import os
import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption)
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag, InvalidSignature

from .exceptions import (CryptoError, EncryptionError, DecryptionError,
                          IntegrityError, KeyError)


KDF_ITERATIONS = 100000
KEY_LENGTH = 32
SALT_LENGTH = 32
NONCE_LENGTH = 12


def generate_salt(length: int = SALT_LENGTH) -> bytes:
    return os.urandom(length)


def generate_nonce(length: int = NONCE_LENGTH) -> bytes:
    return os.urandom(length)


def derive_key(password: str, salt: bytes, iterations: int = KDF_ITERATIONS) -> bytes:
    if not password:
        raise KeyError("Password cannot be empty")
    if not salt:
        raise KeyError("Salt cannot be empty")
    try:
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_LENGTH,
                         salt=salt, iterations=iterations, backend=default_backend())
        return kdf.derive(password.encode("utf-8"))
    except Exception as e:
        raise KeyError(f"Key derivation failed: {e}", original=e)


def derive_key_with_stretching(password, salt=None, iterations=KDF_ITERATIONS):
    if salt is None:
        salt = generate_salt()
    return derive_key(password, salt, iterations), salt


class SymmetricCipher:
    def __init__(self, key: bytes):
        if len(key) != KEY_LENGTH:
            raise KeyError(f"Key must be {KEY_LENGTH} bytes")
        self._key = key
        self._aes = AESGCM(key)

    def encrypt(self, plaintext: bytes, aad: bytes = None, nonce: bytes = None) -> bytes:
        if nonce is None:
            nonce = generate_nonce()
        if len(nonce) != NONCE_LENGTH:
            raise EncryptionError(f"Nonce must be {NONCE_LENGTH} bytes")
        try:
            ct = self._aes.encrypt(nonce, plaintext, aad)
            return nonce + ct
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}", original=e)

    def decrypt(self, ciphertext: bytes, aad: bytes = None) -> bytes:
        if len(ciphertext) < NONCE_LENGTH + 16:
            raise DecryptionError("Ciphertext too short")
        nonce = ciphertext[:NONCE_LENGTH]
        actual = ciphertext[NONCE_LENGTH:]
        try:
            return self._aes.decrypt(nonce, actual, aad)
        except InvalidTag:
            raise IntegrityError("Integrity check failed")
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}", original=e)


@dataclass
class KeyPair:
    private_key: bytes
    public_key: bytes
    algorithm: str = "Ed25519"

    def to_dict(self):
        return {"private": base64.b64encode(self.private_key).decode(),
                "public": base64.b64encode(self.public_key).decode(),
                "algorithm": self.algorithm}


def generate_signing_keypair() -> KeyPair:
    try:
        sk = ed25519.Ed25519PrivateKey.generate()
        pk = sk.public_key()
        return KeyPair(
            sk.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()),
            pk.public_bytes(Encoding.Raw, PublicFormat.Raw),
            "Ed25519")
    except Exception as e:
        raise KeyError(f"Signing keypair generation failed: {e}", original=e)


def generate_exchange_keypair() -> KeyPair:
    try:
        sk = x25519.X25519PrivateKey.generate()
        pk = sk.public_key()
        return KeyPair(
            sk.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()),
            pk.public_bytes(Encoding.Raw, PublicFormat.Raw),
            "X25519")
    except Exception as e:
        raise KeyError(f"Exchange keypair generation failed: {e}", original=e)


def sign_data(private_key_bytes: bytes, data: bytes) -> bytes:
    try:
        sk = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        return sk.sign(data)
    except Exception as e:
        raise CryptoError(f"Sign failed: {e}", original=e)


def verify_signature(public_key_bytes: bytes, signature: bytes, data: bytes) -> bool:
    try:
        pk = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        pk.verify(signature, data)
        return True
    except InvalidSignature:
        return False
    except Exception as e:
        raise CryptoError(f"Verify failed: {e}", original=e)


def derive_shared_secret(private_key_bytes: bytes, peer_public_key_bytes: bytes) -> bytes:
    try:
        sk = x25519.X25519PrivateKey.from_private_bytes(private_key_bytes)
        pk = x25519.X25519PublicKey.from_public_bytes(peer_public_key_bytes)
        return sk.exchange(pk)
    except Exception as e:
        raise CryptoError(f"ECDH failed: {e}", original=e)


def hash_data(data: bytes, algorithm: str = "sha256") -> bytes:
    if algorithm == "sha256":
        h = hashlib.sha256()
    elif algorithm == "sha512":
        h = hashlib.sha512()
    elif algorithm == "sha3_256":
        h = hashlib.sha3_256()
    elif algorithm == "blake2b":
        h = hashlib.blake2b()
    else:
        raise CryptoError(f"Unsupported hash: {algorithm}")
    h.update(data)
    return h.digest()


def hash_hex(data: bytes, algorithm: str = "sha256", length: int = 0) -> str:
    h = hash_data(data, algorithm).hex()
    return h[:length] if length > 0 else h


def hmac_sign(key: bytes, data: bytes) -> bytes:
    h = hmac.new(key, data, hashlib.sha256)
    return h.digest()


def hmac_verify(key: bytes, data: bytes, signature: bytes) -> bool:
    return hmac.compare_digest(hmac_sign(key, data), signature)


def random_bytes(length: int) -> bytes:
    return secrets.token_bytes(length)


def random_hex(length: int = 16) -> str:
    return secrets.token_hex(length)


def random_id(prefix: str = "", length: int = 8) -> str:
    timestamp = int(time.time())
    rand = secrets.token_hex(length // 2)
    return f"{prefix}_{timestamp}_{rand}" if prefix else f"{timestamp}_{rand}"


def constant_time_compare(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)


class InevioCrypto:
    """Main crypto class."""

    def __init__(self, password: str = None, key: bytes = None, salt: bytes = None):
        if key is not None:
            if len(key) != KEY_LENGTH:
                raise KeyError(f"Key must be {KEY_LENGTH} bytes")
            self._key = key
            self._salt = salt or b""
        elif password:
            self._key, self._salt = derive_key_with_stretching(password, salt)
        else:
            raise KeyError("Password or key required")
        self._cipher = SymmetricCipher(self._key)
        self._signing_keypair = None
        self._exchange_keypair = None

    def encrypt(self, data: bytes, aad: bytes = None) -> bytes:
        return self._cipher.encrypt(data, aad)

    def decrypt(self, ciphertext: bytes, aad: bytes = None) -> bytes:
        return self._cipher.decrypt(ciphertext, aad)

    def encrypt_str(self, text: str, aad: bytes = None) -> bytes:
        return self.encrypt(text.encode("utf-8"), aad)

    def decrypt_str(self, ciphertext: bytes, aad: bytes = None) -> str:
        return self.decrypt(ciphertext, aad).decode("utf-8")

    def encrypt_b64(self, data: bytes) -> str:
        return base64.urlsafe_b64encode(self.encrypt(data)).decode("ascii")

    def decrypt_b64(self, b64: str) -> bytes:
        return self.decrypt(base64.urlsafe_b64decode(b64.encode("ascii")))

    def get_signing_keypair(self) -> KeyPair:
        if self._signing_keypair is None:
            self._signing_keypair = generate_signing_keypair()
        return self._signing_keypair

    def get_exchange_keypair(self) -> KeyPair:
        if self._exchange_keypair is None:
            self._exchange_keypair = generate_exchange_keypair()
        return self._exchange_keypair

    def sign(self, data: bytes) -> bytes:
        return sign_data(self.get_signing_keypair().private_key, data)

    def verify(self, data: bytes, signature: bytes, public_key: bytes = None) -> bool:
        if public_key is None:
            public_key = self.get_signing_keypair().public_key
        return verify_signature(public_key, signature, data)

    @staticmethod
    def hash(data: bytes, algorithm: str = "sha256") -> bytes:
        return hash_data(data, algorithm)

    @staticmethod
    def hash_hex(data: bytes, algorithm: str = "sha256", length: int = 16) -> str:
        return hash_hex(data, algorithm, length)

    @staticmethod
    def hmac(key: bytes, data: bytes) -> bytes:
        return hmac_sign(key, data)

    def export_key(self) -> str:
        return base64.b64encode(self._key).decode("ascii")

    def export_salt(self) -> str:
        return base64.b64encode(self._salt).decode("ascii") if self._salt else ""

    @classmethod
    def from_export(cls, key_b64: str, salt_b64: str = ""):
        key = base64.b64decode(key_b64.encode("ascii"))
        salt = base64.b64decode(salt_b64.encode("ascii")) if salt_b64 else None
        return cls(key=key, salt=salt)

    def __repr__(self):
        return f"InevioCrypto(algorithm=AES-256-GCM, key_length={len(self._key)})"


if __name__ == "__main__":
    print("Testing InevioCrypto...")
    crypto = InevioCrypto("test_password")
    data = b"Hello, InevioNet!"
    enc = crypto.encrypt(data)
    dec = crypto.decrypt(enc)
    assert dec == data
    print("OK: encrypt/decrypt")

    kp = generate_signing_keypair()
    sig = sign_data(kp.private_key, data)
    assert verify_signature(kp.public_key, sig, data)
    print("OK: sign/verify")
    print("ALL TESTS PASSED")
