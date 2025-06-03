import http.server
import socketserver
import os
import mimetypes
from pathlib import Path

DEFAULT_PORT = 8001 # Changed port to avoid conflict with ws_server default 8000
DEFAULT_SERVE_DIR = Path("frontend/out")

class ServingHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        if directory is None:
            directory = os.getcwd()
        super().__init__(*args, directory=str(Path(directory).resolve()), **kwargs)

    def guess_type(self, path):
        # Custom guess_type to ensure correct MIME types
        # This might not be strictly necessary if mimetypes module is configured globally
        # and SimpleHTTPRequestHandler uses it correctly.
        base, ext = os.path.splitext(path)
        ext = ext.lower()
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        # Fallback for unknown types
        content_type, _ = mimetypes.guess_type(path)
        return content_type if content_type else self.extensions_map['']


def start_static_server(serve_dir=None, port=None):
    if port is None:
        port = DEFAULT_PORT
    if serve_dir is None:
        serve_dir = DEFAULT_SERVE_DIR

    serve_path = Path(serve_dir)

    if not serve_path.is_dir():
        print(f"Error: The directory '{serve_path}' does not exist or is not a directory.")
        print("Please ensure the frontend has been built and the path is correct.")
        return False # Indicate failure

    # Add common web MIME types if not already present by default
    # These are class variables for SimpleHTTPRequestHandler, but adding them globally is safer.
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("image/svg+xml", ".svg")
    mimetypes.add_type("image/png", ".png")
    mimetypes.add_type("image/jpeg", ".jpg")
    mimetypes.add_type("image/x-icon", ".ico")
    mimetypes.add_type("application/json", ".json")
    mimetypes.add_type("font/woff2", ".woff2")
    mimetypes.add_type("font/woff", ".woff")
    mimetypes.add_type("font/ttf", ".ttf")

    # Patch extensions_map for the handler if needed, though global mimetypes should be enough
    ServingHandler.extensions_map.update({
        ".js": "application/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".ico": "image/x-icon",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        "": "application/octet-stream", # Default
    })

    # The handler needs to be created with the directory argument.
    # We can't use os.chdir as it affects the whole process.
    # functools.partial is used to pass the directory to the handler.
    from functools import partial

    HandlerWithDirectory = partial(ServingHandler, directory=str(serve_path.resolve()))

    try:
        with socketserver.TCPServer(("", port), HandlerWithDirectory) as httpd:
            print(f"Serving static files from '{str(serve_path.resolve())}' at http://localhost:{port}")
            httpd.serve_forever()
        return True # Should not be reached if serve_forever is blocking
    except OSError as e:
        print(f"Error starting static server on port {port}: {e}")
        print(f"This might be because the port is already in use or due to permissions issues.")
        return False


if __name__ == '__main__':
    # This allows running it as a script for testing, but it's now also importable
    # For PyInstaller, we'll call start_static_server from main_app.py
    # You might need to adjust where frontend/out is relative to this script if run directly
    print("Attempting to start static server directly for testing...")
    # In a bundled app, 'frontend/out' will be relative to the executable's location.
    # PyInstaller will place data files in a specific location, often sys._MEIPASS.
    # This path needs to be determined at runtime in main_app.py.

    # For direct testing, assume frontend/out is in the expected place relative to project root
    test_serve_dir = Path(__file__).resolve().parent.parent / "frontend" / "out"
    if not test_serve_dir.exists():
         print(f"Test directory {test_serve_dir} not found. Run from project root or ensure frontend is built.")
    else:
        start_static_server(serve_dir=test_serve_dir, port=DEFAULT_PORT)
