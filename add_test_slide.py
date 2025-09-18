"""
Quick test script to add a dummy slide to your Firestore session
This allows students to start tapping for testing purposes.
"""

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import ArrayUnion, SERVER_TIMESTAMP

# Initialize Firebase (update path to your service account file)
cred = credentials.Certificate('serviceAccount.json')
firebase_admin.initialize_app(cred)

db = firestore.client()
session_id = 'lecture-2025-09-18'

# Add a simple test slide (using a placeholder image)
test_slide_url = 'https://via.placeholder.com/1920x1080/2E3440/88C0D0?text=Test+Slide+%E2%80%A2+Click+anywhere+to+test'

session_ref = db.collection('sessions').document(session_id)
session_ref.set({
    'slides': ArrayUnion([test_slide_url]),
    'slideIndex': 0,
    'screenshotMeta': {
        'width': 1920,
        'height': 1080,
        'monitorIndex': 0
    },
    'lastUpdated': SERVER_TIMESTAMP
}, merge=True)

print(f"✅ Added test slide to session: {session_id}")
print(f"🌐 Students can now visit: https://mkk-swps.github.io/FIRESTORE_PRESENTATION/student.html")
print(f"🖱️ They should see the test slide and be able to click to create dots!")
print(f"👀 Check your Windows desktop app - dots should appear when students click!")