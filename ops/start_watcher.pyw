import runpy, traceback, pathlib
LOG = pathlib.Path(r"C:\T18\logs\watcher_boot.log")
try:
    LOG.write_text("booting watcher...\n", encoding="utf-8")
    runpy.run_path(r"C:\T18\ops\notion_git_watcher.pyw", run_name="__main__")
except SystemExit as e:
    LOG.write_text(f"SystemExit: {e.code}\n", encoding="utf-8")
    raise
except Exception:
    LOG.write_text("CRASH:\n" + traceback.format_exc(), encoding="utf-8")
