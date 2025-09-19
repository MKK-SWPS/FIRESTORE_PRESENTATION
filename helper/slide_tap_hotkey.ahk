; Slide Tap Helper - AutoHotkey Script
; This script captures Ctrl+B and sends it to the Slide Tap Helper via HTTP
; 
; Installation:
; 1. Install AutoHotkey v2 from https://www.autohotkey.com/
; 2. Run this script (double-click or right-click -> Compile Script)
; 3. Make sure Slide Tap Helper is running (it listens on port 8889)
; 4. Press Ctrl+B to capture screenshots
;
; Version: 2025.09.19
; Compatible with: AutoHotkey v2

#Requires AutoHotkey v2.0
#SingleInstance Force

; Configuration
HELPER_BASE := "http://localhost:8889"
HELPER_CAPTURE_URL := HELPER_BASE . "/capture"
HELPER_PING_URL := HELPER_BASE . "/ping"
HELPER_PORT := 8889
HOTKEY_COMBO := "^b"  ; Ctrl+B

; Application info
APP_NAME := "Slide Tap Hotkey Helper"
APP_VERSION := "v2025.09.19"

; Tray icon setup
A_IconTip := APP_NAME . " " . APP_VERSION . "`nHotkey: Ctrl+B`nCapture: /capture`nPing: /ping"

; Create tray menu
TrayMenu := A_TrayMenu
TrayMenu.Delete()  ; Remove default items
TrayMenu.Add("&Test Connection", TestConnection)
TrayMenu.Add("&Status", ShowStatus)
TrayMenu.Add()  ; Separator
TrayMenu.Add("&Help", ShowHelp)
TrayMenu.Add()  ; Separator
TrayMenu.Add("E&xit", ExitApp)
TrayMenu.Default := "&Status"

; Global variables
LastTriggerTime := 0
TriggerCount := 0
ConnectionStatus := "Unknown"
Global CaptureCounter := 0

; Register the hotkey
try {
    Hotkey(HOTKEY_COMBO, TriggerScreenshot)
    ShowTrayTip("Hotkey Registered", "Ctrl+B active. Using /capture endpoint.", 3000)
    ; Perform a non-capturing ping only
    PingHelperSilent()
} catch Error as e {
    ShowTrayTip("Hotkey Error", "Failed to register Ctrl+B: " . e.Message, 5000, 3)
    ExitApp()
}

; Main hotkey function
TriggerScreenshot(*) {
    global LastTriggerTime, TriggerCount, HELPER_CAPTURE_URL, CaptureCounter
    
    ; Prevent rapid triggering (debounce)
    CurrentTime := A_TickCount
    if (CurrentTime - LastTriggerTime < 2000) {
        RemainingTime := Round((2000 - (CurrentTime - LastTriggerTime)) / 1000, 1)
        ShowTrayTip("Hotkey Cooldown", "Please wait " . RemainingTime . "s between captures", 2000, 2)
        return
    }
    
    LastTriggerTime := CurrentTime
    TriggerCount++
    CaptureCounter++
    
    ; Show immediate feedback
    ShowTrayTip("Capturing Screenshot", "Requesting /capture from helper...", 2000)
    
    ; Send HTTP request to helper
    try {
        ; Create HTTP request
        http := ComObject("WinHttp.WinHttpRequest.5.1")
        ; Build URL with cache buster & capture id
    url := HELPER_CAPTURE_URL . "?t=" . A_TickCount . "&cid=" . CaptureCounter
        http.Open("GET", url, false)
        http.SetRequestHeader("User-Agent", "Slide-Tap-Hotkey/" . APP_VERSION)
        ; Increase timeouts (resolve, connect, send, receive) to 15000ms
        http.SetTimeouts(15000, 15000, 15000, 15000)
        
        ; Send request
        http.Send()
        
        ; Check response
        if (http.Status == 200) {
            ResponseText := http.ResponseText
            ShowTrayTip("Screenshot Captured", "Request #" . TriggerCount . " sent successfully`n" . ResponseText, 3000, 1)
            ConnectionStatus := "Connected"
        } else {
            ShowTrayTip("Request Failed", "HTTP " . http.Status . ": " . http.StatusText, 4000, 3)
            ConnectionStatus := "Error"
        }
        
    } catch Error as e {
        ShowTrayTip("Connection Error", "Failed to reach Slide Tap Helper`n" . e.Message . "`n`nIs the helper running?", 5000, 3)
        ConnectionStatus := "Disconnected"
    }
}

; Test connection function
TestConnection(*) {
    global HELPER_PING_URL, ConnectionStatus
    
    ShowTrayTip("Testing Connection", "Pinging helper (no capture)...", 2000)
    
    try {
        http := ComObject("WinHttp.WinHttpRequest.5.1")
    http.Open("GET", HELPER_PING_URL, false)
    http.SetRequestHeader("User-Agent", "Slide-Tap-Hotkey/" . APP_VERSION . " (ping)")
        http.SetTimeouts(3000, 3000, 3000, 3000)
        http.Send()
        
        if (http.Status == 200) {
            ShowTrayTip("Connection Test", "✓ Successfully connected to Slide Tap Helper", 3000, 1)
            ConnectionStatus := "Connected"
        } else {
            ShowTrayTip("Connection Test", "⚠ Helper responded with HTTP " . http.Status, 3000, 2)
            ConnectionStatus := "Warning"
        }
        
    } catch Error as e {
        ShowTrayTip("Connection Test", "✗ Cannot reach Slide Tap Helper`n" . e.Message, 4000, 3)
        ConnectionStatus := "Disconnected"
    }
}

; Silent connection test (no notifications)
PingHelperSilent() {
    global HELPER_PING_URL, ConnectionStatus
    try {
        http := ComObject("WinHttp.WinHttpRequest.5.1")
        http.Open("GET", HELPER_PING_URL, false)
        http.SetRequestHeader("User-Agent", "Slide-Tap-Hotkey/" . APP_VERSION . " (silent-ping)")
        http.SetTimeouts(2000, 2000, 2000, 2000)
        http.Send()
        ConnectionStatus := (http.Status == 200) ? "Connected" : "Warning"
    } catch {
        ConnectionStatus := "Disconnected"
    }
}

; Show status information
ShowStatus(*) {
    global TriggerCount, LastTriggerTime, ConnectionStatus, HELPER_CAPTURE_URL, HOTKEY_COMBO
    
    StatusText := APP_NAME . " " . APP_VERSION . "`n`n"
    StatusText .= "Hotkey: " . HOTKEY_COMBO . "`n"
    StatusText .= "Capture: " . HELPER_CAPTURE_URL . "`n"
    StatusText .= "Ping: " . HELPER_PING_URL . "`n"
    StatusText .= "Status: " . ConnectionStatus . "`n"
    StatusText .= "Triggers: " . TriggerCount . "`n"
    
    if (TriggerCount > 0) {
        TimeSince := Round((A_TickCount - LastTriggerTime) / 1000, 1)
        StatusText .= "Last trigger: " . TimeSince . "s ago"
    }
    
    MsgBox(StatusText, APP_NAME . " - Status", "T10")
}

; Show help information
ShowHelp(*) {
    HelpText := APP_NAME . " " . APP_VERSION . "`n`n"
    HelpText .= "This script captures Ctrl+B and forwards it to the Slide Tap Helper.`n`n"
    HelpText .= "Usage:`n"
    HelpText .= "• Press Ctrl+B to capture a screenshot`n"
    HelpText .= "• Right-click tray icon for options`n"
    HelpText .= "• Test Connection to verify helper is running`n`n"
    HelpText .= "Requirements:`n"
    HelpText .= "• Slide Tap Helper must be running`n"
    HelpText .= "• Helper must be listening on port " . HELPER_PORT . "`n`n"
    HelpText .= "Troubleshooting:`n"
    HelpText .= "• Check Windows Firewall settings`n"
    HelpText .= "• Verify helper is not blocked by antivirus`n"
    HelpText .= "• Make sure port " . HELPER_PORT . " is available"
    
    MsgBox(HelpText, APP_NAME . " - Help", "T15")
}

; Enhanced tray tip function
ShowTrayTip(Title, Text, Duration := 3000, IconType := 1) {
    ; IconType: 1=Info, 2=Warning, 3=Error
    TrayTip(Text, Title, IconType)
    
    ; Auto-hide after duration
    if (Duration > 0) {
        SetTimer(() => TrayTip(), -Duration)
    }
}

; Periodic connection check (every 30 seconds)
SetTimer(PingHelperSilent, 30000)

; Clean exit
ExitApp(*) {
    ShowTrayTip("Exiting", "Slide Tap Hotkey Helper is shutting down", 1000)
    Sleep(1000)
    ExitApp()
}