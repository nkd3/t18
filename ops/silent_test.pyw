# silent_test.pyw
import time
from pathlib import Path
log = Path(r"C:\T18\logs") / "silent_test.log"
log.parent.mkdir(parents=True, exist_ok=True)
with log.open("a", encoding="utf-8") as f:
    f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " - silent test ran via pythonw.exe\n")
