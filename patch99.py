# patch99.py - P99: Merge-fix (P97-fix5) + NLP улучшения + EXE + GitHub
import os
import ast
import shutil
import re

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
DD = os.path.join(INEV, "network", "dead_drop.py")
PIPE = os.path.join(INEV, "nlp", "pipeline.py")
ORG = os.path.join(INEV, "organism.py")
APP = os.path.join(ROOT, "web", "app.py")

BAK = ".bak_p99"


def patch_replace(path, replacements, label, bak=BAK):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + bak
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new and new in content and (not old or old not in content):
            print("  [--] already applied")
            continue
        if old and old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:55].strip().replace(chr(10), ' '))
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:55].strip().replace(chr(10), ' '))
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if path.endswith(".py"):
            try:
                ast.parse(content)
                print("  [OK] syntax " + label)
                return True
            except SyntaxError as e:
                print("  [!!] syntax: " + str(e))
                shutil.copy2(b, path)
                print("  [--] rolled back")
                return False
    return True


# =====================================================================
# PART C: NLP улучшения
# =====================================================================

print()
print("=" * 70)
print("  PART C: NLP улучшения")
print("=" * 70)

with open(PIPE, "r", encoding="utf-8") as f:
    pcontent = f.read()

# C1: service -> relay
old_service = '''    elif ntype == "service":
        node_protocols = ["mDNS"]
    elif ntype == "isp_router":
        node_protocols = ["BGP", "OSPF"]'''

new_service = '''    elif ntype == "service":
        node_protocols = ["mDNS", "SSDP"]
    elif ntype == "isp_router":
        node_protocols = ["BGP", "OSPF"]'''

if old_service in pcontent:
    pcontent = pcontent.replace(old_service, new_service, 1)
    print("  [OK] service protocols")

# C2: f1/f2 для service - разрешить relay
old_eco = '''    else:
        f1 = {"teach": 3, "relay": 2, "capsule": 3, "route": 2, "skip": 1}
        f2 = {"teach": 3, "relay": 3, "capsule": 1, "route": 3, "skip": 4}'''

new_eco = '''    elif ntype == "service":
        # mDNS - потенциальный relay
        f1 = {"teach": 2, "relay": 4, "capsule": 2, "route": 2, "skip": 1}
        f2 = {"teach": 3, "relay": 4, "capsule": 1, "route": 3, "skip": 3}
    else:
        f1 = {"teach": 3, "relay": 2, "capsule": 3, "route": 2, "skip": 1}
        f2 = {"teach": 3, "relay": 3, "capsule": 1, "route": 3, "skip": 4}'''

if old_eco in pcontent:
    pcontent = pcontent.replace(old_eco, new_eco, 1)
    print("  [OK] service relay allowed")

# C3: route+relay synch - in spore_analyze_node
old_plan = '''        # Приоритет
        priority = ["capsule", "teach", "relay", "route", "skip"]'''

new_plan = '''        # P99: route+relay synch - если route разрешён, и relay тоже
        if "route" in candidates and "relay" not in candidates:
            candidates = _append(candidates, "relay")

        # Приоритет
        priority = ["capsule", "teach", "relay", "route", "skip"]'''

if old_plan in pcontent:
    pcontent = pcontent.replace(old_plan, new_plan, 1)
    print("  [OK] route+relay sync")

with open(PIPE, "w", encoding="utf-8") as f:
    f.write(pcontent)

try:
    ast.parse(pcontent)
    print("  [OK] syntax pipeline.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# =====================================================================
# PART B: Merge-fix (P97-fix5) - через seed discovery
# =====================================================================

print()
print("=" * 70)
print("  PART B: Merge-fix (seed discovery)")
print("=" * 70)

# B1: dead_drop - публиковать cards в feed каждые 30 сек
# Уже сделано P97-fix3b

# B2: auto-register peer при получении feed
with open(DD, "r", encoding="utf-8") as f:
    dd_content = f.read()

old_read_end = '''                        # Читаем peers
                        for p in feed.get("peers", []):
                            if p.get("node_id") and p.get("url"):
                                self.register_peer(p["node_id"], p["url"])
                except Exception:
                    pass'''

new_read_end = '''                        # Читаем peers
                        for p in feed.get("peers", []):
                            if p.get("node_id") and p.get("url"):
                                self.register_peer(p["node_id"], p["url"])
                        # P99: авто-подписка на feed от sender
                        sender = feed.get("node_id", "")
                        my_url = feed.get("my_url", "")
                        if sender and my_url and sender != self.node_id:
                            self.register_peer(sender, my_url)
                except Exception:
                    pass'''

if old_read_end in dd_content:
    dd_content = dd_content.replace(old_read_end, new_read_end, 1)
    print("  [OK] auto-subscribe in _read_feeds")

# B3: добавить my_url в feed
old_feed = '''        feed = json.dumps({
            "node_id": self.node_id,
            "ts": time.time(),
            "peers": [{"node_id": nid, "url": u} for nid, u in urls],
            "cards": cards,
        }, separators=(",", ":"))'''

new_feed = '''        feed = json.dumps({
            "node_id": self.node_id,
            "ts": time.time(),
            "my_url": self.my_url,
            "peers": [{"node_id": nid, "url": u} for nid, u in urls],
            "cards": cards,
        }, separators=(",", ":"))'''

if old_feed in dd_content:
    dd_content = dd_content.replace(old_feed, new_feed, 1)
    print("  [OK] my_url in feed")

with open(DD, "w", encoding="utf-8") as f:
    f.write(dd_content)

try:
    ast.parse(dd_content)
    print("  [OK] syntax dead_drop.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# =====================================================================
# PART A: LICENSE + .gitignore
# =====================================================================

print()
print("=" * 70)
print("  PART A: LICENSE + .gitignore")
print("=" * 70)

# LICENSE (dual)
license_text = '''# InevioNet - Dual Licensing

Copyright (c) 2026 dimon027081 (InevioNet Author). All rights reserved.

This software is offered under a DUAL-LICENSE model. You may choose ONE of:

1) GNU Affero General Public License v3.0 or later ("AGPL-3.0-or-later")
   Full text: see LICENSE-AGPL.txt
   For: open-source projects, research, non-commercial use.

2) InevioNet Commercial License v1.0
   Full text: see LICENSE-COMMERCIAL.md
   For: commercial use WITHOUT AGPL obligations.

SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-InevioNet-Commercial-1.0
'''

with open(os.path.join(ROOT, "LICENSE"), "w", encoding="utf-8") as f:
    f.write(license_text)
print("  [OK] LICENSE")

# LICENSE-COMMERCIAL.md
commercial = '''# InevioNet Commercial License v1.0

Copyright (c) 2026 dimon027081 ("Licensor")

1. GRANT. Subject to payment, Licensor grants a non-exclusive,
   non-transferable license to use, modify and deploy InevioNet for
   internal business purposes or as part of a commercial product.

2. RESTRICTIONS. You may NOT sell, rent or distribute the Software
   (modified or not) as a standalone product.

3. FEES (per year):
   Capsule    $5,000   - up to 100 nodes
   Pro        $25,000  - up to 1,000 nodes
   Enterprise $100,000 - unlimited nodes

4. NO WARRANTY. THE SOFTWARE IS PROVIDED "AS IS".

5. GOVERNING LAW. Laws of the Licensor's jurisdiction.

Contact: REPLACE_WITH_YOUR_EMAIL
'''

with open(os.path.join(ROOT, "LICENSE-COMMERCIAL.md"), "w", encoding="utf-8") as f:
    f.write(commercial)
print("  [OK] LICENSE-COMMERCIAL.md")

# .gitignore
gitignore = '''__pycache__/
*.py[cod]
*.egg-info/
build/
dist/
venv/
.venv/
.pytest_cache/
htmlcov/
.coverage

# DATA & SECRETS
data/*
!data/.gitkeep
*.key
*.pem
*.db
secrets.env
.env

# LOGS
logs/
*.log

# BACKUPS
*.bak*
_backup_*/
_archive_broken/
_transfer/
installer_output/
patch*.py
fix_*.py

# IDE
.vscode/
.idea/
Thumbs.db
.DS_Store
'''

with open(os.path.join(ROOT, ".gitignore"), "w", encoding="utf-8") as f:
    f.write(gitignore)
print("  [OK] .gitignore")

# data/.gitkeep
keep = os.path.join(ROOT, "data", ".gitkeep")
os.makedirs(os.path.dirname(keep), exist_ok=True)
open(keep, "w").close()
print("  [OK] data/.gitkeep")


print()
print("=" * 70)
print("  PATCH 99 DONE")
print("=" * 70)
print("  [OK] PART C: NLP улучшения (service->relay, route+relay sync)")
print("  [OK] PART B: Merge-fix (my_url в feed, auto-subscribe)")
print("  [OK] PART A: LICENSE + .gitignore")
print()
print("Далее:")
print("  1. Стоп + перезапуск")
print("  2. Проверка NLP: python _check_nlp_plans.py")
print("  3. Проверка merge: python _check_merge.py")
print("  4. git init + commit")
print("  5. PyInstaller")