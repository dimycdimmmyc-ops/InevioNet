import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")


def patch_file(path, replacements, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + ".bak_p70f"
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print("  [--] already applied")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:50].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:50].strip())
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            ast.parse(content)
            print("  [OK] syntax " + label)
            return True
        except SyntaxError as e:
            print("  [!!] syntax: " + str(e))
            shutil.copy2(b, path)
            print("  [--] rolled back")
            return False
    return True


print()
print("=" * 70)
print("  P70f: orchestrator.py")
print("=" * 70)

anchor1 = '        self.public_addr = None\n        self.nat_type = "unknown"'
repl1 = '''        self.public_addr = None
        self.nat_type = "unknown"

        # P70f: bootstrap + gravity
        self.seed = None
        self.sprout = None
        self.gravity = None
        try:
            from .mesh.gravity import GravityField
            self.gravity = GravityField()
            logger.info("[P70f] gravity field created")
        except Exception as _e:
            logger.debug("[P70f] gravity init: %s", _e)
        try:
            from .bootstrap import SproutEngine
            self.sprout = SproutEngine(self)
            logger.info("[P70f] sprout engine created")
        except Exception as _e:
            logger.debug("[P70f] sprout init: %s", _e)'''

anchor2 = '        # P66a: network info loop'
repl2 = '''        # P70f: запуск SproutEngine
        if getattr(self, "sprout", None):
            try:
                self.sprout.start()
                logger.info("[P70f] sprout engine started")
            except Exception as _e:
                logger.debug("[P70f] sprout start: %s", _e)

        # P66a: network info loop'''

patch_file(ORCH, [(anchor1, repl1, True), (anchor2, repl2, True)], "orchestrator.py")


print()
print("=" * 70)
print("  P70g: web/app.py")
print("=" * 70)

anchor_app = "@app.route('/api/network/public')"
repl_app = '''@app.route('/api/bootstrap/seed', methods=['GET', 'POST'])
def api_bootstrap_seed():
    """P70g: создать/опубликовать Seed."""
    try:
        from inevionet.bootstrap import Seed, SeedPublisher
        n = get_net()
        public_addr = getattr(n, "public_addr", None)
        if not public_addr:
            return jsonify({'success': False, 'error': 'no_public_addr'})
        seed = Seed(
            node_id=n.node_id,
            public_ip=public_addr[0],
            public_port=public_addr[1],
            nat_type=getattr(n, "nat_type", "unknown"),
            ttl_sec=3600,
        )
        seed.sign()
        if request.method == 'POST':
            pub = SeedPublisher()
            url = pub.publish(seed)
            if url:
                return jsonify({'success': True, 'url': url,
                                'seed': seed.to_dict(), 'text': seed.to_text()})
            return jsonify({'success': False, 'error': 'publish_failed',
                            'seed': seed.to_dict(), 'text': seed.to_text()})
        return jsonify({'success': True, 'seed': seed.to_dict(),
                        'text': seed.to_text()})
    except Exception as e:
        log.error('[Bootstrap] seed error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bootstrap/sprout', methods=['POST'])
def api_bootstrap_sprout():
    """P70g: прорастить Seed из URL или текста."""
    try:
        from inevionet.bootstrap import Seed
        d = request.get_json(silent=True) or {}
        n = get_net()
        if not getattr(n, "sprout", None):
            return jsonify({'success': False, 'error': 'no_sprout'})
        url = d.get('url', '')
        text = d.get('text', '')
        if url:
            n.sprout.add_url(url)
            return jsonify({'success': True, 'action': 'queued_url'})
        if text:
            seed = Seed.from_text(text)
            if not seed:
                return jsonify({'success': False, 'error': 'bad_text'})
            ok = n.sprout.add_seed(seed)
            return jsonify({'success': bool(ok), 'sprouted': ok,
                            'node_id': seed.node_id})
        return jsonify({'success': False, 'error': 'need_url_or_text'}), 400
    except Exception as e:
        log.error('[Bootstrap] sprout error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/gravity/field')
def api_gravity_field():
    """P70g: показать поле притяжения."""
    try:
        n = get_net()
        if not getattr(n, "gravity", None):
            return jsonify({'success': False, 'error': 'no_gravity'})
        return jsonify({'success': True, 'field': n.gravity.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bootstrap/status')
def api_bootstrap_status():
    """P70g: статус bootstrap."""
    try:
        n = get_net()
        sprout_stats = {}
        if getattr(n, "sprout", None):
            sprout_stats = n.sprout.get_stats()
        gravity_stats = {}
        if getattr(n, "gravity", None):
            gravity_stats = n.gravity.get_stats()
        return jsonify({
            'success': True,
            'sprout': sprout_stats,
            'gravity': gravity_stats,
            'public_addr': list(getattr(n, "public_addr", None) or []),
            'nat_type': getattr(n, "nat_type", "unknown"),
            'node_id': n.node_id,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/public')'''

patch_file(APP, [(anchor_app, repl_app, True)], "web/app.py")


print()
print("=" * 70)
print("  DONE")
print("=" * 70)