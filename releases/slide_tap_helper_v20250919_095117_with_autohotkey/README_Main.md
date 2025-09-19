# Student Tap Interactive Presenta### Step 1: Firebase Setup ✅ (Already Done)

Your Firebase project `firestore-presentation-27ee4` is already configured! Just make sure:

1. **Firestore Database** is in Native mode ✅
2. **Storage** is enabled ✅  
3. **Authentication** → Anonymous is enabled ✅
4. **Add authorized domain**: Go to Authentication → Settings → Authorized domains → Add `mkk-swps.github.io`

### Step 2: Deploy Security Rules

Deploy the included security rules to your Firebase project:

```bash
# Install Firebase CLI if you haven't already
npm install -g firebase-tools

# Login to Firebase
firebase login

# Initialize project (choose existing project: firestore-presentation-27ee4)
firebase init

# Deploy rules
firebase deploy --only firestore:rules,storage
```

Or manually copy the contents of `firestore.rules` and `storage.rules` to your Firebase Console → Firestore/Storage → Rules.

### Step 3: Configure Student Page ✅ (Already Done)ure Authentication**:
   - Go to Authentication → Settings → Authorized domains
   - Add your GitHub Pages domain: `mkk-swps.github.io`m

A minimal system for interactive presentations where students can tap/click on slides to send feedback points, and presenters see real-time tap locations overlaid on their screen.

## 🎯 Quick Overview

- **Students**: Open a web page, see live slides, tap to send points
- **Presenter**: Press Ctrl+B to capture screen, see student taps as purple dots
- **Backend**: Firebase (Firestore + Storage) handles everything
- **Hosting**: GitHub Pages for the student web page

## 🏗 System Components

### 1. Student Web Page (`student.html`)
- Single HTML file with Firebase Web SDK
- Real-time slide viewing with 16:9 letterboxing
- Touch/click to send normalized coordinates
- Mobile-friendly, no frameworks required

### 2. Windows Desktop Helper (`helper/`)
- Global hotkey (Ctrl+B) for screen capture
- Transparent click-through overlay with purple tap dots
- Firebase Admin SDK for uploading slides and reading responses
- Compiled to single `.exe` file via GitHub Actions

### 3. Firebase Backend
- **Firestore**: Session state, slide indices, tap responses
- **Storage**: Screenshot images with public read access
- **Security Rules**: Demo-permissive, production-ready templates included

## 🚀 Getting Started

### Step 1: Set up Firebase

1. **Create Firebase project** at [console.firebase.google.com](https://console.firebase.google.com)

2. **Enable services**:
   - Firestore Database (Native mode)
   - Storage
   - Authentication → Sign-in method → Anonymous ✅

3. **Configure Authentication**:
   - Go to Authentication → Settings → Authorized domains
   - Add your GitHub Pages domain: `<username>.github.io`

4. **Get Web configuration**:
   - Project Settings → General → Your apps → Web app
   - Copy the config object

### Step 2: Configure Student Page

The student page is already configured with your Firebase project settings!

### Step 4: Deploy Student Page

**GitHub Pages (Recommended)**:
1. Push to GitHub (already done! ✅)
2. Go to Settings → Pages → Source: Deploy from a branch → `main` (root)
3. Student URL: `https://mkk-swps.github.io/FIRESTORE_PRESENTATION/student.html`

**Alternative - Firebase Hosting**:

### Step 3: Deploy Student Page

**Option A: GitHub Pages**
1. Push this repository to GitHub
2. Go to Settings → Pages → Source: Deploy from a branch → `main` (root)
3. Student URL: `https://mkk-swps.github.io/FIRESTORE_PRESENTATION/student.html`

**Option B: Firebase Hosting**
```bash
npm install -g firebase-tools
firebase login
firebase init hosting
firebase deploy
```

### Step 5: Set up Windows Helper

#### Download Pre-built Executable
1. Go to [Actions](../../actions) tab and find the latest successful build
2. Download `slide_tap_helper_distribution_*.zip` artifact
3. Extract to a folder on your Windows PC

**What's included:**
- `slide_tap_helper.exe` - Main application (windowed, no console)  
- `slide_tap_helper_debug.exe` - Debug version (shows console for troubleshooting)
- `config.example.json` - Configuration template
- `README.txt` - Quick start guide

#### Configure Helper
1. **Get service account**:
   - Firebase Console → Project Settings → Service Accounts
   - Generate New Private Key → Download JSON
   - Save as `serviceAccount.json` in the helper folder

2. **Create configuration**:
   ```cmd
   copy config.example.json config.json
   ```
   
3. **Edit `config.json`**:
   ```json
   {
     "session_id": "lecture-2025-09-18",
     "service_account_path": "serviceAccount.json",
     "storage_bucket": "firestore-presentation-27ee4.firebasestorage.app",
     "monitor_index": 0,
     "hotkey": "ctrl+b",
     "dot_color": "#8E4EC6",
     "dot_radius_px": 8,
     "fade_ms": 10000
   }
   ```

#### Run Helper
- Double-click `slide_tap_helper.exe`
- Or run from command prompt to see logs

## 📱 How to Use

### For Students
1. Open the student page URL on any device
2. See "Connected" status and current slide
3. Tap anywhere on the slide image to send feedback
4. Watch slide updates in real-time

### For Presenters
1. Start the Windows helper (overlay appears on your screen)
2. Present normally in any application
3. **Press Ctrl+B** to capture current screen and advance slide
4. See purple dots appear where students tap
5. Dots fade after 10 seconds (configurable)

## 🧪 Test Plan

1. **Start helper** → Transparent overlay appears on screen
2. **Press Ctrl+B** → Screenshot uploads, students see new slide
3. **Student taps** → Purple dots appear at correct locations within ~1 second
4. **Press Ctrl+B again** → Overlay dots clear, new screenshot shown
5. **Student taps** → New dots appear for the new slide

## 🔒 Security & Rules

The included `firestore.rules` and `storage.rules` are **demo-permissive** for easy setup:

- ✅ Anonymous users can read session data and slides
- ✅ Anonymous users can write tap responses with validation
- ❌ Anonymous users cannot write slides or control session state
- ✅ Helper uses Admin SDK to bypass rules for presenter actions

**For production**, consider:
- User authentication beyond anonymous
- Session allowlists or time-based restrictions  
- Rate limiting for tap responses
- Cleanup policies for old slides

## 📁 Project Structure

```
/
├── README.md                     # This file
├── .gitignore                    # Excludes secrets and build files
├── student.html                  # Student web interface (single file)
├── firestore.rules              # Firestore security rules
├── storage.rules                # Storage security rules
│
├── helper/                       # Windows desktop application
│   ├── main.py                   # Entry point and orchestration
│   ├── overlay.py                # Transparent overlay window
│   ├── config.example.json       # Configuration template
│   ├── requirements.txt          # Python dependencies
│   └── README.md                 # Helper-specific documentation
│
└── .github/workflows/
    └── windows-build.yml         # CI to build Windows .exe
```

## 🔧 Development

### Run Helper from Source
```cmd
cd helper
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Test Overlay Only
```cmd
cd helper
python overlay.py
```

### Build Executable Locally
```cmd
cd helper
build.bat  # Windows
# or
./build.sh  # Linux/Mac (for testing only)
```

### Trigger GitHub Actions Build
1. Go to [Actions](../../actions) tab
2. Click "Build Windows Helper Executable"
3. Click "Run workflow" → "Run workflow"
4. Wait for build to complete
5. Download artifact from the completed workflow

## 🐛 Troubleshooting

### Common Issues

**"Failed to register hotkey"**
- Another app is using Ctrl+B (close screen recorders, presentation software)
- Try running as Administrator

**"Dots don't align with student taps"**
- Press Ctrl+B to recapture after moving windows
- Check that students are viewing the latest slide number

**"Student page shows 'Session not found'"**
- Presenter hasn't captured first screenshot yet
- Check that `SESSION_ID` matches in both student.html and config.json

**"Authentication failed"**
- Verify GitHub Pages domain in Firebase Auth settings
- Check that anonymous auth is enabled

**"Firebase permission denied"**
- Ensure service account JSON is correct
- Check Firestore/Storage rules are deployed
- Verify storage bucket name in config

### Debug Steps

1. **Check student page console** (F12) for Firebase errors
2. **Run helper from command line** to see log messages
3. **Verify Firebase configuration** in console.firebase.google.com
4. **Test with single student** before large groups

## ⚙️ Configuration Reference

### Student Page Constants
- `FIREBASE_CONFIG`: Firebase project configuration object
- `SESSION_ID`: Unique session identifier (must match helper config)

### Helper Configuration (key fields)
- `session_id`: Session identifier (matches student page)
- `service_account_path`: Path to Firebase Admin SDK JSON file
- `storage_bucket`: Firebase Storage bucket name
- `monitor_index`: Which monitor to capture (0 = primary)
- `dot_color`: Hex color for tap dots (e.g., "#8E4EC6")
- `dot_radius_px`: Dot size in pixels
- `fade_ms`: Dot fade duration in milliseconds

### New reliability / debugging options
- `enable_hotkey` (bool): If false, skip global hotkey registration entirely (use HTTP/file triggers)
- `overlay_mode` (auto | simple | layered): Select overlay strategy. `auto` tries layered then falls back to simple.
- `overlay_debug_bg` (bool): Draws translucent dark background to visually confirm overlay presence.
- `ignore_past_responses_seconds`: Ignore stale Firestore responses older than this many seconds before startup (prevents replay spam after restart).
- `http_trigger_port`: Port for HTTP screenshot trigger (GET /)
- `trigger_file`: Filename to create/touch to trigger screenshot capture.

You can always capture without the hotkey by either:
1. Visiting http://localhost:8889 (default port) in a browser
2. Creating an empty file named `capture_now.txt` in the helper folder

## 🚨 Important Security Notes

- **Never commit** `serviceAccount.json` or `config.json` to version control
- The helper uses **Firebase Admin SDK** and bypasses security rules
- Only run the helper on **trusted presenter machines**
- Student access is controlled by **Firestore security rules**
- Consider **additional authentication** for production use

## 📝 Known Limitations

- **Windows only**: Helper uses Windows-specific APIs
- **Single hotkey**: Currently hardcoded to Ctrl+B
- **Monitor alignment**: Dots may not align if you switch apps after screenshot
- **DPI scaling**: May need adjustment on high-DPI displays
- **No presentation mode detection**: Works with any application

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test on Windows with Firebase
5. Submit a pull request

## 📄 License

This project is provided as-is for educational and demonstration purposes. Modify and distribute freely.

---

**Need help?** Check the [helper README](helper/README.md) for detailed Windows setup instructions.