# t18_autosync.py  (v2 - pruned walker + single-instance + heartbeat)
# Local-only autosync: C:\T18 -> origin/$BRANCH
# Runs hidden via pythonw.exe + VBS + Scheduled Task. Logs to C:\T18\logs\.

import os, sys, time, subprocess
from pathlib import Path

REPO_DIR = Path(r"C:\T18").resolve()
BRANCH   = os.environ.get("T18_BRANCH", "main")
DEBOUNCE_SECONDS = int(os.environ.get("T18_DEBOUNCE", "90"))
MIN_COMMIT_INTERVAL = int(os.environ.get("T18_MIN_COMMIT_SEC", "300"))
POLL_INTERVAL = 3

LOG_DIR  = Path(r"C:\T18\logs")
LOG_PATH = LOG_DIR / "t18_autosync.log"
CRASH_LOG_PATH = LOG_DIR / "t18_autosync_crash.log"
LOCK_PATH = LOG_DIR / "t18_autosync.lock"

# Hard-ignore (directories fully pruned) + file extensions ignored
IGNORE_DIRS = {".git", ".venv", "logs", "__pycache__", "history", "parquet", "data", "dist", "build", ".idea", ".vscode", "ZZZ"}
IGNORE_EXT  = {".pyc", ".zip", ".db", ".sqlite", ".sqlite3", ".parquet"}

MAX_FILES_IN_MSG = 12
HEARTBEAT_EVERY = 60  # seconds

def log(msg: str):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

def crash(msg: str):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with CRASH_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

def run_git(args, check=True, text=True):
    return subprocess.run(["git", *args], cwd=REPO_DIR, check=check, text=text, capture_output=True)

def single_instance_guard():
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if LOCK_PATH.exists():
            # Another instance likely running
            log("lock present; exiting to keep single instance.")
            sys.exit(0)
        LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")
    except Exception as e:
        crash(f"lock error: {e}")
        # Not fatal—continue without lock

def cleanup_lock():
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink(missing_ok=True)
    except Exception as e:
        crash(f"unlock error: {e}")

def initial_checks():
    if not REPO_DIR.exists():
        raise RuntimeError(f"Repo folder missing: {REPO_DIR}")
    try:
        run_git(["rev-parse", "--is-inside-work-tree"])
    except subprocess.CalledProcessError:
        raise RuntimeError(f"Not a git repo: {REPO_DIR}")
    try:
        run_git(["fetch", "--all"], check=False)
    except Exception as e:
        log(f"fetch warning: {e}")

def iter_files_pruned(root: Path):
    # Pruned os.walk: removes IGNORE_DIRS from traversal so we never descend into them.
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # Prune ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        # Skip paths that already include an ignored part (extra safety)
        parts = Path(dirpath).parts
        if any(p in IGNORE_DIRS for p in parts):
            continue
        # Yield files not in ignored ext
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                if p.suffix.lower() in IGNORE_EXT:
                    continue
                yield p
            except Exception:
                continue

def snapshot(root: Path):
    m = {}
    for p in iter_files_pruned(root):
        try:
            m[str(p.relative_to(root))] = p.stat().st_mtime
        except FileNotFoundError:
            continue
        except PermissionError:
            # Ignore transient locks/permissions
            continue
    return m

def build_commit_message(changed_files):
    n = len(changed_files)
    sample = sorted(changed_files)[:MAX_FILES_IN_MSG]
    extra = "" if n <= MAX_FILES_IN_MSG else f" (+{n - MAX_FILES_IN_MSG} more)"
    preview = ", ".join(sample)
    return f"autosync: {n} file(s) [{preview}{extra}]"

def stage_commit_push(changed_files):
    if not changed_files:
        return
    try:
        run_git(["add", "-A"], check=True)
    except subprocess.CalledProcessError as e:
        log(f"git add error: {e.stderr.strip()}")
        return

    try:
        diff = run_git(["diff", "--cached", "--name-only"], check=True).stdout.strip()
        if not diff:
            log("no staged changes (skip commit)")
            return
    except subprocess.CalledProcessError as e:
        log(f"git diff error: {e.stderr.strip()}")
        return

    msg = build_commit_message(changed_files)
    try:
        run_git(["commit", "-m", msg], check=True)
        log(f"committed: {msg}")
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        if "nothing to commit" in stderr:
            log("nothing to commit")
            return
        log(f"git commit error: {stderr}")
        return

    # Safer on shared branches
    try:
        run_git(["pull", "--rebase", "origin", BRANCH], check=False)
    except subprocess.CalledProcessError as e:
        log(f"git pull warning: {e.stderr.strip()}")

    try:
        run_git(["push", "origin", BRANCH], check=True)
        log(f"pushed to origin/{BRANCH}")
    except subprocess.CalledProcessError as e:
        log(f"git push error: {e.stderr.strip()}")

def main():
    single_instance_guard()
    log("=== T18 autosync starting ===")
    try:
        initial_checks()
    except Exception as e:
        crash(f"startup error: {e}")
        log(f"startup error: {e}")
        cleanup_lock()
        return

    last_snap = snapshot(REPO_DIR)
    last_change_ts = 0.0
    last_commit_ts = 0.0
    changed_since_last = set()
    last_heartbeat = time.time()

    try:
        while True:
            time.sleep(POLL_INTERVAL)
            new_snap = snapshot(REPO_DIR)

            changed = set()
            # mods/adds
            for rel, mt in new_snap.items():
                if rel not in last_snap or last_snap[rel] != mt:
                    changed.add(rel)
            # deletes
            for rel in last_snap.keys() - new_snap.keys():
                changed.add(rel)

            if changed:
                last_change_ts = time.time()
                changed_since_last |= changed
                log(f"detected changes: {len(changed)}")

            now = time.time()
            if changed_since_last and (now - last_change_ts >= DEBOUNCE_SECONDS) and (now - last_commit_ts >= MIN_COMMIT_INTERVAL):
                stage_commit_push(changed_since_last)
                changed_since_last.clear()
                last_commit_ts = now
                last_snap = new_snap
            else:
                last_snap = new_snap

            # heartbeat
            if now - last_heartbeat >= HEARTBEAT_EVERY:
                log("heartbeat: running")
                last_heartbeat = now
    except Exception as e:
        crash(f"loop error: {e}")
    finally:
        cleanup_lock()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        crash(f"fatal error: {e}")
