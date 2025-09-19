# AutoHotkey Integration for Slide Tap Helper

This document explains how to set up the AutoHotkey script for global Ctrl+B hotkey support.

## What is AutoHotkey?

AutoHotkey is a powerful Windows automation scripting language that can capture global hotkeys and perform actions. Since Windows security restrictions prevent applications from registering global hotkeys reliably, we use AutoHotkey as a bridge.

## Setup Instructions

### 1. Install AutoHotkey v2

1. Download AutoHotkey v2 from: https://www.autohotkey.com/
2. Install the latest version (requires v2.0 or higher)
3. Verify installation by right-clicking any `.ahk` file - you should see AutoHotkey options

### 2. Run the Script

**Method A: Direct execution**
1. Double-click `slide_tap_hotkey.ahk` to run it directly
2. Look for the script icon in your system tray

**Method B: Compile to executable**
1. Right-click `slide_tap_hotkey.ahk`
2. Select "Compile Script" from the context menu
3. Run the generated `slide_tap_hotkey.exe`

### 3. Verify Setup

1. Make sure **Slide Tap Helper** is running first
2. Run the AutoHotkey script
3. Right-click the tray icon and select "Test Connection"
4. You should see "✓ Successfully connected to Slide Tap Helper"

## Usage

- **Press Ctrl+B** to capture a screenshot (same as the original hotkey)
- **Right-click tray icon** for options:
  - Test Connection - Check if helper is reachable
  - Status - View connection info and trigger count
  - Help - Show usage instructions
  - Exit - Close the script

## Features

### Smart Connection Detection
- Automatically tests connection every 30 seconds
- Shows connection status in tray tooltips
- Provides detailed error messages if helper is unreachable

### Hotkey Protection
- 1-second cooldown prevents accidental rapid triggers
- Visual feedback via system tray notifications
- Counts successful screenshot captures

### User-Friendly Interface
- System tray integration with helpful tooltips
- Right-click menu with all functions
- Auto-hides tray notifications after a few seconds

## Troubleshooting

### "Connection Error" or "Cannot reach Slide Tap Helper"

**Possible causes:**
1. **Slide Tap Helper not running** - Start the helper first
2. **Port 8889 blocked** - Check Windows Firewall settings
3. **Antivirus blocking** - Add exclusion for both helper and AutoHotkey script

**Solutions:**
1. Verify helper is running and shows "HTTP trigger server started on http://localhost:8889"
2. Try visiting http://localhost:8889 in your browser - should show screenshot capture page
3. Temporarily disable Windows Firewall to test
4. Add firewall exception for port 8889

### "Hotkey Error" or Ctrl+B not working

**Possible causes:**
1. **Another program using Ctrl+B** - Some applications reserve this hotkey
2. **AutoHotkey permission issues** - Run as administrator
3. **Outdated AutoHotkey version** - Requires v2.0+

**Solutions:**
1. Close other applications that might use Ctrl+B
2. Right-click AutoHotkey script and "Run as administrator"
3. Update to AutoHotkey v2.0 from https://www.autohotkey.com/

### Script won't start or compile

**Possible causes:**
1. **AutoHotkey v1 instead of v2** - Script requires v2 syntax
2. **Missing AutoHotkey installation** - Download from official site

**Solutions:**
1. Uninstall old AutoHotkey v1 and install v2
2. Verify installation: right-click .ahk file should show AutoHotkey options

## Technical Details

### Communication Method
- AutoHotkey sends HTTP GET request to `http://localhost:8889`
- Helper receives request and triggers screenshot capture
- Response confirms successful capture

### Error Handling
- 5-second timeout for HTTP requests
- Automatic retry logic for temporary connection issues
- Detailed error messages in tray notifications

### Performance
- Minimal CPU usage when idle
- Fast response time (typically <100ms)
- No file system polling or temporary files

## Advanced Configuration

To modify the hotkey or port, edit these lines in `slide_tap_hotkey.ahk`:

```autohotkey
; Change hotkey (use AutoHotkey syntax)
HOTKEY_COMBO := "^b"        ; Ctrl+B (default)
; HOTKEY_COMBO := "^j"      ; Ctrl+J (alternative)
; HOTKEY_COMBO := "F12"     ; F12 key

; Change target port
HELPER_PORT := 8889         ; Default port
```

## Security Notes

- AutoHotkey script only sends local HTTP requests (localhost)
- No external network access or data collection
- Script source code is fully visible and editable
- Can be compiled to standalone executable for easier distribution

## Auto-Start on Windows Boot

To automatically start the script when Windows boots:

1. Press `Win+R`, type `shell:startup`, press Enter
2. Copy `slide_tap_hotkey.ahk` (or compiled `.exe`) to this folder
3. Script will start automatically on next boot

**Note:** Make sure Slide Tap Helper also starts automatically, or the script will show connection errors until you start the helper manually.