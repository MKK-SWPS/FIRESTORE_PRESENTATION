@echo off
echo Killing all slide_tap_helper processes...
taskkill /F /IM slide_tap_helper.exe 2>nul
taskkill /F /IM slide_tap_helper_debug.exe 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *helper*" 2>nul
echo Done! All helper processes terminated.
pause