"""
Alternative trigger methods for screenshot capture when hotkeys don't work
"""

import threading
import time
import json
import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Import the main helper functions
try:
    from main import capture_screenshot, upload_to_storage, update_session_state
except ImportError:
    # Fallback imports if main is not available
    def capture_screenshot():
        return "dummy_screenshot.png"
    
    def upload_to_storage(path):
        return "http://dummy-url.com/image.png"
    
    def update_session_state(url):
        pass

# Global variables for HTTP trigger cooldown
last_http_trigger_time = 0
HTTP_TRIGGER_COOLDOWN_MS = 2000  # 2 second cooldown between captures

logger = logging.getLogger(__name__)


def handle_http_trigger():
    """Handle HTTP trigger for screenshot capture with cooldown protection."""
    global last_http_trigger_time
    
    current_time = time.time() * 1000  # milliseconds
    
    # Check cooldown
    if current_time - last_http_trigger_time < HTTP_TRIGGER_COOLDOWN_MS:
        cooldown_remaining = int((HTTP_TRIGGER_COOLDOWN_MS - (current_time - last_http_trigger_time)) / 1000)
        print(f"⏰ HTTP trigger cooldown active - {cooldown_remaining}s remaining")
        return f"Cooldown active - please wait {cooldown_remaining} seconds"
    
    # Update last trigger time
    last_http_trigger_time = current_time
    
    print("📸 HTTP trigger activated - capturing screenshot...")
    
    try:
        # Capture screenshot
        screenshot_path = capture_screenshot()
        print(f"📷 Screenshot captured: {screenshot_path}")
        
        # Upload to Firebase Storage
        image_url = upload_to_storage(screenshot_path)
        print(f"☁️ Uploaded to storage: {image_url}")
        
        # Update session state in Firestore
        update_session_state(image_url)
        print("🔄 Session state updated")
        
        print("✅ Screenshot capture and upload completed successfully")
        return "Screenshot captured and uploaded successfully!"
        
    except Exception as e:
        print(f"❌ HTTP trigger failed: {e}")
        return f"Error: {str(e)}"


class ScreenshotHTTPServer:
    """Simple HTTP server that triggers screenshot on GET request."""
    
    def __init__(self, port=8889, callback=None):
        self.port = port
        self.callback = callback
        self.server = None
        self.thread = None
        
    class ScreenshotHandler(SimpleHTTPRequestHandler):
        def __init__(self, request, client_address, server, callback=None):
            self.screenshot_callback = callback
            super().__init__(request, client_address, server)
            
        def do_GET(self):
            if self.path == '/capture' or self.path == '/':
                try:
                    # Use the new handle_http_trigger function with cooldown
                    result = handle_http_trigger()
                    
                    # Detect if request is from AutoHotkey
                    user_agent = self.headers.get('User-Agent', '')
                    is_autohotkey = 'Slide-Tap-Hotkey' in user_agent
                    
                    # Send success response
                    self.send_response(200)
                    
                    if is_autohotkey:
                        # Simple text response for AutoHotkey
                        self.send_header('Content-type', 'text/plain; charset=utf-8')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        
                        self.wfile.write(result.encode('utf-8'))
                        logger.info(f"Screenshot triggered via AutoHotkey: {user_agent}")
                        
                    else:
                        # HTML response for browsers
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        
                        # Simple HTML response without complex styling that might cause parsing issues
                        port = self.server.server_address[1]
                        response_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Screenshot Result</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="background: #2E3440; color: white; text-align: center; padding: 50px;">
    <h1>Screenshot Trigger</h1>
    <p style="color: #A3BE8C; font-size: 18px;">{result}</p>
    <button onclick="location.reload()" style="background: #5E81AC; color: white; border: none; padding: 15px 30px; font-size: 16px; cursor: pointer;">Try Again</button>
    <hr style="margin: 40px 0; border-color: #4C566A;">
    <h3>Bookmark This Page</h3>
    <p>Quick access: <strong>http://localhost:{port}</strong></p>
    <h3>AutoHotkey Integration</h3>
    <p>For Ctrl+B hotkey support, run: <strong>slide_tap_hotkey.ahk</strong></p>
</body>
</html>"""
                        
                        self.wfile.write(response_html.encode('utf-8'))
                        logger.info("Screenshot triggered via browser")
                    
                except Exception as e:
                    logger.error(f"HTTP trigger error: {e}")
                    self.send_error(500, f"Screenshot capture failed: {str(e)}")
            else:
                self.send_error(404, "Use / to trigger screenshot capture")
                
        def log_message(self, format, *args):
            # Reduce HTTP server logging noise
            pass
    
    def start(self):
        """Start the HTTP server in a background thread."""
        try:
            def handler_factory(callback):
                class Handler(self.ScreenshotHandler):
                    def __init__(self, request, client_address, server):
                        super().__init__(request, client_address, server, callback=callback)
                return Handler
            
            handler_class = handler_factory(self.callback)
            self.server = HTTPServer(('localhost', self.port), handler_class)
            
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            
            logger.info(f"HTTP trigger server started on http://localhost:{self.port}")
            logger.info(f"Bookmark this URL for quick screenshot capture!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
            return False
    
    def stop(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("HTTP trigger server stopped")


class FileWatcherTrigger:
    """Trigger screenshot by creating/touching a specific file."""
    
    def __init__(self, trigger_file="capture_now.txt", callback=None):
        self.trigger_file = trigger_file
        self.callback = callback
        self.running = False
        self.thread = None
        self.last_modified = 0
        
    def start(self):
        """Start watching for the trigger file."""
        self.running = True
        self.thread = threading.Thread(target=self._watch_file, daemon=True)
        self.thread.start()
        
        logger.info(f"File trigger started - create/touch '{self.trigger_file}' to capture screenshot")
        logger.info(f"Quick command: echo . > {self.trigger_file}")
        
    def _watch_file(self):
        """Watch for file changes."""
        while self.running:
            try:
                if os.path.exists(self.trigger_file):
                    current_modified = os.path.getmtime(self.trigger_file)
                    
                    if current_modified > self.last_modified:
                        self.last_modified = current_modified
                        logger.info(f"Trigger file detected - capturing screenshot")
                        
                        if self.callback:
                            self.callback()
                        
                        # Clean up the trigger file
                        try:
                            os.remove(self.trigger_file)
                        except:
                            pass
                
                time.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                logger.error(f"File watcher error: {e}")
                time.sleep(1)
    
    def stop(self):
        """Stop watching for the trigger file."""
        self.running = False
        if os.path.exists(self.trigger_file):
            try:
                os.remove(self.trigger_file)
            except:
                pass