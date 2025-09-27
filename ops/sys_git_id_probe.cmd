@echo off
setlocal
set "LOG=C:\Windows\Temp\sys_git_identity.txt"

set "GIT=C:\Program Files\Git\bin\git.exe"
if not exist "%GIT%" set "GIT=C:\Program Files (x86)\Git\bin\git.exe"

>"%LOG%" 2>&1 (
  echo === whoami ===
  whoami
  echo.
  echo === git identity (SYSTEM scope) ===
  "%GIT%" config --show-origin --show-scope user.name
  "%GIT%" config --show-origin --show-scope user.email
  echo.
  echo === git pick-up order (SYSTEM) ===
  "%GIT%" config --list --show-origin
)
endlocal
