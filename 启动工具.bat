@echo off
chcp 936 >nul
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%~dp0vendor;%~dp0.deps;%PYTHONPATH%"
set "PY=python"

where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"

%PY% --version >nul 2>&1
if errorlevel 1 goto no_python

%PY% -c "import PIL, numpy, tkinter" >nul 2>&1
if errorlevel 1 goto install_deps

:launch
if not exist "%~dp0app.py" goto no_app
where pythonw >nul 2>&1
if errorlevel 1 goto launch_console
start "" pythonw "%~dp0app.py"
exit /b 0

:launch_console
%PY% "%~dp0app.py"
exit /b 0

:install_deps
echo.
echo 缺少运行依赖 Pillow / NumPy。
echo 即将安装到工具目录，不会影响其他 Python 项目。
echo.
call "%~dp0安装依赖.bat"
if errorlevel 1 exit /b 1
goto launch

:no_python
echo.
echo [错误] 没有找到 Python 3。
echo 请先安装 Python 3.10 或更新版本，并勾选 Add Python to PATH。
echo 下载：https://www.python.org/downloads/windows/
echo.
pause
exit /b 1

:no_app
echo [错误] 找不到 app.py，请确认工具文件完整。
pause
exit /b 1
