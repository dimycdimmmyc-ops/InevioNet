# patch66c.py - InevioNet: P66c — UI block with public IP
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
TARGET = os.path.join(ROOT, "web", "templates", "index.html")

with open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

if "public-addr-box" in content:
    print("  [--] P66c already applied")
else:
    changed = 0

    # 1) CSS — после .dot.on
    css_anchor = ".dot.on { background:var(--green); box-shadow:0 0 10px var(--green); }"
    css_new = (".dot.on { background:var(--green); box-shadow:0 0 10px var(--green); }\n"
               ".public-addr {\n"
               "  display:flex; align-items:center; justify-content:center;\n"
               "  gap:6px; margin-top:8px; padding:6px 10px;\n"
               "  background:rgba(10,132,255,0.12);\n"
               "  border-radius:8px; font-size:0.78em;\n"
               "  color:var(--dim);\n"
               "  border:0.5px solid rgba(10,132,255,0.3);\n"
               "}\n"
               ".public-addr .addr { color:var(--blue); font-weight:600; font-family:monospace; }\n"
               ".public-addr .nat-cone { color:var(--green); }\n"
               ".public-addr .nat-sym { color:var(--orange); }")

    if css_anchor in content:
        content = content.replace(css_anchor, css_new, 1)
        print("  [OK] CSS inserted")
        changed += 1
    else:
        print("  [!!] CSS anchor NOT FOUND")

    # 2) HTML — после закрывающего div status-bar
    html_anchor = '<div class="dot" id="status-dot"></div>'
    html_new = ('<div class="dot" id="status-dot"></div>\n'
                '  </div>\n'
                '  <div class="public-addr" id="public-addr-box">\n'
                '    <span>public:</span>\n'
                '    <span class="addr" id="public-ip">-</span>\n'
                '    <span class="nat" id="public-nat"></span>\n'
                '  </div>\n'
                '  <div style="display:none">')

    if html_anchor in content:
        content = content.replace(html_anchor, html_new, 1)
        print("  [OK] HTML inserted")
        changed += 1
    else:
        print("  [!!] HTML anchor NOT FOUND")

    # 3) JS — добавить функцию и setInterval
    js_anchor = "setInterval("
    if js_anchor in content:
        first_js = content.find(js_anchor)
        js_new = (
            "async function updatePublicAddr() {\n"
            "  try {\n"
            "    const r = await fetch('/api/network/public');\n"
            "    const d = await r.json();\n"
            "    const ipEl = document.getElementById('public-ip');\n"
            "    const natEl = document.getElementById('public-nat');\n"
            "    if (!ipEl) return;\n"
            "    if (d && d.success) {\n"
            "      ipEl.textContent = d.public_ip + ':' + d.public_port;\n"
            "      natEl.textContent = '(' + d.nat_type + ')';\n"
            "      natEl.className = 'nat ' + (d.nat_type === 'cone' ? 'nat-cone' : 'nat-sym');\n"
            "    } else {\n"
            "      ipEl.textContent = '...';\n"
            "      natEl.textContent = '';\n"
            "    }\n"
            "  } catch(e) {}\n"
            "}\n"
            "updatePublicAddr();\n"
            "setInterval(updatePublicAddr, 30000);\n\n"
            + content[first_js:])
        content = content[:first_js] + js_new
        print("  [OK] JS inserted")
        changed += 1
    else:
        print("  [!!] JS anchor NOT FOUND")

    if changed > 0:
        bak = TARGET + ".bak_p66c"
        shutil.copy2(TARGET, bak)
        print("  [BK] " + os.path.basename(bak))
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(content)
        print("  [OK] saved")

with open(TARGET, "r", encoding="utf-8") as f:
    check = f.read()
print("  public-addr-box: " + str("public-addr-box" in check))
print("  updatePublicAddr: " + str("updatePublicAddr" in check))