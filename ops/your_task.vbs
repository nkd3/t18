Dim sh: Set sh = CreateObject("WScript.Shell")
' EXAMPLES (pick one and comment the other):
' 1) If you used to run a .cmd:
sh.Run "cmd.exe /c C:\T18\ops\your_task.cmd", 0, True
' 2) Or call your Python script directly (no console):
' sh.Run """C:\T18\.venv\Scripts\pythonw.exe"" ""C:\T18\ops\your_script.py""", 0, True
' 3) Or call git.exe directly (also hidden via pythonw helper you already have)
' Done
