import re, subprocess, sys, pathlib

ROOT = pathlib.Path(r'C:\T18')
PATTERNS = [
    re.compile(r'NOTION_TOKEN\s*=\s*[^<\s][^\r\n]+', re.I),
    re.compile(r'DHAN_(API_KEY|ACCESS_TOKEN)\s*=\s*[^<\s][^\r\n]+', re.I),
    re.compile(r'TELEGRAM_BOT_TOKEN\s*=\s*[^<\s][^\r\n]+', re.I),
]
ALLOW = {'.env', '.env.local', '.env.local.backup'}  # these are ignored by git anyway

def staged_files():
    out = subprocess.check_output(['git','diff','--cached','--name-only'], cwd=ROOT, text=True)
    return [f for f in out.splitlines() if f.strip()]

def scan(paths):
    bad = []
    for rel in paths:
        p = ROOT / rel
        if not p.exists() or p.name in ALLOW:
            continue
        if p.suffix.lower() in {'.png','.jpg','.jpeg','.ico','.pdf','.parquet','.db'}:
            continue
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for pat in PATTERNS:
            m = pat.search(text)
            if m:
                bad.append((rel, m.group(0)[:80]))
                break
    return bad

def main():
    files = staged_files()
    offenders = scan(files)
    if offenders:
        print('❌ Secret-like strings found in staged files:')
        for f, snippet in offenders:
            print(' -', f, '->', snippet)
        print('\nFix: remove secrets or unstage those files, then commit again.')
        sys.exit(1)
    print('✅ No obvious secrets in staged files.')
    sys.exit(0)

if __name__ == '__main__':
    main()
