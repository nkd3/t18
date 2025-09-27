@echo off
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command ^
  "$PSVersionTable.PSVersion.ToString()" ^
  > "C:\Windows\Temp\sys_ps_ok.txt" 2>&1
