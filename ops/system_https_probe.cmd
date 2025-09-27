@echo off
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command ^
  "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; ^
    try { (Invoke-WebRequest 'https://api.notion.com/v1/users' -Method Head -TimeoutSec 15).StatusCode } ^
    catch { $_.Exception.Message }" ^
  > "C:\Windows\Temp\system_https_probe.txt" 2>&1
