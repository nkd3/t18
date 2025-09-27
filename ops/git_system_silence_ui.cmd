@echo off
set "HOME=C:\T18\system_home"
set "PATH=%ProgramFiles%\Git\bin;%ProgramFiles(x86)%\Git\bin;%PATH%"
git config --global credential.interactive never
git config --global credential.prompt none
git config --global core.pager cat
