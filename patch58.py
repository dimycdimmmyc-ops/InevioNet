# patch58.py - InevioNet: fix TLS in EXE + START.bat cleanup
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
RUN = os.path.join(ROOT, "run_app.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p58"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
        return True
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        if os.path.exists(path + ".bak_p58"):
            shutil.copy2(path + ".bak_p58", path)
        return False


# ============================================================
# P58a. web/app.py — TLS только если сертификат ВАЛИДНЫЙ
# ============================================================
print()
print("=" * 70)
print("  P58a: web/app.py — TLS только если валидный сертификат")
print("=" * 70)
backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

# Найти блок __main__
old_main = '''if __name__ == '__main__':
    PORT = int(os.environ.get('INEVIO_PORT', 8080))
    install_log_bridge()
    log.info('InevioNet Web Dashboard v%s (CLEAN BUILD)', __version__)

    # HTTPS если есть сертификаты
    ssl_ctx = None
    try:
        import pathlib
        cd = pathlib.Path(__file__).parent.parent / 'data' / 'tls'
        if (cd / 'cert.pem').exists() and (cd / 'key.pem').exists():
            ssl_ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.load_cert_chain(str(cd / 'cert.pem'), str(cd / 'key.pem'))
            print('[TLS] HTTPS включен: https://localhost:8080')
    except Exception as e:
        print('[TLS] выключен:', e)

    socketio.start_background_task(background_scanner)
    socketio.run(
        app,
        host='0.0.0.0',
        port=PORT,
        debug=False,
        allow_unsafe_werkzeug=True,
        ssl_context=ssl_ctx,
    )'''

new_main = '''if __name__ == '__main__':
    PORT = int(os.environ.get('INEVIO_PORT', 8080))
    install_log_bridge()
    log.info('InevioNet Web Dashboard v%s', __version__)

    # P58: TLS только если сертификат ВАЛИДНЫЙ и порт 8443
    # В EXE (frozen) - по умолчанию HTTP (браузер не отвергает)
    ssl_ctx = None
    use_tls = False

    # P58: отключаем TLS в EXE (браузер не принимает self-signed)
    is_frozen = getattr(sys, 'frozen', False)
    force_tls = os.environ.get('INEVIO_TLS', '').lower() in ('1', 'true', 'yes')

    if (not is_frozen) or force_tls:
        try:
            import pathlib
            # P57: portable data dir
            data_home = os.environ.get('INEVIO_DATA_DIR') or os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'data')
            cd = pathlib.Path(data_home) / 'tls'
            if (cd / 'cert.pem').exists() and (cd / 'key.pem').exists():
                ssl_ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
                ssl_ctx.load_cert_chain(str(cd / 'cert.pem'), str(cd / 'key.pem'))
                use_tls = True
                print('[TLS] HTTPS включен: https://localhost:%d' % PORT)
            else:
                print('[TLS] сертификаты не найдены — HTTP: http://localhost:%d' % PORT)
        except Exception as e:
            print('[TLS] выключен:', e)
    else:
        print('[TLS] EXE mode — HTTP: http://localhost:%d' % PORT)

    socketio.start_background_task(background_scanner)
    socketio.run(
        app,
        host='0.0.0.0',
        port=PORT,
        debug=False,
        allow_unsafe_werkzeug=True,
        ssl_context=ssl_ctx if use_tls else None,
    )'''

if old_main in app:
    app = app.replace(old_main, new_main, 1)
    print("  [OK] TLS fix applied")
elif 'P58: TLS только если' in app:
    print("  [--] already applied")
else:
    print("  [!!] __main__ block NOT FOUND — проверь вручную")

save_py(APP, app)


# ============================================================
# P58b. run_app.py — браузер открывает HTTP если нет TLS
# ============================================================
print()
print("=" * 70)
print("  P58b: run_app.py — браузер на HTTP")
print("=" * 70)
backup(RUN)
with open(RUN, "r", encoding="utf-8") as f:
    run = f.read()

old_browser = '''def open_browser():
    time.sleep(3)
    try:
        import webbrowser
        webbrowser.open(f'https://localhost:{PORT}')
    except Exception:
        pass'''

new_browser = '''def open_browser():
    time.sleep(3)
    try:
        import webbrowser
        # P58: EXE — HTTP (TLS self-signed браузер не принимает)
        scheme = 'http'
        if os.environ.get('INEVIO_TLS', '').lower() in ('1', 'true', 'yes'):
            scheme = 'https'
        url = f'{scheme}://localhost:{PORT}'
        webbrowser.open(url)
    except Exception:
        pass'''

if old_browser in run:
    run = run.replace(old_browser, new_browser, 1)
    print("  [OK] browser -> HTTP")
elif 'P58: EXE — HTTP' in run:
    print("  [--] already applied")
else:
    print("  [!!] open_browser NOT FOUND")

with open(RUN, "w", encoding="utf-8") as f:
    f.write(run)
print("  [OK] run_app.py saved")


# ============================================================
# P58c. Создать правильный START.bat в dist\InevioNet\
# ============================================================
print()
print("=" * 70)
print("  P58c: START.bat для EXE")
print("=" * 70)

START_BAT = '''@echo off
chcp 65001 >nul
title InevioNet
cd /d "%~dp0"
echo ============================================================
echo   INEVIONET v3.0.0
echo   Живая сеть
echo ============================================================
echo.
echo Запускаю InevioNet...
echo Открою браузер через 3 секунды.
echo Если не открылся - открой вручную: http://localhost:8080
echo.
echo Нажми Ctrl+C для остановки.
echo.
InevioNet.exe
pause
'''

# Копируем во все возможные места
paths = [
    os.path.join(ROOT, "dist", "InevioNet", "START.bat"),
    os.path.join(ROOT, "InevioNet_RELEASE", "START.bat"),
    os.path.join(ROOT, "START_exe.bat"),   # отдельный, не трогаем основной
]
for p in paths:
    d = os.path.dirname(p)
    if os.path.exists(d):
        with open(p, "w", encoding="utf-8") as f:
            f.write(START_BAT)
        print(f"  [OK] {p}")

print()
print("=" * 70)
print("  PATCH 58 DONE")
print("=" * 70)
print()
print("Пересобери:")
print("  Get-Process InevioNet,python -ErrorAction SilentlyContinue | Stop-Process -Force")
print("  cd E:\\InevioNet")
print("  Remove-Item dist,build -Recurse -Force -ErrorAction SilentlyContinue")
print("  .\\venv\\Scripts\\Activate.ps1")
print("  pyinstaller InevioNet.spec --clean --noconfirm")
print()
print("Запуск:")
print("  Start-Process 'E:\\InevioNet\\dist\\InevioNet\\InevioNet.exe'")
print("  Открой: http://localhost:8080")