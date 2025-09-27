Dim sh: Set sh = CreateObject("WScript.Shell")
Dim env: Set env = sh.Environment("PROCESS")

' Ensure a HOME for SYSTEM and kill any interactive prompts
env("HOME") = "C:\T18\system_home"
env("GIT_TERMINAL_PROMPT") = "0"
env("GCM_INTERACTIVE") = "Never"
env("GIT_ASKPASS") = "echo"
env("SSH_ASKPASS") = "echo"
env("GIT_PAGER") = "cat"

' Resolve git.exe (x64 then x86)
Dim fso: Set fso = CreateObject("Scripting.FileSystemObject")
Dim git
git = "C:\Program Files\Git\bin\git.exe"
If Not fso.FileExists(git) Then
  git = "C:\Program Files (x86)\Git\bin\git.exe"
End If

' Build commands
Dim repo: repo = " -C C:\T18 "
Dim cmdFetch: cmdFetch = """" & git & """" & repo & "fetch --prune --quiet"
'Dim cmdPull:  cmdPull  = """" & git & """" & repo & "pull --ff-only --quiet"

' Run hidden (0), wait (True)
sh.Run cmdFetch, 0, True
' sh.Run cmdPull, 0, True

' Log a heartbeat
sh.Run "cmd.exe /c echo %date% %time% fetched>>C:\T18\logs\git_silent_sync.log", 0, True
