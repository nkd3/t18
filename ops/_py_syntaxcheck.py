import sys, py_compile
try:
    py_compile.compile(r"C:\T18\ops\notion_git_watcher.pyw", doraise=True)
    print("OK")
except Exception as e:
    print("SYNTAX_ERROR")
    print(e)
    sys.exit(1)
