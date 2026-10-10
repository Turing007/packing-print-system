@echo off
REM ============================================================
REM One-click release: bump version, build, commit, tag, push,
REM create GitHub release.
REM Usage:
REM     release.bat patch    bump 1.0.0 to 1.0.1
REM     release.bat minor    bump 1.0.0 to 1.1.0
REM     release.bat major    bump 1.0.0 to 2.0.0
REM     release.bat          default: patch
REM WARNING: keep this file pure ASCII (English only).
REM   Windows cmd.exe mis-parses batch files with non-ASCII bytes
REM   (lines get corrupted / scripts can loop forever). Chinese
REM   text must come from external files, never from this .bat.
REM ============================================================

setlocal enabledelayedexpansion
chcp 936 > nul
cd /d "%~dp0"

set "BUMP=%~1"
if "!BUMP!"=="" set "BUMP=patch"

REM read current version (updater.py line at column 0)
for /f "tokens=2 delims== " %%i in ('findstr /B "__CURRENT_VERSION__" updater.py') do (
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
echo Bumping version !CUR! to !NEW!

REM update version number in updater.py
powershell -NoProfile -Command "$f='updater.py'; $t=[IO.File]::ReadAllText($f,[Text.Encoding]::UTF8); $t=$t -replace '(?<=__CURRENT_VERSION__ = \x22)[\d.]+(?=\x22)','!NEW!'; [IO.File]::WriteAllText($f,$t,(New-Object System.Text.UTF8Encoding($false)))"

REM build (creates release\ exe files)
call build.bat
if errorlevel 1 exit /b 1

REM commit release
git add updater.py build.bat release.bat build.spec installer.nsi
git commit -m "release: v!NEW!"

REM tag + push
git tag -a "v!NEW!" -m "v!NEW!"
git push origin master
git push origin "v!NEW!"

REM write release title (Chinese) to GBK temp file, read it back
python -c "open('release_title.txt','w',encoding='gbk').write('\u88c5\u7bb1\u6253\u5370\u7cfb\u7edf v!NEW!')"
for /f "usebackq delims=" %%t in ("release_title.txt") do set "TITLE=%%t"
del /q release_title.txt

REM create GitHub release with assets
gh release create "v!NEW!" ^
  "release\PackingPrintSystem_v!NEW!_setup.exe" ^
  "release\PackingPrint_v!NEW!_portable.exe" ^
  --title "!TITLE!" ^
  --generate-notes

echo.
echo Release done: https://github.com/Turing007/packing-print-system/releases/tag/v!NEW!
endlocal
