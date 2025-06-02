import http.server
import socketserver
import os
import mimetypes

PORT = 8000
SERVE_DIR = "frontend/out"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    def guess_type(self, path):
        # Correctly serve .js files as application/javascript
        # and .css as text/css
        base, ext = os.path.splitext(path)
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        ext = ext.lower()
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        else:
            return self.extensions_map['']

if not os.path.isdir(SERVE_DIR):
    print(f"Error: The directory '{SERVE_DIR}' does not exist.")
    print("Please ensure you have built the frontend by running 'npm run build' in the 'frontend' directory after setting 'output: "export"' in next.config.ts.")
    exit(1)

# Add common web MIME types if not already present by default
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("image/png", ".png")
mimetypes.add_type("image/jpeg", ".jpg")
mimetypes.add_type("image/x-icon", ".ico")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("font/woff2", ".woff2")


os.chdir(SERVE_DIR) # Change current directory to SERVE_DIR for SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    print(f"Serving static files from '{os.path.join(os.getcwd(), SERVE_DIR)}' at http://localhost:{PORT}")
    print(f"Actually serving from current directory: '{os.getcwd()}' which should be '{SERVE_DIR}'")
    httpd.serve_forever()
