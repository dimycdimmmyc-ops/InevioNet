"""Tests for cryptography module."""
import os
import pytest
from inevionet.core.crypto import (
    InevioCrypto, SymmetricCipher, KeyPair,
    generate_signing_keypair, generate_exchange_keypair,
    sign_data, verify_signature, derive_shared_secret,
    hash_data, hash_hex, hmac_sign, hmac_verify,
    random_bytes, random_hex, random_id, constant_time_compare)
from inevionet.core.exceptions import IntegrityError, CryptoError, KeyError


class TestSymmetricEncryption:
    def test_encrypt_decrypt(self, crypto):
        data = b"Hello, InevioNet!"
        encrypted = crypto.encrypt(data)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == data

    def test_encryption_different_each_time(self, crypto):
        data = b"Hello"
        e1 = crypto.encrypt(data)
        e2 = crypto.encrypt(data)
        assert e1 != e2

    def test_wrong_key_fails(self):
        c1 = InevioCrypto("password1")
        c2 = InevioCrypto("password2")
        encrypted = c1.encrypt(b"Secret")
        with pytest.raises((IntegrityError, CryptoError)):
            c2.decrypt(encrypted)

    def test_tampered_data_detected(self, crypto):
        encrypted = bytearray(crypto.encrypt(b"Secret"))
        encrypted[-1] ^= 0xFF
        with pytest.raises((IntegrityError, CryptoError)):
            crypto.decrypt(bytes(encrypted))

    def test_empty_data(self, crypto):
        encrypted = crypto.encrypt(b"")
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == b""

    def test_large_data(self, crypto):
        data = os.urandom(1024 * 1024)
        encrypted = crypto.encrypt(data)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == data

    def test_string_helpers(self, crypto):
        text = "Test message with русский"
        encrypted = crypto.encrypt_str(text)
        decrypted = crypto.decrypt_str(encrypted)
        assert decrypted == text

    def test_b64_helpers(self, crypto):
        data = b"Base64 test"
        b64 = crypto.encrypt_b64(data)
        decrypted = crypto.decrypt_b64(b64)
        assert decrypted == data


class TestAsymmetricCrypto:
    def test_signing_keypair_generation(self):
        kp = generate_signing_keypair()
        assert len(kp.private_key) == 32
        assert len(kp.public_key) == 32
        assert kp.algorithm == "Ed25519"

    def test_sign_verify(self, crypto):
        data = b"Sign this"
        signature = crypto.sign(data)
        assert crypto.verify(data, signature)
        assert not crypto.verify(b"Modified", signature)

    def test_exchange_keypair(self):
        kp = generate_exchange_keypair()
        assert len(kp.private_key) == 32
        assert len(kp.public_key) == 32
        assert kp.algorithm == "X25519"

    def test_ecdh_shared_secret(self):
        kp1 = generate_exchange_keypair()
        kp2 = generate_exchange_keypair()
        shared1 = derive_shared_secret(kp1.private_key, kp2.public_key)
        shared2 = derive_shared_secret(kp2.private_key, kp1.public_key)
        assert shared1 == shared2


class TestHashing:
    def test_hash_data(self):
        h = hash_data(b"test")
        assert len(h) == 32

    def test_hash_hex_length(self):
        h = hash_hex(b"test", length=16)
        assert len(h) == 16

    def test_hash_deterministic(self):
        assert hash_data(b"test") == hash_data(b"test")
        assert hash_data(b"test") != hash_data(b"Test")

    def test_hmac(self):
        key = random_bytes(32)
        data = b"message"
        mac = hmac_sign(key, data)
        assert hmac_verify(key, data, mac)
        assert not hmac_verify(key, b"other", mac)


class TestUtils:
    def test_random_bytes(self):
        b1 = random_bytes(32)
        b2 = random_bytes(32)
        assert len(b1) == 32
        assert b1 != b2

    def test_random_id(self):
        id1 = random_id("test", 8)
        id2 = random_id("test", 8)
        assert id1 != id2
        assert id1.startswith("test_")

    def test_constant_time_compare(self):
        a = b"test"
        b = b"test"
        c = b"Test"
        assert constant_time_compare(a, b)
        assert not constant_time_compare(a, c)


class TestKeyExport:
    def test_export_import(self):
        crypto = InevioCrypto("password")
        data = b"Test data"
        encrypted = crypto.encrypt(data)
        exported_key = crypto.export_key()
        exported_salt = crypto.export_salt()
        imported = InevioCrypto.from_export(exported_key, exported_salt)
        decrypted = imported.decrypt(encrypted)
        assert decrypted == data
