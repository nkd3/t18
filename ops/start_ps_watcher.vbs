Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\T18"
cmd = """C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"" -NoProfile -ExecutionPolicy Bypass -File ""C:\T18\ops\ps_watcher.ps1"""
WshShell.Run cmd, 0, False
