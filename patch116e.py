import os
import ast
import shutil
import re

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")

with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

b = APP + ".bak_p116e"
shutil.copy2(APP, b)
print("  [BK] " + os.path.basename(b))

# Найти функцию api_dht_bootstrap целиком
pattern = re.compile(
    r"@app\.route\('/api/dht/bootstrap'.*?\n(?=@app\.route|\Z)",
    re.DOTALL
)
m = pattern.search(content)
if not m:
    print("  [!!] api_dht_bootstrap not found")
    exit(1)

new_func = '''@app.route('/api/dht/bootstrap', methods=['POST'])
def api_dht_bootstrap():
    """P116e: добавить peer + зарегистрировать в dead_drop + publish map."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        peer_json = d.get("json", "")
        peer_dict = d.get("peer", {})
        
        log.info("[P116e] bootstrap START: json_len=%d, dict=%s",
                 len(peer_json) if peer_json else 0,
                 bool(peer_dict))
        
        if not getattr(n, "dht_bootstrap", None):
            return jsonify({"success": False, "error": "no_dht"})
        
        added = False
        parsed = {}
        
        if peer_json:
            # Парсим строку JSON
            try:
                if isinstance(peer_json, str):
                    parsed = json.loads(peer_json)
                elif isinstance(peer_json, dict):
                    parsed = peer_json
            except Exception as _je:
                log.warning("[P116e] json parse fail: %s", _je)
                parsed = {}
            added = n.dht_bootstrap.add_peer_json(peer_json) if isinstance(peer_json, str) else False
        elif peer_dict:
            parsed = peer_dict
            added = n.dht_bootstrap.add_peer_dict(peer_dict)
        
        log.info("[P116e] parsed keys: %s", list(parsed.keys()) if parsed else [])
        
        if parsed:
            node_id = parsed.get("node_id", "")
            dd_url = parsed.get("dead_drop_url", "")
            log.info("[P116e] node=%s dd_url=%s", node_id, dd_url[:60] if dd_url else "EMPTY")
            
            # Регистрируем в dead_drop
            _dd = getattr(n, "dead_drop", None)
            if _dd is None:
                log.error("[P116e] dead_drop is NONE")
            elif not hasattr(_dd, "register_peer"):
                log.error("[P116e] no register_peer method")
            elif node_id and dd_url:
                try:
                    _before = len(getattr(_dd, "peer_urls", {}))
                    _dd.register_peer(node_id, dd_url)
                    _after = len(getattr(_dd, "peer_urls", {}))
                    log.info("[P116e] registered: peers %d -> %d", _before, _after)
                except Exception as _re:
                    import traceback
                    log.error("[P116e] register fail: %s\\n%s", _re, traceback.format_exc())
            else:
                log.warning("[P116e] node_id=%s dd_url=%s — SKIP", node_id, dd_url)
            
            # P116c: publish map
            if getattr(n, "organism", None):
                try:
                    n.organism._publish_map_to_dead_drop()
                    log.info("[P116e] map published")
                except Exception as _pe:
                    log.debug("[P116e] publish: %s", _pe)
            
            # trusted_hosts
            pub_ip = parsed.get("public_ip", "")
            pub_port = parsed.get("public_port", 0)
            if node_id and pub_ip and pub_port:
                try:
                    n.trusted_hosts.add("%s:%d" % (pub_ip, int(pub_port)),
                                        label=node_id, method="dht")
                except Exception:
                    pass
        
        # Debug-ответ
        _dd_peers = 0
        if getattr(n, "dead_drop", None):
            _dd_peers = len(getattr(n.dead_drop, "peer_urls", {}))
        
        return jsonify({
            "success": True,
            "added": added,
            "peers": n.dht_bootstrap.get_peers_count(),
            "deaddrop_peers": _dd_peers,
        })
    except Exception as e:
        import traceback
        log.error("[P116e] outer: %s\\n%s", e, traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


'''

content = content[:m.start()] + new_func + content[m.end():]

with open(APP, "w", encoding="utf-8") as f:
    f.write(content)

try:
    ast.parse(content)
    print("  [OK] api_dht_bootstrap заменён (P116e)")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))
    shutil.copy2(b, APP)
    print("  [--] rolled back")