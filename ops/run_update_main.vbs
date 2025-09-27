Dim sh, cmd
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\T18"
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""C:\T18\ops\update_main.ps1"""
sh.Run cmd, 0, True
MsgBox "Update finished.", 64, "T18 Git"
