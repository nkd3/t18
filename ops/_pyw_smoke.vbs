Dim W, cmd
Set W = CreateObject("WScript.Shell")
W.CurrentDirectory = "C:\T18"
cmd = """C:\T18\.venv\Scripts\pythonw.exe"" ""C:\T18\ops\_pyw_smoke.pyw"""
W.Run cmd, 0, False
