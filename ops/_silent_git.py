import os, subprocess

# Hardened flags to suppress any windows
CREATE_NO_WINDOW   = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
DETACHED_PROCESS   = 0x00000008
STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
SW_HIDE            = 0

# Resolve git.exe directly (avoid git.cmd shim)
_GIT = r"C:\Program Files\Git\bin\git.exe"
if not os.path.exists(_GIT):
    _GIT = r"C:\Program Files (x86)\Git\bin\git.exe"

def _run_silent(cmd, cwd=None, env=None):
    """
    Run a command hidden, detached, non-interactive. Returns CompletedProcess.
    """
    si = subprocess.STARTUPINFO()
    si.dwFlags |= STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE

    flags = CREATE_NO_WINDOW | DETACHED_PROCESS

    e = os.environ.copy()
    if env:
        e.update(env)

    # Kill all possible interactive prompts / pagers
    e.setdefault("GIT_TERMINAL_PROMPT", "0")
    e.setdefault("GCM_INTERACTIVE", "Never")
    e.setdefault("GIT_ASKPASS", "echo")
    e.setdefault("SSH_ASKPASS", "echo")
    e.setdefault("GIT_PAGER", "cat")

    return subprocess.run(
        cmd,
        cwd=cwd,
        env=e,
        startupinfo=si,
        creationflags=flags,
        shell=False,
        capture_output=True,
        text=True,
    )
