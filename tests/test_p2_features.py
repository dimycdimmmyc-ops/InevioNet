"""Tests for P2: security (E2E/PFS, PBKDF2), outbox, groups."""
import os
import pytest
from inevionet.security import (hash_password, verify_password, make_exchange_pair,
                                seal_key, open_key, encrypt_for, decrypt_envelope)
from inevionet.messaging.outbox import Outbox


def test_pbkdf2_roundtrip():
    salt, stored = hash_password("secret123")
    ok, modern = verify_password("secret123", salt, stored)
    assert ok and modern
    bad, _ = verify_password("wrong", salt, stored)
    assert not bad


def test_legacy_upgrade_path():
    import hashlib
    salt = "aabbcc"
    legacy = hashlib.sha256(("%s:%s" % (salt, "oldpass")).encode()).hexdigest()
    ok, modern = verify_password("oldpass", salt, legacy)
    assert ok and not modern
    bad, _ = verify_password("x", salt, legacy)
    assert not bad


def test_seal_open_key():
    priv, pub = make_exchange_pair()
    sealed = seal_key("pw123", priv)
    assert open_key("pw123", sealed) == priv
    assert open_key("pw123", "") is None


def test_e2e_envelope_roundtrip():
    priv_a, pub_a = make_exchange_pair()
    priv_b, pub_b = make_exchange_pair()
    env = encrypt_for(pub_b, "привет, узел".encode("utf-8"))
    assert decrypt_envelope(priv_b, env) == "привет, узел".encode("utf-8")
    with pytest.raises(Exception):
        decrypt_envelope(priv_a, env)


def test_outbox_queue_persist(tmp_path):
    p = str(tmp_path / "outbox.json")
    ob = Outbox(p)
    item = ob.enqueue("node_x", {"v": 1, "ct": "aa"})
    assert len(ob.pending()) == 1
    ob2 = Outbox(p)
    assert len(ob2.pending()) == 1
    ob2.remove(item)
    assert Outbox(p).pending() == []


def test_groups(tmp_path):
    ob = Outbox(str(tmp_path / "g.json"))
    ob.add_group("roiy", ["alice", "bob"])
    assert ob.groups()["roiy"] == ["alice", "bob"]


def test_inbox_history(tmp_path):
    ob = Outbox(str(tmp_path / "i.json"))
    ob.push_inbox("alice", "test", True)
    assert ob.inbox()[0]["message"] == "test"
