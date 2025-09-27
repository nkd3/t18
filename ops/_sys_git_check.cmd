@echo off
cd /d C:\T18
set "HOME=C:\T18\system_home"
set "PATH=%SystemRoot%\System32;%ProgramFiles%\Git\bin;%ProgramFiles(x86)%\Git\bin;%ProgramFiles%\Git\cmd;%ProgramFiles(x86)%\Git\cmd;%PATH%"
git --version  >  C:\Windows\Temp\sys_git.txt 2>&1
git rev-parse --is-inside-work-tree >> C:\Windows\Temp\sys_git.txt 2>&1
git status --porcelain            >> C:\Windows\Temp\sys_git.txt 2>&1
