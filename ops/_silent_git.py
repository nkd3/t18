import os, subprocess

# Hardened flags to suppress any windows
_CREATE_NO_WINDOW     = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_DETACHED_PROCESS     = 0x00000008
_STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
_SW_HIDE              = 0

# Resolve the real git.exe (avoid git.cmd)
GIT_EXE = r"C:\Program Files\Git\bin\git.exe"
if not os.path.exists(GIT_EXE):
    GIT_EXE = r"C:\Program Files (x86)\Git\bin\git.exe"

def run_git_hidden(args, cwd=r"C:\T18", env=None, check=False):
    """
    args: list like ["git","status"] or [GIT_EXE,"status"].
    Runs git fully hidden, no console, no prompts.
    """
    si = subprocess.STARTUPINFO()
    si.dwFlags |= _STARTF_USESHOWWINDOW
    si.wShowWindow = _SW_HIDE

    e = os.environ.copy()
    if env: e.update(env)
    # kill any interactive prompts & pagers
    e.setdefault("GIT_TERMINAL_PROMPT","0")
    e.setdefault("GCM_INTERACTIVE","Never")
    e.setdefault("GIT_ASKPASS","echo")
    e.setdefault("SSH_ASKPASS","echo")
    e.setdefault("GIT_PAGER","cat")

    # force real git.exe in position 0
    if args:
        a0 = args[0].lower()
        if a0 == "git" or a0.endswith("git.exe"):
            args = [GIT_EXE] + list(args[1:])

    return subprocess.run(
        args,
        cwd=cwd,
        env=e,
        startupinfo=si,
        creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS,
        shell=False,
        capture_output=True,
        text=True,
        check=check,
    )
