Dim W
Set W = CreateObject("WScript.Shell")
W.CurrentDirectory = "C:\T18"
' Run PowerShell hidden, bypass policy, with an optional message you can edit
W.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""C:\T18\ops\git_manual_push.ps1""", 0, False
