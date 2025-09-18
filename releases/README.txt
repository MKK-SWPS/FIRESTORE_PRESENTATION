# Slide Tap Helper - Windows Executable

Build: 2025.09.18.8dd4270
Built: 2025-09-18 12:33:12 UTC
Commit: 8dd427001602b1c5047f5483d27efe4c20d86370

## Files Included

- \slide_tap_helper.exe\ - Main application (windowed, no console)
- \slide_tap_helper_debug.exe\ - Debug version (shows console for troubleshooting)
- \config.example.json\ - Configuration template

## Quick Start

1. Create \config.json\ by copying \config.example.json\
2. Download your Firebase service account JSON and save as \serviceAccount.json\
3. Edit \config.json\ with your Firebase project details
4. Run \slide_tap_helper.exe\

## Troubleshooting

If the main executable doesn't work or you need to see error messages:
1. Run \slide_tap_helper_debug.exe\ instead
2. Check the console output for error details
3. Ensure Windows allows network access
4. Verify Firebase project settings

See the full documentation at: https://github.com/MKK-SWPS/FIRESTORE_PRESENTATION

## Security Notes

- \serviceAccount.json\ contains sensitive credentials
- Never share or commit this file to version control
- Keep it in the same folder as the executable

