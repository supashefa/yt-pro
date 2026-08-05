@echo off
REM Build YT-Pro.exe. Output lands in dist\YT-Pro.exe.
setlocal

echo.
echo === YT-Pro build ===
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo Python is not on PATH. Install it, then run this again.
    exit /b 1
)

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install --quiet pyinstaller
)

python -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo Installing customtkinter...
    python -m pip install --quiet -r requirements.txt
)

echo Cleaning previous build...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo Building...
python -m PyInstaller --noconfirm --clean YT-Pro.spec
if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    exit /b 1
)

echo.
echo Done: dist\YT-Pro.exe
dir /b dist
endlocal
