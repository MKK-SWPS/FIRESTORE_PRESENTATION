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
trigger_counter = 0

logger = logging.getLogger(__name__)


def handle_http_trigger(callback=None):
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
        if callback:
            # Use the callback function provided by the main application
            callback()
            print("✅ Screenshot capture completed via callback")
            return "Screenshot captured and uploaded successfully!"
        else:
            # Fallback to direct imports (this should not be used in normal operation)
            screenshot_path = capture_screenshot()
            print(f"📷 Screenshot captured: {screenshot_path}")
            
            image_url = upload_to_storage(screenshot_path)
            print(f"☁️ Uploaded to storage: {image_url}")
            
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
            try:
                # Normalize path (strip query string)
                path = self.path.split('?')[0]
                user_agent = self.headers.get('User-Agent', '')
                is_autohotkey = 'Slide-Tap-Hotkey' in user_agent
                
                # /ping => health only
                if path == '/ping':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain; charset=utf-8')
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    body = 'OK'
                    try:
                        self.wfile.write(body.encode('utf-8'))
                    except (ConnectionResetError, BrokenPipeError):
                        pass
                    logger.info(f"Ping request from {'AHK' if is_autohotkey else 'client'} -> OK")
                    return
                
                # /capture => perform screenshot (AHK & browser both allowed)
                if path == '/capture':
                    global trigger_counter
                    result = handle_http_trigger(callback=self.screenshot_callback)
                    trigger_counter += 1
                    trig_id = trigger_counter
                    logger.info(f"HTTPTrigger[{trig_id}] path=/capture user_agent='{user_agent}' ahk={is_autohotkey} result='{result}'")
                    self.send_response(200)
                    if is_autohotkey:
                        self.send_header('Content-type', 'text/plain; charset=utf-8')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        try:
                            self.wfile.write(result.encode('utf-8'))
                        except (ConnectionResetError, BrokenPipeError):
                            pass
                    else:
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        port = self.server.server_address[1]
                        response_html = f"""<!DOCTYPE html><html><head><title>Capture Result</title><meta charset='utf-8'></head><body style='background:#2E3440;color:white;text-align:center;padding:40px;'>
<h2>Capture Result</h2><p style='color:#A3BE8C;font-size:18px;'>{result}</p>
<p><a href='/capture' style='color:#88C0D0;'>Capture Again</a></p>
<p>Hotkey users: run slide_tap_hotkey.ahk and press Ctrl+B</p>
<hr><p>Status: <a style='color:#81A1C1;' href='/'>Home</a> | <a style='color:#81A1C1;' href='/ping'>Ping</a></p>
</body></html>"""
                        try:
                            self.wfile.write(response_html.encode('utf-8'))
                        except (ConnectionResetError, BrokenPipeError):
                            pass
                    return
                
                # Root '/' => status page only (NO CAPTURE)
                if path == '/':
                    self.send_response(200)
                    if is_autohotkey:
                        # AHK should prefer /ping; if it hits '/', give short hint
                        self.send_header('Content-type', 'text/plain; charset=utf-8')
                        self.end_headers()
                        try:
                            self.wfile.write(b"Slide Tap Helper OK - use /capture for screenshots")
                        except (ConnectionResetError, BrokenPipeError):
                            pass
                    else:
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.end_headers()
                        port = self.server.server_address[1]
                        html = f"""<!DOCTYPE html><html><head><title>Slide Tap Helper</title><meta charset='utf-8'></head>
<body style='background:#2E3440;color:white;text-align:center;padding:40px;'>
<h1>Slide Tap Helper</h1>
<p>Status: Running on port {port}</p>
<p><strong>Endpoints:</strong></p>
<ul style='list-style:none;'>
<li><code>/ping</code> - health check</li>
<li><code>/capture</code> - trigger screenshot</li>
</ul>
<p>AutoHotkey users: script will call /capture only on Ctrl+B.</p>
</body></html>"""
                        try:
                            self.wfile.write(html.encode('utf-8'))
                        except (ConnectionResetError, BrokenPipeError):
                            pass
                    logger.info(f"Status page served to {'AHK' if is_autohotkey else 'browser'}")
                    return
                
                # Unknown path
                self.send_error(404, "Unknown endpoint. Use /ping or /capture")
            except Exception as e:
                logger.error(f"HTTP handler error: {e}")
                try:
                    self.send_error(500, "Internal server error")
                except Exception:
                    pass
                
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