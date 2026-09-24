import json
import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request("https://localhost:8080/api/organism")
with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
    d = json.loads(r.read())

nodes = d.get("nodes_sample", [])
print("FULL node dump (first 3):")
for item in nodes[:3]:
    ip = item[0]
    node = item[1]
    print("=== %s ===" % ip)
    for k, v in node.items():
        if isinstance(v, (str, int, float, bool, type(None))):
            print("  %s = %r" % (k, v))
    print()