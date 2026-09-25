import os
import ast
import shutil

ROOT = r"E:\InevioNet"
SEED = os.path.join(ROOT, "inevionet", "bootstrap", "seed.py")

with open(SEED, "r", encoding="utf-8") as f:
    content = f.read()

if "def fetch_multi" in content:
    print("  [--] P75a already applied")
else:
    # Якорь: конец метода fetch в SeedFetcher
    anchor = '''        except Exception as e:
            logger.debug("[Seed] fetch error: %s", e)
            return None'''

    new = '''        except Exception as e:
            logger.debug("[Seed] fetch error: %s", e)
            return None

    def fetch_multi(self, urls) -> "Optional[Seed]":
        """P75a: попробовать несколько URL, вернуть первый валидный."""
        for url in urls:
            seed = self.fetch(url)
            if seed:
                return seed
        return None

    def guess_urls_from_text(self, text: str):
        """P75a: вытащить все URL из текста (для Telegram)."""
        import re
        urls = re.findall(r"https?://[^\\s]+", text)
        return urls'''

    if anchor in content:
        content = content.replace(anchor, new, 1)
        print("  [OK] fetch_multi + guess_urls added")
    else:
        print("  [!!] anchor NOT FOUND")
        lines = content.splitlines()
        for i in range(max(0, len(lines)-15), len(lines)):
            print("    " + str(i+1) + ": " + repr(lines[i]))

    b = SEED + ".bak_p75a"
    shutil.copy2(SEED, b)
    print("  [BK] " + os.path.basename(b))

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
print("  fetch_multi: " + str("def fetch_multi" in check))
print("  guess_urls_from_text: " + str("def guess_urls_from_text" in check))