@echo off
chcp 936 >nul
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%~dp0vendor;%~dp0.deps;%PYTHONPATH%"

where py >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3"
) else (
    set "PY=python"
)

%PY% "%~dp0app.py"
echo.
echo 程序已退出。若有报错信息请截图或复制上方内容。
pause
