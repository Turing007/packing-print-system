@echo off
chcp 65001 >nul
echo ========================================
echo    装箱打印系统 - EXE 打包工具
echo ========================================
echo.
echo 正在检测 Python 环境...
call "%~dp0python_cmd.bat"
if %ERRORLEVEL% NEQ 0 (
    pause
    exit /b 1
)

for %%I in ("%PYTHON_EXE%") do set "PYTHON_HOME=%%~dpI"

"%PYTHON_EXE%" --version

echo 正在检测 PyInstaller...
"%PYTHON_EXE%" -m PyInstaller --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 正在安装 PyInstaller...
    "%PYTHON_EXE%" -m pip install pyinstaller
)

echo.
echo 正在打包 EXE（单文件模式）...
echo.

"%PYTHON_EXE%" -m PyInstaller --onefile --windowed --name "装箱打印系统" ^
    --add-data "packing_label.css;." ^
    --add-data "%PYTHON_HOME%tcl\tcl8.6;tcl\tcl8.6" ^
    --add-data "%PYTHON_HOME%tcl\tk8.6;tcl\tk8.6" ^
    --hidden-import tkinter ^
    --hidden-import tkinter.ttk ^
    --hidden-import tkinter.messagebox ^
    --hidden-import json ^
    --hidden-import os ^
    --hidden-import tempfile ^
    --hidden-import webbrowser ^
    --hidden-import datetime ^
    --hidden-import dataclasses ^
    --hidden-import typing ^
    main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ======== 打包成功 ========
    echo 输出文件: dist\装箱打印系统.exe
    echo.
    echo 首次运行前，请确保 dist\packing_label.css 文件与 EXE 在同一目录
    echo ============================
) else (
    echo.
    echo [错误] 打包失败，请检查错误信息
)

pause
