import json
import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for port in (8080, 8081):
    req = urllib.request.Request("https://localhost:%d/api/deaddrop/status" % port)
    with urllib.request.urlopen(req, context=ctx, timeout=5) as r:
        d = json.loads(r.read())
    s = d.get("stats", {})
    print("PORT %d: my_url=%s" % (port, s.get("my_url")))