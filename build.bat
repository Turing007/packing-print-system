@echo off
REM ============================================================
REM One-click build: version, PyInstaller, NSIS, release folder
REM Usage: build.bat
REM WARNING: keep this file pure ASCII (English only).
REM   Windows cmd.exe mis-parses batch files with non-ASCII bytes
REM   (lines get corrupted / scripts can loop forever). Chinese
REM   text must come from external files, never from this .bat.
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ---- 1. read version (single source: updater.py, line at column 0) ----
for /f "tokens=2 delims== " %%i in ('findstr /B "__CURRENT_VERSION__" updater.py') do (
    set "VERSION=%%~i"
)
set "VERSION=!VERSION:"=!"
if "!VERSION!"=="" set "VERSION=0.0.0"

echo [1/5] Current version: !VERSION!

REM ---- 2. clean old artifacts ----
echo [2/5] Cleaning old artifacts...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist release rmdir /s /q release
del /q PackingPrint_v*.exe 2>nul
del /q PackingPrintSystem_v*.exe 2>nul

REM ---- 3. PyInstaller (ASCII file names, for NSIS) ----
echo [3/5] Running PyInstaller...
python -m PyInstaller --clean --noconfirm build.spec
if errorlevel 1 (
    echo [X] PyInstaller build failed
    exit /b 1
)

REM ---- 4. copy portable exe to project root (NSIS looks here) ----
copy /y "dist\PackingPrint_v!VERSION!_portable.exe" "PackingPrint_v!VERSION!_portable.exe" > nul

REM ---- 5. NSIS ----
echo [5/5] Building installer...
set "MAKENSIS=C:\Program Files (x86)\NSIS\makensis.exe"
if not exist "!MAKENSIS!" (
    echo [WARN] NSIS not found, installer skipped. Portable exe is in dist\
    goto :done
)

"!MAKENSIS!" "/DAPP_VERSION=!VERSION!" "installer.nsi"
if errorlevel 1 (
    echo [X] NSIS installer build failed
    exit /b 1
)

REM ---- collect into release/ ----
mkdir release
move /y "PackingPrintSystem_v!VERSION!_setup.exe" "release\" > nul
move /y "PackingPrint_v!VERSION!_portable.exe" "release\" > nul

:done
echo.
echo ============================================================
echo  Build done. Artifacts in release\ :
dir /b release 2>nul
echo ============================================================
echo.
echo Next: run release.bat to publish, or upload release\ files manually.
endlocal
