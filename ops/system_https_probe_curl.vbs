Dim sh: Set sh = CreateObject("WScript.Shell")
' run hidden (0), don?t wait (False) or wait (True) depending on need
sh.Run "cmd.exe /c C:\T18\ops\system_https_probe_curl.cmd", 0, True
' optionally: sh.Run """C:\T18\.venv\Scripts\pythonw.exe"" ""C:\T18\ops\someprobe.pyw""", 0, True
' or call git.exe directly hidden via a tiny pythonw helper if you prefer
' (your autosync already does this correctly)
' done
