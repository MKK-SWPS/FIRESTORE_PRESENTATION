"""
Alternative trigger methods for screenshot capture when hotkeys don't work
"""

import threading
import time
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
import logging

logger = logging.getLogger(__name__)


class ScreenshotHTTPServer:
    """Simple HTTP server that triggers screenshot on GET request."""
    
    def __init__(self, port=8889, callback=None):
        self.port = port
        self.callback = callback
        self.server = None
        self.thread = None
        
    class ScreenshotHandler(SimpleHTTPRequestHandler):
        def __init__(self, callback):
            self.screenshot_callback = callback
            super().__init__()
            
        def __call__(self, *args, **kwargs):
            self.screenshot_callback = self.screenshot_callback
            return super().__call__(*args, **kwargs)
        
        def do_GET(self):
            if self.path == '/capture' or self.path == '/':
                try:
                    if self.screenshot_callback:
                        self.screenshot_callback()
                    
                    # Send success response
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    
                    response = """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Screenshot Trigger</title>
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <style>
                            body { font-family: Arial; text-align: center; padding: 50px; background: #2E3440; color: white; }
                            .button { background: #5E81AC; color: white; border: none; padding: 20px 40px; font-size: 18px; border-radius: 8px; cursor: pointer; margin: 10px; }
                            .button:hover { background: #81A1C1; }
                            .success { color: #A3BE8C; font-size: 24px; margin: 20px; }
                        </style>
                    </head>
                    <body>
                        <h1>Screenshot Captured! ✅</h1>
                        <p class="success">Screenshot has been taken and uploaded to Firebase</p>
                        <button class="button" onclick="location.reload()">Capture Another</button>
                        <hr style="margin: 40px 0; border-color: #4C566A;">
                        <h3>Bookmark This Page!</h3>
                        <p>Add this to your browser bookmarks for quick access:<br>
                        <strong>http://localhost:{}</strong></p>
                        <p><small>Keep this window open while presenting</small></p>
                    </body>
                    </html>
                    """.format(self.server.server_address[1] if hasattr(self, 'server') else self.port)
                    
                    self.wfile.write(response.encode())
                    
                except Exception as e:
                    logger.error(f"HTTP trigger error: {e}")
                    self.send_error(500, f"Screenshot failed: {e}")
            else:
                self.send_error(404, "Use /capture or / to trigger screenshot")
                
        def log_message(self, format, *args):
            # Reduce HTTP server logging noise
            pass
    
    def start(self):
        """Start the HTTP server in a background thread."""
        try:
            handler = lambda *args, **kwargs: self.ScreenshotHandler(self.callback)(*args, **kwargs)
            self.server = HTTPServer(('localhost', self.port), handler)
            self.server.screenshot_callback = self.callback
            
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