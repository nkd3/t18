import os, subprocess, pathlib, time

LOG = pathlib.Path(r"C:\T18\logs\git_silent_sync.log")
LOG.parent.mkdir(parents=True, exist_ok=True)

# Hardened "no window" flags
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
DETACHED_PROCESS = 0x00000008
STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
SW_HIDE = 0

def run_git(args):
    # Resolve git.exe (x64 then x86)
    git = r"C:\Program Files\Git\bin\git.exe"
    if not os.path.exists(git):
        git = r"C:\Program Files (x86)\Git\bin\git.exe"

    si = subprocess.STARTUPINFO()
    si.dwFlags |= STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE

    env = os.environ.copy()
    env["HOME"] = r"C:\T18\system_home"
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GCM_INTERACTIVE", "Never")
    env.setdefault("GIT_ASKPASS", "echo")
    env.setdefault("SSH_ASKPASS", "echo")
    env.setdefault("GIT_PAGER", "cat")

    p = subprocess.run(
        [git, "-C", r"C:\T18", *args],
        cwd=r"C:\T18",
        env=env,
        startupinfo=si,
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        shell=False,
        capture_output=True,
        text=True,
    )
    return p

def append(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")

# Do a quiet fetch (and optional fast-forward pull)
rc1 = run_git(["fetch", "--prune", "--quiet"]).returncode
append(f"fetched rc={rc1}")
# To also pull fast-forward only, uncomment:
# rc2 = run_git(["pull", "--ff-only", "--quiet"]).returncode
# append(f"pull rc={rc2}")
