# patch97fix3b.py - P97-fix3b: замена _publish_feed по строкам
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
DD = os.path.join(ROOT, "inevionet", "network", "dead_drop.py")

BAK = ".bak_p97fix3b"


def patch_by_lines(path, replacements, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    b = path + BAK
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    
    # Заменяем с конца
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


# Найти точные строки
with open(DD, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Найти _publish_feed
pf_start = None
pf_end = None
for i, line in enumerate(lines):
    if "def _publish_feed" in line:
        pf_start = i + 1
        # Ищем конец - следующая def
        for j in range(i + 1, len(lines)):
            if lines[j].strip().startswith("def ") and "publish_feed" not in lines[j]:
                pf_end = j  # предыдущая строка
                break
        break

if pf_start and pf_end:
    print("  Found _publish_feed: lines {}-{}".format(pf_start, pf_end))
    
    new_feed = '''    def _publish_feed(self):
        """P97-fix3: feed с cards (URL последних карт)."""
        with self._lock:
            urls = list(self.peer_urls.items())
            cards = list(self.recent_cards)[-5:] if hasattr(self, "recent_cards") else []
        feed = json.dumps({
            "node_id": self.node_id,
            "ts": time.time(),
            "peers": [{"node_id": nid, "url": u} for nid, u in urls],
            "cards": cards,
        }, separators=(",", ":"))
        url = self._publish(feed)
        if url:
            self.my_url = url
            logger.info("[DeadDrop] my feed: %s (peers=%d, cards=%d)",
                        url[:60], len(urls), len(cards))'''
    
    patch_by_lines(DD, [(pf_start, pf_end, new_feed)], "publish_feed")
else:
    print("  [!!] _publish_feed not found")


# 2. __init__: recent_cards
with open(DD, "r", encoding="utf-8") as f:
    content = f.read()

if "recent_cards" not in content:
    old_init = '''        # Мой публичный drop URL
        self.my_url: str = ""
        # Уже прочитанные сообщения
        self._seen_ids: set = set()'''
    
    new_init = '''        # Мой публичный drop URL
        self.my_url: str = ""
        # P97-fix3: последние карты для feed
        self.recent_cards = deque(maxlen=10)
        # Уже прочитанные сообщения
        self._seen_ids: set = set()'''
    
    if old_init in content:
        content = content.replace(old_init, new_init, 1)
        with open(DD, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            ast.parse(content)
            print("  [OK] recent_cards in __init__")
        except SyntaxError as e:
            print("  [!!] syntax: " + str(e))
    else:
        print("  [!!] __init__ anchor not found")
else:
    print("  [--] recent_cards already exists")


# 3. _publish_outbox: запоминает URL
with open(DD, "r", encoding="utf-8") as f:
    content = f.read()

if "recent_cards.append" not in content:
    old_out = '''                if url:
                    self._stats["sent"] += 1
                    logger.info("[DeadDrop] sent %s -> %s at %s",
                                msg.sender, msg.receiver, url[:60])'''
    
    new_out = '''                if url:
                    self._stats["sent"] += 1
                    # P97-fix3: запомнить URL карты
                    try:
                        with self._lock:
                            self.recent_cards.append(url)
                    except Exception:
                        pass
                    logger.info("[DeadDrop] sent %s -> %s at %s",
                                msg.sender, msg.receiver, url[:60])'''
    
    if old_out in content:
        content = content.replace(old_out, new_out, 1)
        with open(DD, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            ast.parse(content)
            print("  [OK] _publish_outbox remembers URL")
        except SyntaxError as e:
            print("  [!!] syntax: " + str(e))
    else:
        print("  [!!] _publish_outbox anchor not found")
else:
    print("  [--] recent_cards.append already exists")


# 4. _read_feeds: читает cards из feed
with open(DD, "r", encoding="utf-8") as f:
    content = f.read()

if 'feed.get("cards"' not in content:
    old_read = '''                # Или как feed
                try:
                    feed = json.loads(text)
                    if isinstance(feed, dict) and "peers" in feed:
                        for p in feed["peers"]:
                            if p.get("node_id") and p.get("url"):
                                self.register_peer(p["node_id"], p["url"])
                except Exception:
                    pass'''
    
    new_read = '''                # Или как feed
                try:
                    feed = json.loads(text)
                    if isinstance(feed, dict):
                        # P97-fix3: читаем cards
                        for card_url in feed.get("cards", []):
                            if card_url and card_url not in self._seen_ids:
                                self._seen_ids.add(card_url)
                                card_text = self._fetch(card_url)
                                if card_text:
                                    card_msg = DropMessage.from_text(card_text)
                                    if card_msg and card_msg.verify():
                                        if (card_msg.receiver == self.node_id or
                                                card_msg.receiver == "broadcast"):
                                            self._handle_message(card_msg)
                                            continue
                        # Читаем peers
                        for p in feed.get("peers", []):
                            if p.get("node_id") and p.get("url"):
                                self.register_peer(p["node_id"], p["url"])
                except Exception:
                    pass'''
    
    if old_read in content:
        content = content.replace(old_read, new_read, 1)
        with open(DD, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            ast.parse(content)
            print("  [OK] _read_feeds reads cards")
        except SyntaxError as e:
            print("  [!!] syntax: " + str(e))
    else:
        print("  [!!] _read_feeds anchor not found")
else:
    print("  [--] _read_feeds already reads cards")


# 5. import deque
with open(DD, "r", encoding="utf-8") as f:
    content = f.read()

if "from collections import deque" not in content:
    if "import threading" in content:
        content = content.replace(
            "import threading",
            "import threading\nfrom collections import deque",
            1)
        with open(DD, "w", encoding="utf-8") as f:
            f.write(content)
        print("  [OK] import deque")


print()
print("=" * 70)
print("  PATCH 97-FIX3B DONE")
print("=" * 70)
print()
print("Проверка:")
print("  Select-String -Path 'E:\\InevioNet\\inevionet\\network\\dead_drop.py' -Pattern 'recent_cards|cards' | Select-Object LineNumber, Line")