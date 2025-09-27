# t18_autosync.py — one-way (local -> remote) push-only autosync
# Runs completely hidden when launched via pythonw.exe
import os, sys, time, subprocess, traceback, hashlib, threading
from pathlib import Path

ROOT       = Path(r"C:\T18").resolve()
LOG_DIR    = ROOT / "logs"
LOG        = LOG_DIR / "t18_autosync.log"
CRASH_LOG  = LOG_DIR / "t18_autosync_crash.log"
LOCK_FILE  = ROOT / ".locks" / "t18_autosync.lock"

# Tunables
SCAN_INTERVAL_SEC     = int(os.getenv("T18_SCAN_SEC", "15"))   # how often to scan FS
DEBOUNCE_SEC          = int(os.getenv("T18_DEBOUNCE", "30"))   # wait after last change
MIN_COMMIT_INTERVAL   = int(os.getenv("T18_MIN_COMMIT_SEC", "60"))
GIT_REMOTE            = os.getenv("T18_REMOTE", "origin")
GIT_BRANCH            = os.getenv("T18_BRANCH", "main")

# Ignore rules (lightweight)
IGNORE_DIRS = {".git", ".venv", "__pycache__", "logs", ".locks", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
IGNORE_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".parquet", ".zip", ".gz", ".lz4", ".lock"}
IGNORE_FILES = {"t18_autosync.lock"}

# -------- logging ----------
def _ensure_dirs():
    (ROOT / ".locks").mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def log(msg):
    _ensure_dirs()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def crash(msg):
    _ensure_dirs()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with CRASH_LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

# -------- single instance guard ----------
def take_lock():
    _ensure_dirs()
    try:
        if LOCK_FILE.exists():
            # stale lock? if older than 1 day, reclaim
            try:
                if time.time() - LOCK_FILE.stat().st_mtime > 86400:
                    LOCK_FILE.unlink(missing_ok=True)
            except Exception:
                pass
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
        return True
    except FileExistsError:
        return False

def release_lock():
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass

# -------- git helpers (hidden, no console) ----------
def _git_path():
    # Prefer real git.exe to avoid .cmd wrappers
    candidates = [
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        os.environ.get("GIT_EXE", ""),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return "git"  # fallback (still hidden below)

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
DETACHED_PROCESS = 0x00000008
STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)

def _run_git(args, timeout=120):
    cmd = [_git_path(), "-C", str(ROOT), *args]
    si = subprocess.STARTUPINFO()
    si.dwFlags |= STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    env = os.environ.copy()
    # ensure fully non-interactive, no UI
    env.setdefault("HOME", str(ROOT / "system_home"))
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GCM_INTERACTIVE", "Never")
    env.setdefault("GIT_ASKPASS", "echo")
    env.setdefault("SSH_ASKPASS", "echo")
    env.setdefault("GIT_PAGER", "cat")
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        startupinfo=si,
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def repo_dirty():
    rc, out, err = _run_git(["status", "--porcelain"])
    if rc != 0:
        log(f"git status error rc={rc} err={err}")
        return False, ""
    return bool(out), out

def commit_all():
    rc, out, err = _run_git(["add", "-A"])
    if rc != 0:
        log(f"git add error rc={rc} err={err}")
        return False
    msg = f'autosync: {time.strftime("%Y-%m-%d %H:%M:%S")}'
    rc, out, err = _run_git(["commit", "-m", msg, "--quiet"])
    if rc == 0:
        log(f"committed: {msg}")
        return True
    # rc!=0 often means "nothing to commit"
    if "nothing to commit" in (out + " " + err).lower():
        return False
    log(f"git commit rc={rc} out={out} err={err}")
    return False

def push_quiet():
    rc, out, err = _run_git(["push", "--quiet", "--porcelain", GIT_REMOTE, GIT_BRANCH])
    if rc == 0:
        log(f"pushed to {GIT_REMOTE}/{GIT_BRANCH}")
        return True
    # Do NOT fetch/pull; just log and continue (one-way)
    log(f"push failed (one-way, no fetch): rc={rc} out={out} err={err}")
    return False

# -------- scan / debounce ----------
def iter_files():
    for root, dirs, files in os.walk(ROOT):
        # prune ignore dirs
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for name in files:
            if name in IGNORE_FILES: 
                continue
            p = Path(root) / name
            if p.suffix.lower() in IGNORE_SUFFIXES:
                continue
            yield p

def fs_fingerprint():
    # lightweight hash: paths + mtimes + sizes
    h = hashlib.sha1()
    for p in sorted(iter_files()):
        try:
            st = p.stat()
        except Exception:
            continue
        h.update(str(p.relative_to(ROOT)).encode("utf-8", "ignore"))
        h.update(str(int(st.st_mtime)).encode())
        h.update(str(st.st_size).encode())
    return h.hexdigest()

def main():
    if not take_lock():
        log("another instance detected; exiting")
        return
    log("=== t18_autosync starting (push-only, hidden) ===")
    last_fp = ""
    last_change_t = 0.0
    last_commit_t = 0.0
    hb_t = 0.0
    try:
        while True:
            fp = fs_fingerprint()
            now = time.time()
            if fp != last_fp:
                last_fp = fp
                last_change_t = now
            # heartbeat
            if now - hb_t >= 60:
                log("heartbeat: running")
                hb_t = now
            # debounce window passed and min commit spacing respected?
            if last_change_t and (now - last_change_t >= DEBOUNCE_SEC) and (now - last_commit_t >= MIN_COMMIT_INTERVAL):
                dirty, detail = repo_dirty()
                if dirty:
                    if commit_all():
                        push_quiet()
                        last_commit_t = now
                else:
                    # still push if commit was external (rare)
                    pass
            time.sleep(SCAN_INTERVAL_SEC)
    except Exception:
        crash(traceback.format_exc())
        log("crashed; see crash log")
    finally:
        release_lock()

if __name__ == "__main__":
    main()
