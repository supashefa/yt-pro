@echo off
REM Build a release: exe + checksum + the latest.json that the updater reads.
REM Output goes to release\ , which is what you upload to your static host.
setlocal enabledelayedexpansion

call build.bat
if errorlevel 1 exit /b 1

if not exist release mkdir release
copy /y dist\YT-Pro.exe release\YT-Pro.exe >nul

for /f "tokens=*" %%v in ('python -c "import ytpro; print(ytpro.__version__)"') do set VER=%%v
for /f "tokens=*" %%h in ('python -c "from ytpro.tools import sha256_of; print(sha256_of(r'release\YT-Pro.exe'))"') do set HASH=%%h
for /f "tokens=*" %%u in ('python -c "import ytpro; print(ytpro.UPDATE_URL)"') do set UPDURL=%%u

if "!UPDURL!"=="" (
    echo.
    echo WARNING: UPDATE_URL is empty in ytpro\__init__.py, so the built exe will
    echo          never check for updates. Set it to where latest.json will live,
    echo          then rebuild.
    echo.
)

REM The exe URL is assumed to sit beside latest.json on the same host.
python -c "import json,os,ytpro; u=ytpro.UPDATE_URL; base=u.rsplit('/',1)[0] if u else ''; json.dump({'version':ytpro.__version__,'url':(base+'/YT-Pro.exe') if base else 'PUT-THE-EXE-URL-HERE','sha256':os.environ['HASH'],'notes':'See the changelog.'}, open(r'release\latest.json','w'), indent=2)"

> release\SHA256SUMS.txt echo !HASH!  YT-Pro.exe

echo.
echo === release\ ===
dir /b release
echo.
echo Version : !VER!
echo SHA-256 : !HASH!
echo.
echo Upload the contents of release\ to your host. Check that latest.json's
echo "url" actually points at the uploaded exe before telling anyone.
endlocal
