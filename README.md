# Slide Heatmap (Presenter/Student)

Two static pages with Firebase Firestore realtime sync.

- `presenter.html` — Next/Prev slides + live heatmap of taps.
- `student.html` — tap anywhere to submit immediately.

## Setup
1. Create a Firebase project → enable **Firestore** + **Anonymous Auth**.
2. Copy your config into both HTML files (`FIREBASE_CONFIG`).
3. Set `SESSION_ID` (any string to isolate a lecture).
4. Export slides to images; set `SLIDE_IMAGES` arrays to those file paths.
5. Host the folder (GitHub Pages, Netlify, Firebase Hosting, etc.).
6. Add your host domain to **Firebase Auth → Authorized domains**.

## Notes
- Taps are stored under `sessions/{SESSION_ID}/slides/{index}/responses`.
- Heatmap auto-clears on slide change because we re-subscribe to the new slide's collection.