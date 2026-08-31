@echo off
REM ============================================================
REM 一键发布：build → git push → gh release create
REM 用法：
REM     release.bat patch    升级 1.0.0 -> 1.0.1
REM     release.bat minor    升级 1.0.0 -> 1.1.0
REM     release.bat major    升级 1.0.0 -> 2.0.0
REM     release.bat          默认 patch
REM ============================================================

setlocal enabledelayedexpansion
chcp 65001 > nul
cd /d "%~dp0"

set "BUMP=%~1"
if "!BUMP!"=="" set "BUMP=patch"

REM 读当前版本号
for /f "tokens=2 delims== delims " %%i in ('findstr /R "__CURRENT_VERSION__" updater.py') do (
    set "CUR=%%~i"
)
set "CUR=!CUR:"=!"
for /f "tokens=1-3 delims=." %%a in ("!CUR!") do (
    set "MAJOR=%%a"
    set "MINOR=%%b"
    set "PATCH=%%c"
)

if /i "!BUMP!"=="major" (
    set /a MAJOR=MAJOR+1
    set "MINOR=0"
    set "PATCH=0"
) else if /i "!BUMP!"=="minor" (
    set /a MINOR=MINOR+1
    set "PATCH=0"
) else (
    set /a PATCH=PATCH+1
)
set "NEW=!MAJOR!.!MINOR!.!PATCH!"
echo 当前版本：!CUR!  -^>  新版本：!NEW!

REM 修改 updater.py
powershell -Command "(Get-Content updater.py -Encoding UTF8) -replace '__CURRENT_VERSION__\s*=\s*\"[^\"]+\"', '__CURRENT_VERSION__ = \"!NEW!\"' | Set-Content updater.py -Encoding UTF8"

REM 重新打包
call build.bat
if errorlevel 1 exit /b 1

REM 提交代码
git add updater.py build.bat build.spec installer.nsi
git commit -m "release: v!NEW!"

REM 打 tag + 推送
git tag -a "v!NEW!" -m "v!NEW!"
git push origin master
git push origin "v!NEW!"

REM 在 GitHub 创建 Release 并上传资产
gh release create "v!NEW!" ^
  "release\PackingPrintSystem_v!NEW!_setup.exe" ^
  "release\PackingPrint_v!NEW!_portable.exe" ^
  --title "装箱打印系统 v!NEW!" ^
  --generate-notes

echo.
echo 发布完成：https://github.com/Turing007/packing-print-system/releases/tag/v!NEW!
endlocal