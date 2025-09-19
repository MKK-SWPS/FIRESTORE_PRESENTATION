# Slide Tap Helper v20250919_095117 - with AutoHotkey Integration

This release includes the new AutoHotkey integration feature for reliable global hotkey support.

## What's New
- **AutoHotkey Integration**: Reliable Ctrl+B global hotkey using AutoHotkey script
- **Enhanced HTTP Server**: Smart detection of AutoHotkey vs browser requests
- **System Tray Integration**: Full Windows tray application with connection monitoring
- **Improved Distribution**: AutoHotkey script and documentation included in build

## Quick Start

### Option 1: Use with AutoHotkey (Recommended)
1. Install AutoHotkey v2 from https://www.autohotkey.com/
2. Build the helper executable using `build.bat`
3. Run the helper executable (it will start the HTTP server)
4. Double-click `slide_tap_hotkey.ahk` to start the hotkey script
5. Press Ctrl+B anywhere in Windows to trigger a screenshot

### Option 2: Use HTTP Trigger Directly
1. Build and run the helper executable
2. Open http://localhost:8889 in your browser
3. Click the button to trigger screenshots

## Files Included

### Core Application
- `main.py`: Main helper application
- `overlay.py`: Screenshot overlay system  
- `alternative_triggers.py`: HTTP trigger server
- `config.example.json`: Configuration template
- `requirements.txt`: Python dependencies
- `slide_tap_helper.spec`: PyInstaller build configuration

### AutoHotkey Integration
- `slide_tap_hotkey.ahk`: AutoHotkey v2 script for global Ctrl+B hotkey
- `AutoHotkey_README.md`: Detailed AutoHotkey setup and troubleshooting guide

### Build Tools
- `build.bat`: Windows build script (creates slide_tap_helper.exe)
- `README.md`: Core helper documentation

## Building Instructions

### On Windows:
1. Run `build.bat` to create `slide_tap_helper.exe`
2. The executable will be in the `dist` folder

### On Linux (for development):
Note: This will create a Linux binary that won't work on Windows
```bash
./build.sh
```

## AutoHotkey Setup

1. **Install AutoHotkey v2** from https://www.autohotkey.com/
2. **Start the Helper**: Run `slide_tap_helper.exe`
3. **Start AutoHotkey Script**: Double-click `slide_tap_hotkey.ahk`
4. **Look for Tray Icon**: The AutoHotkey script will appear in your system tray
5. **Test Connection**: Right-click the tray icon and select "Test Connection"
6. **Use Hotkey**: Press Ctrl+B anywhere to trigger screenshots

## Troubleshooting

### AutoHotkey Issues
- See `AutoHotkey_README.md` for detailed troubleshooting
- Ensure AutoHotkey v2 is installed (not v1)
- Check that the helper is running on port 8889
- Try running both programs as administrator if needed

### Helper Issues  
- Make sure port 8889 is not in use by other applications
- Check Windows Firewall settings
- Try running as administrator

## Technical Details

### Architecture
- **Helper**: Python application with HTTP server on localhost:8889
- **AutoHotkey Script**: Captures Ctrl+B globally and sends HTTP request to helper
- **Communication**: HTTP GET request triggers screenshot capture
- **Tray Integration**: AutoHotkey provides system tray with status and controls

### Security
- Only listens on localhost (127.0.0.1)
- No external network access required
- AutoHotkey script only captures Ctrl+B hotkey
- HTTP requests are simple GET requests with no data transmission

## Version Information
- **Release Date**: 2025-09-19 09:51:17
- **Features**: AutoHotkey integration, system tray, enhanced HTTP server
- **Platform**: Windows (requires Windows APIs and AutoHotkey v2)

---

For detailed AutoHotkey setup and troubleshooting, see `AutoHotkey_README.md`.
For core helper documentation, see `README.md`.
