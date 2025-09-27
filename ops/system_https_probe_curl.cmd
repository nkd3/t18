@echo off
"%SystemRoot%\System32\curl.exe" -I --max-time 15 https://api.notion.com/v1/users > "C:\Windows\Temp\system_https_probe.txt" 2>&1
