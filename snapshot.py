import os, json, time, re
from pathlib import Path
from collections import Counter

ROOT = Path(r"E:\InevioNet")
OUT = ROOT / "snapshot_py.txt"

EXCLUDE_DIRS = {
    'node_modules', '.git', 'bin', 'obj', 'dist', 'build',
    '__pycache__', '.venv', 'venv', 'env', '.idea', '.vscode',
    'target', 'out', 'coverage', '.next', '.cache', 'vendor',
    'tor', 'logs', 'htmlcov', '.pytest_cache',
    'InevioNet_RELEASE', 'InevioNet_v1.0.0_portable',
    'inevionet.egg-info', 'backups', 'tls',
}
EXCLUDE_PREFIX = ('_backup_', 'backup_')
EXCLUDE_EXT = {
    '.exe','.dll','.so','.dylib','.bin','.iso','.img','.zip','.tar',
    '.gz','.7z','.rar','.jar','.war','.mp3','.mp4','.avi','.mkv',
    '.mov','.jpg','.jpeg','.png','.gif','.bmp','.ico','.webp','.pdf',
    '.doc','.docx','.xls','.xlsx','.ppt','.pptx','.pyc','.pyo',
    '.class','.o','.obj','.pdb','.lock','.tmp','.temp','.swp','.swo',
    '.bak','.broken',
}
TEXT_EXT = {
    '.py','.ps1','.psm1','.psd1','.bat','.cmd','.sh','.html','.htm',
    '.css','.js','.json','.yaml','.yml','.toml','.ini','.cfg','.conf',
    '.xml','.md','.txt','.spec',
}
MAX_KB = 500

def excluded_dir(p: Path) -> bool:
    try:
        parts = p.relative_to(ROOT).parts
    except ValueError:
        return True
    for x in parts:
        if x in EXCLUDE_DIRS or x.startswith(EXCLUDE_PREFIX):
            return True
    return False

def excluded_file(p: Path) -> bool:
    if p.suffix.lower() in EXCLUDE_EXT: return True
    if p.name.startswith('snapshot_'): return True
    return False

def collect():
    files, dirs = [], []
    for dp, dns, fns in os.walk(ROOT):
        d = Path(dp)
        dns[:] = [x for x in dns if not excluded_dir(d / x)]
        if excluded_dir(d) and d != ROOT:
            continue
        dirs.append(d)
        for fn in fns:
            fp = d / fn
            if not excluded_file(fp):
                files.append(fp)
    return files, dirs

def sz(n):
    if n > 1024*1024: return f"{n/1024/1024:.2f} MB"
    if n > 1024: return f"{n/1024:.2f} KB"
    return f"{n} B"

def main():
    print("[*] Сканирую...")
    files, dirs = collect()
    print(f"[*] Файлов: {len(files)}, папок: {len(dirs)}")
    with open(OUT, 'w', encoding='utf-8') as out:
        def w(s=''): out.write(s + '\n')
        def sec(t): w(); w('='*100); w(f'  {t}'); w('='*100); w()
        def sub(t): w(); w(f'--- {t} ---'); w()

        sec('0. МЕТА')
        w(f'Root:      {ROOT}')
        w(f'Time:      {time.strftime("%Y-%m-%d %H:%M:%S")}')
        w(f'Files:     {len(files)}')
        w(f'Dirs:      {len(dirs)}')

        sec('1. ДЕРЕВО ПАПОК')
        for d in sorted(dirs):
            rel = d.relative_to(ROOT)
            w('  ' * len(rel.parts) + rel.name + '/')

        sec('2. СТАТИСТИКА')
        cc, cs = Counter(), Counter()
        for f in files:
            e = f.suffix.lower() or '(no ext)'
            cc[e] += 1
            cs[e] += f.stat().st_size
        w(f'{"Ext":<15} {"Count":>8} {"Size":>15}')
        w('-'*45)
        for e, c in cc.most_common(40):
            w(f'{e:<15} {c:>8} {sz(cs[e]):>15}')
        w(); w(f'TOTAL FILES: {len(files)}')
        w(f'TOTAL SIZE:  {sz(sum(f.stat().st_size for f in files))}')

        sec('3. СПИСОК ФАЙЛОВ')
        for f in sorted(files):
            st = f.stat()
            mt = time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))
            w(f'{str(f.relative_to(ROOT)):<70} {sz(st.st_size):>12} {mt:>18}')

        sec('4. ИМПОРТЫ')
        sub('Python')
        py_re = re.compile(r'^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))', re.M)
        for f in sorted(files):
            if f.suffix != '.py': continue
            try: t = f.read_text(encoding='utf-8', errors='replace')
            except: continue
            imps = sorted({(m.group(1) or m.group(2)) for m in py_re.finditer(t)})
            if imps:
                w(f'{f.relative_to(ROOT)} :')
                for i in imps: w(f'    -> {i}')

        sec('5. ВЫЗОВЫ')
        def_re = re.compile(r'^\s*(?:class|def)\s+([A-Za-z_]\w*)', re.M)
        defs_map = {}
        for f in sorted(files):
            if f.suffix != '.py': continue
            try: t = f.read_text(encoding='utf-8', errors='replace')
            except: continue
            d = sorted(set(def_re.findall(t)))
            if d: defs_map[str(f.relative_to(ROOT))] = d
        sub('Определения')
        for r, ds in defs_map.items():
            w(f'{r} :')
            for x in ds: w(f'    def/class {x}')
        sub('Использование')
        alln = set()
        for ds in defs_map.values(): alln.update(ds)
        if alln:
            rx = re.compile(r'\b(' + '|'.join(re.escape(n) for n in alln) + r')\b')
            for f in sorted(files):
                if f.suffix != '.py': continue
                try: t = f.read_text(encoding='utf-8', errors='replace')
                except: continue
                r = str(f.relative_to(ROOT))
                own = set(defs_map.get(r, []))
                used = set(rx.findall(t)) - own
                if used:
                    w(f'{r} :')
                    for u in sorted(used): w(f'    uses {u}')

        sec('6. ТОЧКИ ВХОДА')
        main_re = re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']')
        for f in sorted(files):
            if f.suffix != '.py': continue
            try: t = f.read_text(encoding='utf-8', errors='replace')
            except: continue
            if main_re.search(t): w(f'  {f.relative_to(ROOT)}')

        sec('7. data/')
        dd = ROOT / 'data'
        if dd.exists():
            for f in sorted(dd.rglob('*')):
                if not f.is_file(): continue
                w(f'{f.relative_to(ROOT)}  ({sz(f.stat().st_size)})')
                if f.suffix == '.json' and f.stat().st_size < 100*1024:
                    try:
                        j = json.loads(f.read_text(encoding='utf-8'))
                        if isinstance(j, dict): w(f'    keys: {", ".join(j.keys())}')
                        elif isinstance(j, list): w(f'    array of {len(j)}')
                    except: w('    (не JSON)')
        else: w('(нет data/)')

        sec('8. ЛОГИ')
        ld = ROOT / 'logs'
        if ld.exists():
            for f in sorted(ld.glob('*.log'), key=lambda x: x.stat().st_mtime, reverse=True):
                sub(f'{f.name}  ({sz(f.stat().st_size)})')
                try:
                    for ln in f.read_text(encoding='utf-8', errors='replace').splitlines()[-200:]:
                        w(ln)
                except: w('(ошибка)')
        else: w('(нет logs/)')

        sec('9. СОДЕРЖИМОЕ')
        cf = sorted([f for f in files if f.suffix.lower() in TEXT_EXT])
        w(f'Файлов: {len(cf)}'); w()
        for i, f in enumerate(cf, 1):
            rel = f.relative_to(ROOT)
            kb = f.stat().st_size / 1024
            sub(f'[{i}/{len(cf)}] {rel}  ({kb:.2f} KB)')
            if f.stat().st_size > MAX_KB * 1024:
                w(f'>>> БОЛЬШОЙ ({kb:.2f} KB) - первые 50 строк: <<<')
                try:
                    for ln in f.read_text(encoding='utf-8', errors='replace').splitlines()[:50]:
                        w(ln)
                except: w('(ошибка)')
            else:
                try: w(f.read_text(encoding='utf-8', errors='replace'))
                except: w('(бинарный)')
            w()

        sec('END')
        w(f'Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}')

    print()
    print('='*50)
    print(' SNAPSHOT ГОТОВ')
    print('='*50)
    print(f' File:  {OUT}')
    print(f' Size:  {sz(OUT.stat().st_size)}')
    print(f' Files: {len(files)}')
    print(f' Dirs:  {len(dirs)}')
    print('='*50)

if __name__ == '__main__':
    main()