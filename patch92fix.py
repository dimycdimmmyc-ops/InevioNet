# patch92fix.py - P92-fix: INFO-логи + force endpoint + fallback
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
ORCH = os.path.join(INEV, "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")

BAK = ".bak_p92fix"


def patch_file(path, replacements, label, bak=BAK):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + bak
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new and new in content and (not old or old not in content):
            print("  [--] already applied")
            continue
        if old and old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:55].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:55].strip())
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if path.endswith(".py"):
            try:
                ast.parse(content)
                print("  [OK] syntax " + label)
                return True
            except SyntaxError as e:
                print("  [!!] syntax: " + str(e))
                shutil.copy2(b, path)
                print("  [--] rolled back")
                return False
        else:
            print("  [OK] saved " + label)
            return True
    return True


# =====================================================================
# 1. orchestrator: P92-блок -> INFO-логи + fallback
# =====================================================================

print()
print("=" * 70)
print("  1. orchestrator: P92 INFO-логи + fallback")
print("=" * 70)

old_p92 = '''                    # P92: профиль сети -> analyzer + spores
                    try:
                        from .masking.network_profile import build_network_profile
                        _prof = build_network_profile(
                            local_map=local,
                            hops=tr_result.get("hops", []),
                            mdns_devices=mdns_result.get("devices", []),
                        )
                        _am = getattr(self, "_ambient_masker", None)
                        if _am is None:
                            # создать лениво
                            try:
                                self._ambient_masker = self._enable_ambient_masking_impl()
                                _am = self._ambient_masker
                            except Exception:
                                _am = None
                        if _am is not None:
                            _am.adapt_to_network(_prof)
                        # P92b: профиль в споры
                        try:
                            _sm = getattr(getattr(self, "mycelium", None), "spores", None)
                            if _sm is not None and hasattr(_sm, "set_profile_all"):
                                _n = _sm.set_profile_all(_prof)
                                if _n:
                                    logger.info("[P92b] profile -> %d spores (%s)",
                                                _n, _prof.get("network_type"))
                        except Exception as _se:
                            logger.debug("[P92b] %s", _se)
                    except Exception as _pe:
                        logger.debug("[P92] %s", _pe)'''

new_p92 = '''                    # P92: профиль сети -> analyzer + spores
                    try:
                        from .masking.network_profile import build_network_profile
                        _prof = build_network_profile(
                            local_map=local,
                            hops=tr_result.get("hops", []),
                            mdns_devices=mdns_result.get("devices", []),
                        )
                        logger.info("[P92] profile built: type=%s dev=%d routers=%d",
                                    _prof.get("network_type"),
                                    _prof.get("total_devices", 0),
                                    _prof.get("unique_routers", 0))
                        # Получить/создать ambient masker
                        _am = getattr(self, "_ambient_masker", None)
                        if _am is None:
                            try:
                                _am = self._enable_ambient_masking_impl()
                                self._ambient_masker = _am
                                logger.info("[P92] _ambient_masker created via impl")
                            except Exception as _ce:
                                logger.warning("[P92] impl failed: %s -> direct", _ce)
                                try:
                                    from .masking.ambient import AmbientMasker
                                    _am = AmbientMasker(adaptation_strength=0.7)
                                    self._ambient_masker = _am
                                    logger.info("[P92] _ambient_masker created direct")
                                except Exception as _de:
                                    logger.error("[P92] direct create failed: %s", _de)
                                    _am = None
                        if _am is not None:
                            try:
                                _ok = _am.adapt_to_network(_prof)
                                logger.info("[P92d] adapt_to_network -> %s", _ok)
                            except Exception as _ae:
                                logger.warning("[P92d] adapt failed: %s", _ae)
                        # P92b: профиль в споры
                        try:
                            _sm = getattr(getattr(self, "mycelium", None), "spores", None)
                            if _sm is not None and hasattr(_sm, "set_profile_all"):
                                _n = _sm.set_profile_all(_prof)
                                logger.info("[P92b] profile -> %d spores (%s)",
                                            _n, _prof.get("network_type"))
                            else:
                                logger.debug("[P92b] no spores manager")
                        except Exception as _se:
                            logger.warning("[P92b] %s", _se)
                    except Exception as _pe:
                        logger.warning("[P92] outer error: %s", _pe)'''

patch_file(ORCH, [(old_p92, new_p92, True)], "orchestrator P92 INFO+fallback")


# =====================================================================
# 2. orchestrator: P92d INFO-логи
# =====================================================================

print()
print("=" * 70)
print("  2. orchestrator: P92d INFO")
print("=" * 70)

old_p92d = '''                # P92d: периодически перечитывать профиль сети и адаптировать маскировку
                try:
                    _am = getattr(self, "_ambient_masker", None)
                    if _am is not None:
                        _p = _am.get_network_profile()
                        if not _p:
                            # попробовать у спор
                            _sm = getattr(getattr(self, "mycelium", None), "spores", None)
                            if _sm is not None and hasattr(_sm, "get_any_profile"):
                                _p = _sm.get_any_profile()
                        if _p:
                            _am.adapt_to_network(_p)
                except Exception as _ae:
                    logger.debug("[P92d] %s", _ae)'''

new_p92d = '''                # P92d: периодически перечитывать профиль сети и адаптировать маскировку
                try:
                    _am = getattr(self, "_ambient_masker", None)
                    if _am is not None:
                        _p = _am.get_network_profile()
                        if not _p:
                            _sm = getattr(getattr(self, "mycelium", None), "spores", None)
                            if _sm is not None and hasattr(_sm, "get_any_profile"):
                                _p = _sm.get_any_profile()
                        if _p:
                            _am.adapt_to_network(_p)
                            logger.debug("[P92d] re-adapt: %s", _p.get("network_type"))
                except Exception as _ae:
                    logger.debug("[P92d] %s", _ae)'''

patch_file(ORCH, [(old_p92d, new_p92d, True)], "orchestrator P92d INFO")


# =====================================================================
# 3. app.py: force endpoint
# =====================================================================

print()
print("=" * 70)
print("  3. app.py: /api/network/profile/force")
print("=" * 70)

anchor = "@app.route('/api/network/public')"

force_ep = '''@app.route('/api/network/profile/force', methods=['POST', 'GET'])
def api_network_profile_force():
    """P92-fix: принудительно собрать профиль сети и применить."""
    try:
        n = get_net()
        out = {"success": True, "steps": []}

        # 1. Собрать данные
        local = {}
        try:
            if getattr(n, "local_map", None):
                local = n.local_map.build() or {}
            out["steps"].append("local_map: %d devices" % len(local.get("devices", [])))
        except Exception as e:
            out["steps"].append("local_map FAIL: %s" % e)

        hops = []
        try:
            if getattr(n, "traceroute_scan", None):
                tr = n.traceroute_scan.scan_multi() or {}
                hops = tr.get("hops", [])
            out["steps"].append("traceroute: %d hops" % len(hops))
        except Exception as e:
            out["steps"].append("traceroute FAIL: %s" % e)

        mdns = []
        try:
            if getattr(n, "local_discovery", None):
                md = n.local_discovery.scan_all(timeout=2.0) or {}
                mdns = md.get("devices", [])
            out["steps"].append("mdns: %d devices" % len(mdns))
        except Exception as e:
            out["steps"].append("mdns FAIL: %s" % e)

        # 2. Построить профиль
        prof = {}
        try:
            from inevionet.masking.network_profile import build_network_profile
            prof = build_network_profile(
                local_map=local, hops=hops, mdns_devices=mdns)
            out["profile"] = prof
            out["steps"].append("profile: type=%s" % prof.get("network_type"))
        except Exception as e:
            out["steps"].append("profile FAIL: %s" % e)
            return jsonify(out), 500

        # 3. Создать/получить masker
        am = getattr(n, "_ambient_masker", None)
        if am is None:
            try:
                am = n._enable_ambient_masking_impl()
                n._ambient_masker = am
                out["steps"].append("masker: created via impl")
            except Exception as e:
                try:
                    from inevionet.masking.ambient import AmbientMasker
                    am = AmbientMasker(adaptation_strength=0.7)
                    n._ambient_masker = am
                    out["steps"].append("masker: created direct (%s)" % e)
                except Exception as e2:
                    out["steps"].append("masker FAIL: %s / %s" % (e, e2))
                    am = None

        # 4. Применить
        if am is not None:
            try:
                ok = am.adapt_to_network(prof)
                out["steps"].append("adapt_to_network -> %s" % ok)
            except Exception as e:
                out["steps"].append("adapt FAIL: %s" % e)

        # 5. В споры
        try:
            sm = getattr(getattr(n, "mycelium", None), "spores", None)
            if sm is not None and hasattr(sm, "set_profile_all"):
                cnt = sm.set_profile_all(prof)
                out["steps"].append("spores -> %d" % cnt)
        except Exception as e:
            out["steps"].append("spores FAIL: %s" % e)

        # 6. Итог
        if am is not None:
            out["masker"] = {
                "network_type": am.get_network_type() if hasattr(am, "get_network_type") else "unknown",
                "profile": am.get_network_profile() if hasattr(am, "get_network_profile") else {},
                "strength": getattr(am, "adaptation_strength", None),
            }
        return jsonify(out)
    except Exception as e:
        log.error('[P92-fix] force: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/public')'''

patch_file(APP, [(anchor, force_ep, True)], "app.py force endpoint")


print()
print("=" * 70)
print("  PATCH 92 FIX DONE")
print("=" * 70)
print("  [OK] orchestrator: P92 INFO-логи + fallback")
print("  [OK] orchestrator: P92d INFO-логи")
print("  [OK] app.py: POST/GET /api/network/profile/force")
print()
print("Перезапуск: python -m web.app")
print()
print("Проверка:")
print("  curl.exe -s -k -X POST https://localhost:8080/api/network/profile/force")
print("  curl.exe -s -k https://localhost:8080/api/network/profile")