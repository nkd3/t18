# C:\T18\ops\_silent_git2.py
import os, subprocess, shlex

# Resolve *real* git.exe (never git.cmd)
_GIT = r"C:\Program Files\Git\bin\git.exe"
if not os.path.exists(_GIT):
    _GIT = r"C:\Program Files (x86)\Git\bin\git.exe"

CREATE_NO_WINDOW     = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
DETACHED_PROCESS     = 0x00000008
STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)

# Inline -c options to *guarantee* no UI/prompts/pagers/helpers
_GIT_INLINE_CFG = [
    "-c", "credential.helper=",
    "-c", "credential.prompt=false",
    "-c", "core.askpass=",
    "-c", "core.pager=cat",
]

# Extra env to belt-and-suspenders this
_BASE_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GCM_INTERACTIVE": "Never",
    "GIT_ASKPASS": "echo",
    "SSH_ASKPASS": "echo",
    "GIT_PAGER": "cat",
    # avoid MSYS converting paths or popping terminals
    "MSYS2_ARG_CONV_EXCL": "*",
}

def run_git_hidden(args, cwd=r"C:\T18", extra_env=None, capture=True):
    if isinstance(args, str):
        args = shlex.split(args)
    # ensure git.exe is head and inject our inline configs
    if not args or os.path.basename(str(args[0])).lower() not in ("git.exe", "git"):
        cmd = [_GIT] + _GIT_INLINE_CFG + list(args)
    else:
        cmd = [_GIT] + _GIT_INLINE_CFG + list(args[1:])

    env = os.environ.copy()
    env.update(_BASE_ENV)
    if extra_env:
        env.update(extra_env)

    si = subprocess.STARTUPINFO()
    si.dwFlags |= STARTF_USESHOWWINDOW
    si.wShowWindow = 0

    flags = CREATE_NO_WINDOW | DETACHED_PROCESS

    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        startupinfo=si,
        creationflags=flags,
        shell=False,
        capture_output=capture,
        text=True,
        check=False,
    )
