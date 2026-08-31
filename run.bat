@echo off
chcp 65001 >nul
setlocal

set "APP_DIR=%~dp0"
call "%APP_DIR%python_cmd.bat"
if errorlevel 1 (
    pause
    exit /b 1
)

cd /d "%APP_DIR%"
"%PYTHON_EXE%" main.py
exit /b %ERRORLEVEL%
