# patch63d.py - InevioNet: P63d — endpoint /api/relay/transit
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
TARGET = os.path.join(ROOT, "web", "app.py")

with open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

if "/api/relay/transit" in content:
    print("  [--] P63d already applied")
else:
    # Якорь: конец api_relay_incoming
    anchor = """        log.error('[Relay] incoming error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/stats')"""

    repl = """        log.error('[Relay] incoming error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/relay/transit', methods=['POST'])
def api_relay_transit():
    \"\"\"P63d: register transit pheromone from relay.\"\"\"
    try:
        d = request.get_json(silent=True) or {}
        source = d.get('source', '') or ''
        destination = d.get('destination', '') or ''
        via = d.get('via', '') or ''
        path = d.get('path', []) or []
        if not source or not destination:
            return jsonify({'success': False, 'error': 'missing'}), 400
        n = get_net()
        try:
            n.mycelium.pheromones.mark_transit(
                source=source, destination=destination,
                via=via, path=path)
        except Exception as _e:
            log.debug('[Transit] mark: %s', _e)
        return jsonify({'success': True})
    except Exception as e:
        log.error('[Transit] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/relay/port')
def api_relay_port():
    \"\"\"P63d: relay listen port.\"\"\"
    try:
        n = get_net()
        port = int(os.environ.get('INEVIO_RELAY_PORT', 0))
        return jsonify({'success': True, 'port': port,
                        'running': getattr(n, 'relay', None) is not None})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/stats')"""

    if anchor in content:
        content = content.replace(anchor, repl, 1)
        print("  [OK] endpoint inserted")
    else:
        print("  [!!] anchor NOT FOUND")
        for i, line in enumerate(content.splitlines()):
            if 'api/relay/incoming' in line:
                print(f"    line {i+1}: {line!r}")

    bak = TARGET + ".bak_p63d"
    shutil.copy2(TARGET, bak)
    print(f"  [BK] {os.path.basename(bak)}")

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [OK] saved")

    try:
        ast.parse(content)
        print("  [OK] syntax")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        shutil.copy2(bak, TARGET)
        print("  [--] rolled back")

with open(TARGET, "r", encoding="utf-8") as f:
    check = f.read()
print(f"  /api/relay/transit: {'/api/relay/transit' in check}")
print(f"  /api/relay/port:    {'/api/relay/port' in check}")