import json
import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for name, url in [("PC-A (8080)", "https://localhost:8080/api/organism"),
                  ("PC-A2 (8081)", "https://localhost:8081/api/organism")]:
    print("=== %s ===" % name)
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            d = json.loads(r.read())
        s = d.get("stats", {})
        m = d.get("memory", {})
        print("  maps_merged:", s.get("maps_merged"))
        print("  nodes_from_merge:", s.get("nodes_from_merge"))
        print("  nodes_found:", s.get("nodes_found"))
        print("  nodes_count:", m.get("nodes_count"))
    except Exception as e:
        print("  ERROR:", e)