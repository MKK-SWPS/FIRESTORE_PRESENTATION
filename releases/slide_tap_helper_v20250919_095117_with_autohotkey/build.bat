@echo off
REM Build script for Slide Tap Helper Windows executable
REM Run this from the helper directory

echo Building Slide Tap Helper...
echo.

REM Check if we're in the right directory
if not exist "main.py" (
    echo Error: main.py not found. Make sure you're running this from the helper directory.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

REM Create version info
echo Creating version info...
python -c "
import datetime
import subprocess
try:
    commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd='..').decode().strip()
except:
    commit = 'unknown'
version_info = f'''VERSION_INFO = {{
    'version': '{datetime.date.today().strftime('%Y.%m.%d')}.{commit}',
    'build_date': '{datetime.date.today().strftime('%Y.%m.%d')}',
    'commit': '{commit}',
    'branch': 'local'
}}'''
with open('version_info.py', 'w') as f:
    f.write(version_info)
"

REM Build with PyInstaller
echo Building executable...
pyinstaller slide_tap_helper.spec --clean --noconfirm

REM Check if build was successful
if exist "dist\slide_tap_helper.exe" (
    echo.
    echo ✅ Build successful!
    for %%I in (dist\slide_tap_helper.exe) do echo Executable size: %%~zI bytes
    echo Location: %CD%\dist\slide_tap_helper.exe
    echo.
    echo Don't forget to:
    echo 1. Copy config.example.json to config.json and edit it
    echo 2. Add your serviceAccount.json file
    echo 3. Test the executable
    echo.
) else (
    echo.
    echo ❌ Build failed!
    echo Check the output above for error details.
    echo.
)

pause