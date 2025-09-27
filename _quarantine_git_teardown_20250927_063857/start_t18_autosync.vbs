' start_t18_autosync.vbs — launch autosync hidden
Dim WshShell, cmd
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\T18"
cmd = """C:\T18\.venv\Scripts\pythonw.exe"" ""C:\T18\ops\t18_autosync.py"""
WshShell.Run cmd, 0, False
