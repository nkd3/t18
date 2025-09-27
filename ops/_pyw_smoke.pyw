import time, pathlib
p = pathlib.Path(r"C:\T18\logs\pyw_smoke.log")
p.write_text("pyw smoke started\n", encoding="utf-8")
time.sleep(60)
p.write_text("pyw smoke exiting\n", encoding="utf-8")
