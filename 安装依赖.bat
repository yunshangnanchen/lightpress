@echo off
chcp 936 >nul
setlocal
cd /d "%~dp0"

echo.
echo  ============================================
echo    轻压 · 安装 Python 依赖
echo  ============================================
echo.

where py >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3"
) else (
    set "PY=python"
)

%PY% --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 没有找到 Python。
    echo 请先安装 Python 3.10 或更新版本，并勾选 "Add Python to PATH"。
    echo 下载地址：https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

echo 正在把 Pillow 和 NumPy 安装到工具目录的 .deps 文件夹……
echo 这样不会影响电脑上的其他 Python 项目。
echo.

%PY% -m pip install --disable-pip-version-check --upgrade --target "%~dp0.deps" -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo [失败] 依赖安装没有完成。
    echo 请检查网络连接，或在命令行手动执行：
    echo   %PY% -m pip install --target "%~dp0.deps" -r "%~dp0requirements.txt"
    pause
    exit /b 1
)

echo.
echo [完成] 现在可以双击 "启动工具.bat" 使用轻压。
pause
