# Windows Desktop Helper

The Windows desktop helper is a Python application that runs on the presenter's Windows PC. It provides:

- **Global hotkey capture** (Ctrl+B) to take screenshots even when other apps are focused
- **Automatic screenshot upload** to Firebase Storage
- **Real-time overlay** showing student tap locations as purple dots
- **Firestore integration** for session management and student response monitoring

## Prerequisites

- **Windows 10/11** (required for Windows-specific APIs)
- **Python 3.11+** (tested with Python 3.11)
- **Firebase project** with Firestore and Storage enabled
- **Service account JSON** for Firebase Admin SDK access

## Installation

### 1. Set up Python environment

```cmd
cd helper
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Firebase credentials

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project → **Project Settings** → **Service Accounts**
3. Click **Generate New Private Key** and download the JSON file
4. Save it as `serviceAccount.json` in the `helper` folder

⚠️ **Important**: Never commit `serviceAccount.json` to version control!

### 3. Create configuration file

```cmd
copy config.example.json config.json
```

Edit `config.json` with your settings:

```json
{
  "session_id": "lecture-2025-09-17",
  "service_account_path": "serviceAccount.json",
  "storage_bucket": "your-project.appspot.com",
  "monitor_index": 0,
  "hotkey": "ctrl+b",
  "dot_color": "#8E4EC6",
  "dot_radius_px": 8,
  "fade_ms": 10000
}
```

**Configuration fields:**
- `session_id`: Unique ID for this presentation (students will use the same ID)
- `service_account_path`: Path to your Firebase service account JSON file
- `storage_bucket`: Your Firebase Storage bucket (usually `project-id.appspot.com`)
- `monitor_index`: Which monitor to capture (0 = primary, 1 = secondary, etc.)
- `hotkey`: Global hotkey (currently only "ctrl+b" is supported)
- `dot_color`: Color of student tap dots in hex format
- `dot_radius_px`: Size of tap dots in pixels
- `fade_ms`: How long dots stay visible (10000 = 10 seconds)

## Running the Helper

### From Source

```cmd
cd helper
.venv\Scripts\activate
python main.py
```

### Using the Compiled Executable

1. Download `slide_tap_helper.exe` from the GitHub Actions artifacts
2. Place it in the same folder as `config.json` and `serviceAccount.json`
3. Double-click to run

## How It Works

### Startup
1. Helper creates a transparent overlay window covering your selected monitor
2. Registers global hotkey (Ctrl+B) that works even when other apps have focus
3. Connects to Firestore to monitor session changes and student responses

### Taking a Screenshot (Ctrl+B)
1. Captures the current screen of your selected monitor
2. Uploads image to Firebase Storage
3. Updates Firestore with the new slide URL and index
4. Clears any existing overlay dots (fresh start for new slide)

### Displaying Student Taps
1. Monitors Firestore for new tap responses on the current slide
2. Converts normalized tap coordinates (0.0-1.0) to absolute screen pixels
3. Shows purple dots on the overlay at tap locations
4. Dots gradually fade out over the configured time period

### Overlay Window
- **Always on top**: Visible over all other applications
- **Click-through**: Mouse and keyboard events pass through to underlying apps
- **Transparent**: Only the purple dots are visible
- **Monitor-aware**: Correctly handles multiple monitors and DPI scaling

## Troubleshooting

### "Failed to register hotkey"
- Another application might be using Ctrl+B
- Try closing other presentation software or screen capture tools
- Some antivirus software may block hotkey registration

### "Screenshot capture failed"
- Check that `monitor_index` in config.json matches your setup
- Use `screeninfo.get_monitors()` to list available monitors
- Ensure you have permissions to access screen content

### "Firebase authentication failed"
- Verify `serviceAccount.json` path is correct
- Ensure the service account has Firestore and Storage permissions
- Check that the storage bucket name matches your project

### "Dots don't align with student taps"
- This usually happens after moving windows or changing screen resolution
- Press Ctrl+B to capture a fresh screenshot and reset alignment
- Ensure students are viewing the latest slide (check slide counter)

### Overlay not visible or clickable
- Check Windows display scaling settings
- Try running as Administrator if overlay doesn't appear
- Verify that Windows hasn't disabled layered windows

## Development

### Testing the Overlay
```cmd
python overlay.py
```
This runs a test with sample dots to verify overlay functionality.

### Building Executable Locally

**Windows (automated script):**
```cmd
build.bat
```

**Manual build:**
```cmd
pip install pyinstaller
pyinstaller slide_tap_helper.spec --clean --noconfirm
```

**Cross-platform testing (won't create working .exe):**
```bash
./build.sh
```

The build creates two versions:
- `slide_tap_helper.exe` - Windowed version (no console)
- `slide_tap_helper_debug.exe` - Console version for debugging

### Debug Logging
The helper logs to console. For more detailed logging:
- Edit the logging level in `main.py`
- Check Windows Event Viewer for system-level issues

### Building Executable
The GitHub Actions workflow automatically builds a Windows executable using PyInstaller. To build locally:

```cmd
pip install pyinstaller
pyinstaller --onefile --windowed --name slide_tap_helper main.py
```

## Security Notes

- The helper uses Firebase Admin SDK, bypassing Firestore security rules
- Only run the helper on trusted presenter machines
- Keep `serviceAccount.json` secure and never commit it to version control
- Students use Firebase Web SDK with security rules, so they can only read slides and write tap responses

## Known Limitations

- **Windows only**: Uses Windows-specific APIs for hotkeys and overlay
- **Single hotkey**: Currently hardcoded to Ctrl+B
- **No presentation mode detection**: Dots may not align if you switch apps after screenshot
- **DPI scaling**: May need adjustment on high-DPI displays
- **Firewall**: Windows Defender may prompt for network permissions on first run