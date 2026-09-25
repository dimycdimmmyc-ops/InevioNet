# patch96v5.py - P96-v5: async industrial + skip MQTT timeout
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p96v5"


def patch_by_lines(path, replacements, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    b = path + BAK
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    
    for start, end, new_text in sorted(replacements, key=lambda x: -x[0]):
        new_lines = [l + "\n" for l in new_text.split("\n")]
        if new_lines and new_lines[-1] == "\n":
            new_lines = new_lines[:-1]
        lines[start-1:end] = new_lines
        print("  [OK] lines {}-{} -> {} lines".format(start, end, len(new_lines)))
    
    content = "".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    
    try:
        ast.parse(content)
        print("  [OK] syntax " + label)
        return True
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
        shutil.copy2(b, path)
        print("  [--] rolled back")
        return False


# Найти точные строки _industrial_probe
with open(ORG, "r", encoding="utf-8") as f:
    all_lines = f.readlines()

# Ищем def _industrial_probe
start = None
end = None
for i, line in enumerate(all_lines):
    if "def _industrial_probe" in line:
        start = i + 1  # 1-based
        # Ищем следующий def или return False на уровне метода
        for j in range(i + 1, min(i + 40, len(all_lines))):
            stripped = all_lines[j].strip()
            if stripped.startswith("def ") and not stripped.startswith("def _" + "_"):
                end = j  # предыдущая строка
                break
            if stripped == "return False" and j > i + 5:
                # это последний return False метода
                # проверим что следующая не пустая или def
                if j + 1 < len(all_lines):
                    nxt = all_lines[j + 1].strip()
                    if nxt == "" or nxt.startswith("def "):
                        end = j + 1  # включительно
                        break
        break

if start and end:
    print("  Found _industrial_probe: lines {}-{}".format(start, end))
    
    new_ind = '''    def _industrial_probe(self, ip):
        """P96-v5: быстрый probe (не ждём timeout)."""
        # Быстрая проверка портов
        try:
            import socket
            ports_open = []
            for port in (502, 1883, 4840, 20000):  # modbus, mqtt, opcua, dnp3
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                try:
                    if s.connect_ex((ip, port)) == 0:
                        ports_open.append(port)
                finally:
                    s.close()
            if not ports_open:
                return False  # нет открытых портов - не тратим время
        except Exception:
            return False
        # Если есть открытые - пробуем scan_industrial (но быстро)
        try:
            fn = getattr(self.net, "scan_industrial", None)
            if fn and callable(fn):
                try:
                    fn(ip)
                    return True
                except Exception:
                    pass
        except Exception as e:
            logger.debug("[Industrial] %s: %s", ip, e)
        return False'''
    
    patch_by_lines(ORG, [(start, end, new_ind)], "industrial fast probe")
else:
    print("  [!!] _industrial_probe not found")


print()
print("=" * 70)
print("  PATCH 96-V5 DONE")
print("=" * 70)
print("  [OK] _industrial_probe: быстрый probe (порты 502/1883/4840/20000)")
print()
print("Перезапуск + 90 сек:")
print("  curl -k https://localhost:8080/api/organism | python -m json.tool")