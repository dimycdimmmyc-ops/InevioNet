"""InevioNet Security - E2E encryption (X25519 + AES-256-GCM, sender-side PFS)
+ strong password hashing (PBKDF2-HMAC-SHA256) with legacy fallback."""
import os
import hashlib
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption)

PBKDF2_ITER = 120000
_KDF_SALT = b"inevionet-exch-v1"


def hash_password(password, salt=None):
    """PBKDF2-HMAC-SHA256, 120k iterations. Returns (salt, stored_hash)."""
    salt = salt or os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITER)
    return salt, "pbkdf2$%d$%s" % (PBKDF2_ITER, dk.hex())


def verify_password(password, salt, stored):
    """Returns (ok, is_modern). Legacy sha256 hashes accepted for upgrade."""
    if stored.startswith("pbkdf2$"):
        _, iters, hexdig = stored.split("$", 2)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
        return dk.hex() == hexdig, True
    legacy = hashlib.sha256(("%s:%s" % (salt, password)).encode()).hexdigest()
    return legacy == stored, False


def make_exchange_pair():
    """New X25519 exchange keypair. Returns (priv_hex, pub_hex)."""
    priv = X25519PrivateKey.generate()
    priv_b = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_b = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return priv_b.hex(), pub_b.hex()


def seal_key(password, priv_hex):
    """Encrypt exchange private key with password-derived key (AES-256-GCM)."""
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), _KDF_SALT, PBKDF2_ITER)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, bytes.fromhex(priv_hex), None)
    return nonce.hex() + ":" + ct.hex()


def open_key(password, sealed):
    """Decrypt exchange private key. Returns hex or None."""
    if not sealed:
        return None
    nonce_hex, ct_hex = sealed.split(":", 1)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), _KDF_SALT, PBKDF2_ITER)
    return AESGCM(key).decrypt(bytes.fromhex(nonce_hex), bytes.fromhex(ct_hex), None).hex()


def encrypt_for(recipient_pub_hex, plaintext):
    """E2E envelope: ephemeral X25519 (PFS per message) + AES-256-GCM."""
    eph = X25519PrivateKey.generate()
    pub = X25519PublicKey.from_public_bytes(bytes.fromhex(recipient_pub_hex))
    shared = eph.exchange(pub)
    key = hashlib.sha256(shared).digest()
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return {"v": 1,
            "eph": eph.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
            "nonce": nonce.hex(),
            "ct": ct.hex()}


def decrypt_envelope(my_priv_hex, env):
    """Decrypt envelope with own exchange private key."""
    priv = X25519PrivateKey.from_private_bytes(bytes.fromhex(my_priv_hex))
    pub = X25519PublicKey.from_public_bytes(bytes.fromhex(env["eph"]))
    shared = priv.exchange(pub)
    key = hashlib.sha256(shared).digest()
    return AESGCM(key).decrypt(bytes.fromhex(env["nonce"]), bytes.fromhex(env["ct"]), None)
