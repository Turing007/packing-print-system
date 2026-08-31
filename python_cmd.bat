@echo off
set "PYTHON_EXE="

call :check "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if defined PYTHON_EXE goto :found
call :check "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if defined PYTHON_EXE goto :found
call :check "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if defined PYTHON_EXE goto :found
call :check "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
if defined PYTHON_EXE goto :found
call :check "%LOCALAPPDATA%\Programs\Python\Python38\python.exe"
if defined PYTHON_EXE goto :found
call :check "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if defined PYTHON_EXE goto :found

for /f "delims=" %%P in ('where python 2^>nul') do (
    call :check "%%~P"
    if defined PYTHON_EXE goto :found
)

where py >nul 2>&1
if not errorlevel 1 (
    py --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=py"
        goto :found
    )
)

echo [错误] 未找到可用的 Python 3.8+。
echo 当前系统的 python/py 命令不可用，请重新安装 Python，或检查 PATH/py launcher 配置。
exit /b 1

:found
exit /b 0

:check
if exist "%~1" (
    "%~1" --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=%~1"
)
exit /b 0
