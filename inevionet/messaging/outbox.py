"""InevioNet Messaging - outbox (store-and-forward) and groups."""
import json
import os
import threading
import time
import uuid


class Outbox:
    """Persistent store-and-forward queue + group registry."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.data = {"queue": [], "groups": {}, "inbox": []}
        self.load()

    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data.update(json.load(f))
        except Exception:
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
        except Exception:
            pass

    def enqueue(self, recipient, envelope):
        item = {"id": uuid.uuid4().hex, "recipient": recipient,
                "envelope": envelope, "ts": time.time()}
        with self.lock:
            self.data["queue"].append(item)
            self.save()
        return item

    def pending(self):
        with self.lock:
            return list(self.data["queue"])

    def remove(self, item):
        with self.lock:
            self.data["queue"] = [i for i in self.data["queue"] if i["id"] != item["id"]]
            self.save()

    def push_inbox(self, sender, message, secure):
        with self.lock:
            self.data["inbox"].append({"sender": sender, "message": message,
                                       "secure": bool(secure), "ts": time.time()})
            self.data["inbox"] = self.data["inbox"][-100:]
            self.save()

    def inbox(self):
        with self.lock:
            return list(self.data["inbox"])

    def add_group(self, name, members):
        with self.lock:
            self.data["groups"][name] = list(members)
            self.save()

    def groups(self):
        with self.lock:
            return dict(self.data["groups"])
