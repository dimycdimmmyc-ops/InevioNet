import os
import ast
import shutil
import re

ROOT = r"E:\InevioNet"
DD = os.path.join(ROOT, "inevionet", "network", "dead_drop.py")

with open(DD, "r", encoding="utf-8") as f:
    content = f.read()

b = DD + ".bak_p117"
shutil.copy2(DD, b)
print("  [BK] " + os.path.basename(b))

# Найти метод _publish
pattern = re.compile(
    r"    def _publish\(self, text: str\).*?(?=\n    def |\n    # )",
    re.DOTALL
)
m = pattern.search(content)

if m:
    new_publish = '''    def _publish(self, text: str):
        """P117: публикует через ротацию paste-сервисов."""
        # P117: список сервисов (ротация)
        services = [
            ("paste.rs", self._publish_paste_rs),
            ("dpaste.com", self._publish_dpaste),
            ("termbin.com", self._publish_termbin),
            ("sprunge.us", self._publish_sprunge),
            ("ix.io", self._publish_ix_io),
        ]
        # Начинаем с последнего успешного
        last = getattr(self, "_last_paste_service", 0)
        # Пробуем все, начиная с last
        for offset in range(len(services)):
            idx = (last + offset) % len(services)
            name, fn = services[idx]
            try:
                url = fn(text)
                if url:
                    self._last_paste_service = idx
                    logger.debug("[DeadDrop] published via %s: %s", name, url[:60])
                    return url
            except Exception as e:
                logger.debug("[DeadDrop] %s failed: %s", name, e)
                continue
        logger.warning("[DeadDrop] ALL paste services failed")
        return None

    def _publish_paste_rs(self, text: str):
        """paste.rs"""
        req = urllib.request.Request(
            "https://paste.rs", data=text.encode("utf-8"),
            headers={"Content-Type": "text/plain"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status in (200, 201):
                result = r.read().decode().strip()
                if result.startswith("http"):
                    return result
                return "https://paste.rs/" + result
        return None

    def _publish_dpaste(self, text: str):
        """dpaste.com (POST form)"""
        data = urllib.parse.urlencode({
            "content": text,
            "format": "url",
            "expires": "86400",
        }).encode()
        req = urllib.request.Request(
            "https://dpaste.com/api/v2/", data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status in (200, 201):
                return r.read().decode().strip()
        return None

    def _publish_termbin(self, text: str):
        """termbin.com (netcat-style, TCP)"""
        import socket as _sock
        s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        s.settimeout(10)
        try:
            s.connect(("termbin.com", 9999))
            s.sendall(text.encode("utf-8"))
            s.shutdown(_sock.SHUT_WR)
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            result = data.decode("utf-8", errors="replace").strip()
            if result.startswith("http"):
                return result
            return None
        finally:
            s.close()

    def _publish_sprunge(self, text: str):
        """sprunge.us"""
        data = urllib.parse.urlencode({"sprunge": text}).encode()
        req = urllib.request.Request(
            "http://sprunge.us", data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 200:
                result = r.read().decode().strip()
                if result.startswith("http"):
                    return result
        return None

    def _publish_ix_io(self, text: str):
        """ix.io (POST form)"""
        data = urllib.parse.urlencode({"f:1": text}).encode()
        req = urllib.request.Request(
            "http://ix.io", data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 200:
                result = r.read().decode().strip()
                if result.startswith("http"):
                    return result
        return None
'''
    content = content[:m.start()] + new_publish + content[m.end():]
    print("  [OK] _publish → ротация 5 сервисов")
else:
    print("  [!!] _publish not found")

with open(DD, "w", encoding="utf-8") as f:
    f.write(content)

try:
    ast.parse(content)
    print("  [OK] syntax dead_drop.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))
    shutil.copy2(b, DD)
    print("  [--] rolled back")

print()
print("=" * 70)
print("  PATCH 117 DONE")
print("=" * 70)
print("  [OK] _publish с ротацией: paste.rs → dpaste → termbin → sprunge → ix.io")
print()
print("Перезапуск + тест")