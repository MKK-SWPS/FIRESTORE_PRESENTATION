#!/bin/bash
# Build script for Slide Tap Helper (for development/testing only - Windows .exe requires Windows)
# This won't create the .exe but can test PyInstaller on other platforms

echo "Building Slide Tap Helper (development build)..."
echo

# Check if we're in the right directory
if [[ ! -f "main.py" ]]; then
    echo "Error: main.py not found. Make sure you're running this from the helper directory."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [[ ! -d ".venv" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Create version info
echo "Creating version info..."
python3 -c "
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

# Note about Windows-only nature
echo
echo "Note: This helper is Windows-only and requires Windows APIs."
echo "PyInstaller will create a binary for the current platform, but it won't work without Windows."
echo "Use GitHub Actions or a Windows machine to create the actual .exe file."
echo

# Build with PyInstaller (will create platform-specific executable)
echo "Building executable (platform-specific)..."
pyinstaller slide_tap_helper.spec --clean --noconfirm

# Check result
if [[ -f "dist/slide_tap_helper" ]] || [[ -f "dist/slide_tap_helper.exe" ]]; then
    echo
    echo "✅ Build completed!"
    echo "Location: $(pwd)/dist/"
    ls -la dist/
    echo
    echo "Remember: This helper requires Windows to run properly."
else
    echo
    echo "❌ Build failed!"
    echo "Check the output above for error details."
fi