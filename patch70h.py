# patch70h.py - P70h: paste.rs + termbin как приоритетные
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
SEED = os.path.join(ROOT, "inevionet", "bootstrap", "seed.py")

with open(SEED, "r", encoding="utf-8") as f:
    content = f.read()

if "paste.rs" in content:
    print("  [--] P70h already applied")
else:
    # 1. Заменить порядок сервисов
    old = '''        for name, fn in [
            ("transfer.sh", self._publish_transfer),
            ("dpaste", self._publish_dpaste),
            ("ix.io", self._publish_ixio),
        ]:'''

    new = '''        for name, fn in [
            ("paste.rs", self._publish_pasters),
            ("termbin", self._publish_termbin),
            ("sprunge.us", self._publish_sprunge),
            ("transfer.sh", self._publish_transfer),
            ("dpaste", self._publish_dpaste),
            ("ix.io", self._publish_ixio),
        ]:'''

    if old in content:
        content = content.replace(old, new, 1)
        print("  [OK] service list replaced")
    else:
        print("  [!!] service list anchor NOT FOUND")

    # 2. Добавить методы перед _publish_transfer
    anchor = "    def _publish_transfer(self, text: str) -> Optional[str]:"

    new_methods = '''    def _publish_pasters(self, text: str) -> Optional[str]:
        """paste.rs - простой POST, возвращает URL."""
        import urllib.request
        req = urllib.request.Request(
            "https://paste.rs/",
            data=text.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status in (200, 201):
                return r.read().decode().strip()
        return None

    def _publish_termbin(self, text: str) -> Optional[str]:
        """termbin.com - TCP сокет порт 9999."""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect(("termbin.com", 9999))
            s.sendall(text.encode("utf-8"))
            s.shutdown(socket.SHUT_WR)
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            s.close()
            result = data.decode("utf-8", errors="replace").strip()
            if result.startswith("http"):
                return result
            if result and "/" not in result:
                return "https://termbin.com/" + result
            return result if result else None
        except Exception as e:
            import logging
            logging.debug("[Seed] termbin: %s", e)
            return None

    def _publish_sprunge(self, text: str) -> Optional[str]:
        """sprunge.us - POST form."""
        import urllib.request
        import urllib.parse
        data = urllib.parse.urlencode({"sprunge": text}).encode()
        req = urllib.request.Request(
            "http://sprunge.us",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status == 200:
                return r.read().decode().strip()
        return None

    def _publish_transfer(self, text: str) -> Optional[str]:'''

    if anchor in content:
        content = content.replace(anchor, new_methods, 1)
        print("  [OK] new methods added")
    else:
        print("  [!!] methods anchor NOT FOUND")

    # Backup
    b = SEED + ".bak_p70h"
    shutil.copy2(SEED, b)
    print("  [BK] " + os.path.basename(b))

    # Запись
    with open(SEED, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        ast.parse(content)
        print("  [OK] syntax seed.py")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
        shutil.copy2(b, SEED)
        print("  [--] rolled back")

with open(SEED, "r", encoding="utf-8") as f:
    check = f.read()
print("  paste.rs: " + str("_publish_pasters" in check))
print("  termbin: " + str("_publish_termbin" in check))
print("  sprunge: " + str("_publish_sprunge" in check))