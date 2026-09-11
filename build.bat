@echo off
REM ============================================================
REM 一键打包脚本：读版本号 → PyInstaller → NSIS 安装器 → 输出到 release/
REM 用法：build.bat
REM ============================================================

setlocal enabledelayedexpansion
chcp 65001 > nul

cd /d "%~dp0"

REM ---- 1. 读取版本号（从 updater.py 解析，确保单一来源）----
REM /B 只匹配行首，锁定第 32 行的定义（注释和 `return __CURRENT_VERSION__` 也含该串）
REM delims 用 "= " 切开 `__CURRENT_VERSION__ = "1.0.9"`：第 2 段是 "1.0.9"，%%~i 去掉引号
for /f "tokens=2 delims== " %%i in ('findstr /B "__CURRENT_VERSION__" updater.py') do (
    set "VERSION=%%~i"
)
REM 去引号（兜底：%%~i 已去引号，此处仅防手写改动）
set "VERSION=!VERSION:"=!"
if "!VERSION!"=="" set "VERSION=0.0.0"

echo [1/5] 当前版本：!VERSION!

REM ---- 2. 清理旧的构建产物 ----
echo [2/5] 清理旧产物...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist release rmdir /s /q release
del /q PackingPrint_v*.exe 2>nul
del /q PackingPrintSystem_v*.exe 2>nul

REM ---- 3. 跑 PyInstaller（ASCII 文件名，方便 NSIS 引用）----
echo [3/5] 调用 PyInstaller 打包 portable EXE...
python -m PyInstaller --clean --noconfirm build.spec
if errorlevel 1 (
    echo [X] PyInstaller 打包失败
    exit /b 1
)

REM ---- 4. 把 portable EXE 复制一份到项目根（NSIS 在脚本目录找源文件）----
copy /y "dist\PackingPrint_v!VERSION!_portable.exe" "PackingPrint_v!VERSION!_portable.exe" > nul

REM ---- 5. 跑 NSIS ----
echo [5/5] 生成安装器...
set "MAKENSIS=C:\Program Files (x86)\NSIS\makensis.exe"
if not exist "!MAKENSIS!" (
    echo [!] 未找到 NSIS，跳过安装器生成。便携版 EXE 在 dist\
    goto :done
)

"!MAKENSIS!" "/DAPP_VERSION=!VERSION!" "installer.nsi"
if errorlevel 1 (
    echo [X] NSIS 安装器生成失败
    exit /b 1
)

REM ---- 整理 release/ 目录 ----
mkdir release
move /y "PackingPrintSystem_v!VERSION!_setup.exe" "release\" > nul
move /y "PackingPrint_v!VERSION!_portable.exe" "release\" > nul

:done
echo.
echo ============================================================
echo  打包完成，产物在 release\ 目录：
dir /b release 2>nul
echo ============================================================
echo.
echo 下一步：把 release\ 下文件拖到 GitHub Release 页面上传即可。
echo 或运行 release.bat 一键发布。
endlocal