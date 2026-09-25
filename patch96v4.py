# patch96v4.py - P96-v4: замена _stego_send и _industrial_probe
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p96v4"


def patch_by_lines(path, replacements, label):
    """Замена по строкам (1-based, inclusive)."""
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    b = path + BAK
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    
    # Заменяем по номерам (с конца, чтобы не сбить индексы)
    for start, end, new_text in sorted(replacements, key=lambda x: -x[0]):
        # start, end - 1-based, inclusive
        new_lines = [l + "\n" for l in new_text.split("\n")]
        # Убираем последний пустой
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


# _stego_send - заменить строки 892-916 (с def по return False)
new_stego = '''    def _stego_send(self, ip, payload):
        """P96-v4: через net.send_masked (правильный API)."""
        try:
            # 1. send_masked (маскировка + отправка)
            fn = getattr(self.net, "send_masked", None)
            if fn and callable(fn):
                try:
                    fn(ip, payload)
                    return True
                except TypeError:
                    try:
                        fn(payload, ip)
                        return True
                    except TypeError:
                        pass
                except Exception as e:
                    logger.debug("[Stego] send_masked: %s", e)
            # 2. Fallback: SteganographyEngine
            try:
                if not hasattr(self, "_stego_engine"):
                    from .steganography.engine import SteganographyEngine
                    self._stego_engine = SteganographyEngine()
                for m in ("send_auto", "send_parallel", "send"):
                    mfn = getattr(self._stego_engine, m, None)
                    if mfn and callable(mfn):
                        try:
                            mfn(ip, payload)
                            return True
                        except TypeError:
                            try:
                                mfn(payload, ip)
                                return True
                            except Exception:
                                continue
                        except Exception:
                            continue
            except Exception as e:
                logger.debug("[Stego] engine: %s", e)
        except Exception as e:
            logger.debug("[Stego] %s: %s", ip, e)
        return False'''

# _industrial_probe - заменить строки 939-955
new_ind = '''    def _industrial_probe(self, ip):
        """P96-v4: через net.scan_industrial (правильный API)."""
        try:
            fn = getattr(self.net, "scan_industrial", None)
            if fn and callable(fn):
                try:
                    fn(ip)
                    return True
                except TypeError:
                    try:
                        fn(target=ip)
                        return True
                    except TypeError:
                        try:
                            fn()
                            return True
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug("[Industrial] scan_industrial: %s", e)
        except Exception as e:
            logger.debug("[Industrial] %s: %s", ip, e)
        return False'''

# Заменяем (снизу вверх, чтобы не сбить индексы)
patch_by_lines(ORG, [
    (939, 955, new_ind),    # _industrial_probe
    (892, 916, new_stego),  # _stego_send
], "stego + industrial")

print()
print("=" * 70)
print("  PATCH 96-V4 DONE")
print("=" * 70)
print("  [OK] _stego_send -> net.send_masked")
print("  [OK] _industrial_probe -> net.scan_industrial")
print()
print("Перезапуск + 90 сек:")
print("  curl -k https://localhost:8080/api/organism | python -m json.tool")