@echo off
REM Knoa 前后端一键脚本的 Windows 启动器
REM 双击本文件即可运行；参数同 dev.sh: start(默认) / restart / stop / status
"C:\Program Files\Git\bin\bash.exe" "%~dp0dev.sh" %*
