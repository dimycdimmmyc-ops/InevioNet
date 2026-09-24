import sys
import json
import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request("https://localhost:8080/api/organism")
with urllib.request.urlopen(req, context=ctx) as r:
    d = json.loads(r.read())

m = d.get("memory", {})
s = d.get("stats", {})

print("=== MEMORY ===")
print("nodes_count:", m.get("nodes_count"))
print("colonized_count:", m.get("colonized_count"))
print("routes_count:", m.get("routes_count"))
print("taught_count:", m.get("taught_count"))
print()
print("=== STATS ===")
print("cycles:", s.get("cycles"))
print("nodes_found:", s.get("nodes_found"))
print("nodes_taught:", s.get("nodes_taught"))
print("nodes_relayed:", s.get("nodes_relayed"))
print("nodes_capsuled:", s.get("nodes_capsuled"))
print("stego_sent:", s.get("stego_sent"))
print("industrial_probed:", s.get("industrial_probed"))
print("maps_merged:", s.get("maps_merged"))
print("nodes_from_merge:", s.get("nodes_from_merge"))
print("max_depth:", s.get("max_depth"))
print()
print("=== NODES SAMPLE (first 15) ===")
for item in (d.get("nodes_sample") or [])[:15]:
    ip = item[0]
    node = item[1]
    t = node.get("type", "?")
    src = node.get("source", "?")
    depth = node.get("depth", "?")
    print("  %s | type=%s | src=%s | depth=%s" % (ip, t, src, depth))