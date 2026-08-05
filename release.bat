@echo off
REM Build a release: the exe plus its SHA-256, ready to attach to a GitHub
REM release. Everything lands in release\ .
setlocal enabledelayedexpansion

call build.bat
if errorlevel 1 exit /b 1

if not exist release mkdir release
copy /y dist\YT-Pro.exe release\YT-Pro.exe >nul

for /f "tokens=*" %%v in ('python -c "import ytpro; print(ytpro.__version__)"') do set VER=%%v
for /f "tokens=*" %%h in ('python -c "from ytpro.tools import sha256_of; print(sha256_of(r'release\YT-Pro.exe'))"') do set HASH=%%h
for /f "tokens=*" %%r in ('python -c "import ytpro; print(ytpro.GITHUB_REPO)"') do set REPO=%%r

> release\SHA256SUMS.txt echo !HASH!  YT-Pro.exe

echo.
echo ============================================================
echo   Version   v!VER!
echo   SHA-256   !HASH!
echo   Repo      !REPO!
echo ============================================================
echo.
echo release\ contains:
dir /b release
echo.
echo To publish:
echo   1. Tag it:        git tag v!VER!  ^&^&  git push origin v!VER!
echo   2. Draft a release on GitHub for tag v!VER!
echo   3. Attach release\YT-Pro.exe and release\SHA256SUMS.txt
echo   4. Paste the SHA-256 above into the release notes
echo.
echo The tag MUST be v!VER! - the updater compares it against __version__,
echo so a mismatched tag means nobody gets offered the update.
endlocal
