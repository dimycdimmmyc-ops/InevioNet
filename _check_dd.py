import json
import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for name, port in [("PC-A (8080)", 8080), ("PC-A2 (8081)", 8081)]:
    print("=== %s ===" % name)
    try:
        # dead_drop status
        req = urllib.request.Request("https://localhost:%d/api/deaddrop/status" % port)
        with urllib.request.urlopen(req, context=ctx, timeout=5) as r:
            d = json.loads(r.read())
        s = d.get("stats", {})
        print("  deaddrop: received=%s sent=%s peers=%s inbox=%s outbox=%s" % (
            s.get("received"), s.get("sent"), s.get("peers"),
            s.get("inbox_size"), s.get("outbox_size")))
        
        # inbox содержимое
        req = urllib.request.Request("https://localhost:%d/api/deaddrop/inbox" % port)
        with urllib.request.urlopen(req, context=ctx, timeout=5) as r:
            d = json.loads(r.read())
        msgs = d.get("messages", [])
        print("  inbox messages: %d" % len(msgs))
        for m in msgs[:3]:
            print("    - from=%s to=%s size=%d" % (
                m.get("sender"), m.get("receiver"), len(str(m.get("message", "")))))
    except Exception as e:
        print("  ERROR:", e)
    print()