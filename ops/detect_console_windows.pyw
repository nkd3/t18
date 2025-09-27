# C:\T18\ops\detect_console_windows.pyw
import ctypes, ctypes.wintypes as wt, time, os, datetime

LOG = r"C:\T18\logs\noflash_windows.log"
os.makedirs(os.path.dirname(LOG), exist_ok=True)

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
GetWindowThreadProcessId.restype  = wt.DWORD

EnumWindows = user32.EnumWindows
EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM), wt.LPARAM]
EnumWindows.restype  = wt.BOOL

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [wt.HWND]
IsWindowVisible.restype  = wt.BOOL

GetClassNameW = user32.GetClassNameW
GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
GetClassNameW.restype  = ctypes.c_int

GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextW = user32.GetWindowTextW

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
OpenProcess.restype  = wt.HANDLE

QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
QueryFullProcessImageNameW.restype  = wt.BOOL

CloseHandle = kernel32.CloseHandle

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SEEN = set()

def proc_path(pid: int) -> str:
    h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return f"PID {pid}"
    try:
        buf_len = wt.DWORD(32768)
        buf = ctypes.create_unicode_buffer(buf_len.value)
        if QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(buf_len)):
            return buf.value
        return f"PID {pid}"
    finally:
        CloseHandle(h)

def log(line: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")

CMPROC = {"ConsoleWindowClass"}  # classic console class

@ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
def enum_cb(hwnd, lparam):
    try:
        if not IsWindowVisible(hwnd):
            return True
        # class name
        cn_buf = ctypes.create_unicode_buffer(256)
        GetClassNameW(hwnd, cn_buf, 256)
        cls = cn_buf.value

        # only console-ish windows
        if cls not in CMPROC:
            return True

        # window text (optional)
        length = GetWindowTextLengthW(hwnd)
        tbuf = ctypes.create_unicode_buffer(length + 1)
        GetWindowTextW(hwnd, tbuf, length + 1)
        title = tbuf.value

        pid = wt.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        key = (int(hwnd), int(pid.value))
        if key not in SEEN:
            SEEN.add(key)
            path = proc_path(pid.value)
            log(f"VISIBLE CONSOLE hwnd=0x{int(hwnd):X} pid={pid.value} exe={path} title={title!r} class={cls}")
    except Exception as e:
        log(f"enum error: {e}")
    return True

def main():
    log("==== WINDOW WATCH START ====")
    # watch ~10 minutes; adjust if you want
    end = time.time() + 600
    while time.time() < end:
        EnumWindows(enum_cb, 0)
        time.sleep(0.2)
    log("==== WINDOW WATCH END ====")

if __name__ == "__main__":
    main()
