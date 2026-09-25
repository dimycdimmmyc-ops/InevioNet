# patch21.py - detailed deploy_all results + allow localhost
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
CAPSULE = os.path.join(ROOT, "inevionet", "mycelium", "capsule.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def backup(path):
    shutil.copy2(path, path + ".bak_p21")
    print(f"  Backup: {os.path.basename(path)}.bak_p21")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        shutil.copy2(path + ".bak_p21", path)
        sys.exit(1)


def save_raw(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  [OK] saved: {os.path.basename(path)}")


# ============================================================
# 1. capsule.py: allow 127.0.0.1 in trusted (for local test)
# ============================================================
print("=" * 70)
print("  PATCH 21a: allow 127.0.0.1 (local test)")
print("=" * 70)

backup(CAPSULE)
with open(CAPSULE, "r", encoding="utf-8") as f:
    cap = f.read()

if "P21: allow localhost" in cap:
    print("  [--] already patched")
else:
    old = '''        host_ip = host.split(":")[0]
        my_ips = {"127.0.0.1", "localhost", "0.0.0.0"}
        try:
            import socket as _s
            for info in _s.getaddrinfo(_s.gethostname(), None):
                my_ips.add(info[4][0])
        except Exception:
            pass
        if host_ip in my_ips:
            logger.warning("[Trusted] skip self: %s", host)
            return False'''
    new = '''        host_ip = host.split(":")[0]
        # P21: allow localhost (127.0.0.1, localhost) for local testing
        if host_ip in ("127.0.0.1", "localhost"):
            pass  # allowed
        else:
            my_ips = set()
            try:
                import socket as _s
                for info in _s.getaddrinfo(_s.gethostname(), None):
                    my_ips.add(info[4][0])
            except Exception:
                pass
            if host_ip in my_ips:
                logger.warning("[Trusted] skip self: %s", host)
                return False'''
    if old in cap:
        cap = cap.replace(old, new, 1)
        print("  [OK] allow 127.0.0.1 in trusted")
    else:
        print("  [!!] skip self pattern not found")

save_py(CAPSULE, cap)


# ============================================================
# 2. app.py: detailed deploy_all results
# ============================================================
print()
print("=" * 70)
print("  PATCH 21b: detailed deploy_all results")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

if "skip_reason" in app:
    print("  [--] detailed results exist")
else:
    # Replace the results.append sections
    old_skip = '''            # Skip self
            if ntype == 'self':
                continue

            # Skip no-OS nodes
            if ntype in no_os_types:
                skipped_count += 1
                continue

            # Skip unknown IP
            if not ip or ip == 'unknown':
                skipped_count += 1
                continue'''
    new_skip = '''            # Skip self
            if ntype == 'self':
                results.append({
                    'node_id': nid, 'type': ntype,
                    'status': 'skip', 'skip_reason': 'self',
                })
                skipped_count += 1
                continue

            # Skip no-OS nodes
            if ntype in no_os_types:
                results.append({
                    'node_id': nid, 'type': ntype,
                    'status': 'skip', 'skip_reason': 'no_os',
                })
                skipped_count += 1
                continue

            # Skip unknown IP
            if not ip or ip == 'unknown':
                results.append({
                    'node_id': nid, 'type': ntype,
                    'status': 'skip', 'skip_reason': 'no_ip',
                })
                skipped_count += 1
                continue'''
    if old_skip in app:
        app = app.replace(old_skip, new_skip, 1)
        print("  [OK] detailed skip reasons")
    else:
        print("  [!!] skip pattern not found")

    save_py(APP, app)


# ============================================================
# 3. index.html: color-coded results
# ============================================================
print()
print("=" * 70)
print("  PATCH 21c: color-coded results in UI")
print("=" * 70)

backup(HTML)
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()

if "deploy-results" in html:
    print("  [--] deploy-results style exists")
else:
    # Add CSS
    css = '''<style>
.deploy-result {
    padding: 4px 8px;
    margin: 2px 0;
    border-radius: 4px;
    font-size: 0.8em;
    font-family: monospace;
}
.deploy-result.deployed { background: rgba(48,209,88,0.15); color: var(--green); }
.deploy-result.failed { background: rgba(255,69,58,0.15); color: var(--red); }
.deploy-result.skip { background: rgba(120,120,128,0.15); color: var(--dim); }
</style>'''
    if "</head>" in html:
        html = html.replace("</head>", css + "\n</head>", 1)
        print("  [OK] CSS added")

    # Update JS
    old_js = '''                let out = '<div style="margin-top:10px">';
                out += '<b>Результаты:</b><br>';
                for (const res of (d.results || [])) {
                    const icon = res.status === 'deployed' ? '✅' :
                                 res.status === 'failed' ? '❌' : '⚠️';
                    out += icon + ' ' + res.type + ' @ ' + res.target + '<br>';
                }
                out += '</div>';
                el.innerHTML = out + el.innerHTML;'''
    new_js = '''                let out = '<div style="margin-top:10px">';
                out += '<b>Результаты (' + (d.results || []).length + '):</b><br>';
                const sorted = (d.results || []).sort((a, b) => {
                    const order = {deployed: 0, failed: 1, skip: 2};
                    return (order[a.status] || 9) - (order[b.status] || 9);
                });
                for (const res of sorted) {
                    const cls = res.status === 'deployed' ? 'deployed' :
                                res.status === 'failed' ? 'failed' : 'skip';
                    const icon = res.status === 'deployed' ? '✅' :
                                 res.status === 'failed' ? '❌' : '⚠️';
                    const reason = res.skip_reason ? ' (' + res.skip_reason + ')' : '';
                    out += '<div class="deploy-result ' + cls + '">' +
                           icon + ' ' + (res.type || '?') +
                           ' @ ' + (res.target || 'unknown') +
                           reason + '</div>';
                }
                out += '</div>';
                el.innerHTML = out + el.innerHTML;'''
    if old_js in html:
        html = html.replace(old_js, new_js, 1)
        print("  [OK] JS updated (colored results)")

    save_raw(HTML, html)


print()
print("=" * 70)
print("  PATCH 21 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] 127.0.0.1 разрешён в trusted (для локального теста)")
print("  [OK] deploy_all показывает причины skip")
print("  [OK] UI: цветные результаты")
print()
print("Перезапусти сервер: python -m web.app")