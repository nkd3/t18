import os, subprocess, time, sys, pathlib

LOG = pathlib.Path(r"C:\T18\logs\test_hide_windows.log")
LOG.parent.mkdir(parents=True, exist_ok=True)

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)

def run_silent(cmd, cwd=r"C:\T18"):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GCM_INTERACTIVE", "Never")
    env.setdefault("GIT_ASKPASS", "echo")
    p = subprocess.run(
        cmd,
        cwd=cwd,
        startupinfo=si,
        creationflags=CREATE_NO_WINDOW,
        shell=False,
        env=env,
        capture_output=True,
        text=True,
    )
    return p.returncode, p.stdout, p.stderr

with LOG.open("w", encoding="utf-8") as f:
    f.write("begin test\n")
    for i in range(10):
        rc, out, err = run_silent(["git","--version"])
        f.write(f"[{i}] rc={rc} out={out.strip()} err={err.strip()}\n")
        time.sleep(0.4)
    # also try a few real repo ops
    rc1, out1, err1 = run_silent(["git","rev-parse","--is-inside-work-tree"])
    rc2, out2, err2 = run_silent(["git","status","--porcelain"])
    f.write(f"rev-parse rc={rc1} out={out1.strip()} err={err1.strip()}\n")
    f.write(f"status    rc={rc2} out-len={len(out2)} err={err2.strip()}\n")
    f.write("end test\n")
