# -*- coding: utf-8 -*-
import os, sys, subprocess, time
from pathlib import Path

ROOT = Path(r"C:\T18")
PYW  = ROOT / r"ops\notion_git_watcher.pyw"
VENV = ROOT / r".venv\Scripts\pythonw.exe"
LOGO = ROOT / r"logs\notion_git_watcher.log"

def main():
    if not VENV.exists():
        # Fallback to system pythonw
        VENV_FALLBACK = Path(sys.executable)
        py = VENV_FALLBACK
    else:
        py = VENV
    # Ensure logs dir
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    # Launch watcher (detached)
    subprocess.Popen([str(py), str(PYW)], cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # exit immediately; no console
if __name__ == "__main__":
    main()
