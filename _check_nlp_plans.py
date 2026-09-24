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
print("Sample nodes with NLP plans (%d shown):" % len(nodes))
print()
print("%-20s %-15s %-10s %-6s %-8s" % ("IP", "TYPE", "PLAN", "CONF", "LEADING"))
print("-" * 65)
for item in nodes[:20]:
    ip = item[0]
    node = item[1]
    plan = node.get("nlp_plan", "?")
    conf = node.get("nlp_confidence", 0)
    leading = node.get("nlp_leading", "?")
    ntype = node.get("type", "?")
    print("%-20s %-15s %-10s %-6.2f %-8s" % (ip, ntype, plan, conf, leading))

# Статистика планов
stats = d.get("stats", {})
print()
print("=== STATS ===")
print("cycles:", stats.get("cycles"))
print("nodes_found:", stats.get("nodes_found"))
print("nodes_taught:", stats.get("nodes_taught"))
print("nodes_relayed:", stats.get("nodes_relayed"))
print("nodes_capsuled:", stats.get("nodes_capsuled"))
print("max_depth:", stats.get("max_depth"))