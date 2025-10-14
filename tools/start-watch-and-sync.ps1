Start-Process -WindowStyle Hidden -FilePath "powershell.exe" -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy","Bypass",
  "-File","C:\T18\tools\watch-and-sync.ps1"
) | Out-Null
