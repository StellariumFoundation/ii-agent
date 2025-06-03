import threading
import time
import os
import sys
import webbrowser
from pathlib import Path

import config_ui # Assuming config_ui.py is in the same directory or Python path
import serve_static # Assuming serve_static.py is ...
import ws_server # Assuming ws_server.py is ...

# --- Configuration ---
FRONTEND_SERVER_PORT = 8001 # Should match serve_static.DEFAULT_PORT
WEBSOCKET_SERVER_PORT = 8000 # Should match ws_server default or be configurable

# Define required API keys for config_ui
REQUIRED_API_KEYS = [
    "ANTHROPIC_API_KEY",
    "TAVILY_API_KEY",
    # Add any other keys ws_server might need from its .env expectations
]

def get_base_path():
    # Get the base path for bundled app (MEIPASS) or development
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent

def get_frontend_out_dir(base_path):
    # In PyInstaller, 'frontend/out' will be bundled as a data directory.
    # Its path relative to sys._MEIPASS will be 'frontend/out'.
    return base_path / "frontend" / "out"

def run_websocket_server(config):
    print("Starting WebSocket server...")
    # ws_server.py uses argparse. We need to simulate or set these args.
    # Or refactor ws_server.main to accept args directly.
    # For now, let's assume environment variables can cover its config needs
    # once API keys are in 'config'.

    # Set environment variables from loaded/entered config for ws_server
    for key, value in config.items():
        os.environ[key] = value
        print(f"Set env var for ws_server: {key}")

    # TODO: Refactor ws_server.py to have a callable main(args_dict) or similar
    # For now, try to call its existing main() if it doesn't conflict.
    # This is a placeholder and might need significant adjustment based on ws_server.py structure.
    try:
        # Simulate command line arguments for ws_server if necessary
        # This is a simplified approach. A proper refactor of ws_server.py's arg parsing
        # would be better for robust integration.
        ws_args = ws_server.parse_common_args(ws_server.argparse.ArgumentParser()).parse_args([
            '--host', '0.0.0.0',
            '--port', str(WEBSOCKET_SERVER_PORT),
            # Add other necessary args from ws_server that global_args expects
            # e.g. --workspace, --logs-path, --context-manager
            # These should ideally also come from a config or be sensible defaults
            '--workspace', str(get_base_path() / "workspace_main_app"), # Example
            '--logs-path', str(get_base_path() / "main_app_ws.log"),    # Example
            '--context-manager', 'amortized-forgetting' # Example default
        ])
        ws_server.global_args = ws_args # Directly set if possible, or pass to a main function

        # Ensure workspace for ws_server exists
        ws_workspace_path = Path(ws_args.workspace)
        ws_workspace_path.mkdir(parents=True, exist_ok=True)
        ws_server.setup_workspace(ws_server.app, ws_workspace_path)


        print(f"Attempting to start ws_server on port {WEBSOCKET_SERVER_PORT}...")
        # uvicorn.run(app, host=args.host, port=args.port) is called in ws_server.main()
        # We need to make ws_server.main() runnable without starting uvicorn if uvicorn.run is blocking
        # Or ensure ws_server.main() itself is the target for the thread.
        # For now, assuming ws_server.main() is appropriate for threading.

        # If ws_server.main() calls uvicorn.run(), it will block.
        # We need to run uvicorn in a way that it can be managed by this script.
        # The easiest is to configure ws_server.app and then run uvicorn here.

        import uvicorn
        uvicorn.run(ws_server.app, host="0.0.0.0", port=WEBSOCKET_SERVER_PORT, log_level="info")
        print("WebSocket server finished.") # Should not be reached if uvicorn runs forever
    except Exception as e:
        print(f"Error starting WebSocket server: {e}")
        import traceback
        traceback.print_exc()

def run_static_server(frontend_dir):
    print(f"Starting static frontend server for directory: {frontend_dir}")
    if not frontend_dir.exists() or not frontend_dir.is_dir():
        print(f"Error: Frontend directory '{frontend_dir}' not found or not a directory.")
        print("Ensure the frontend is built and included in the PyInstaller bundle correctly.")
        return
    serve_static.start_static_server(serve_dir=frontend_dir, port=FRONTEND_SERVER_PORT)
    print("Static frontend server finished.") # Should not be reached

def main():
    base_path = get_base_path()
    print(f"Application base path: {base_path}")

    # 1. Ensure API keys are configured
    print("Checking API key configuration...")
    api_config = config_ui.ensure_api_keys(REQUIRED_API_KEYS)

    # Check if essential keys were actually provided
    keys_sufficient = True
    for req_key in REQUIRED_API_KEYS:
        if not api_config.get(req_key):
            print(f"Error: Required API key '{req_key}' is missing after configuration attempt.")
            keys_sufficient = False

    if not keys_sufficient:
        print("Cannot start servers due to missing API keys. Please re-run and provide the keys.")
        # In a real GUI app, you might re-prompt or show an error message.
        # For a bundled app, exiting might be the only option if keys are crucial.
        return

    print("API keys configured.")

    # 2. Determine frontend directory path
    frontend_out_dir = get_frontend_out_dir(base_path)
    print(f"Frontend assets expected at: {frontend_out_dir}")


    # 3. Start WebSocket server in a thread
    ws_thread = threading.Thread(target=run_websocket_server, args=(api_config,), daemon=True)
    ws_thread.start()
    print("WebSocket server thread started.")

    # 4. Start static file server in a thread
    static_server_thread = threading.Thread(target=run_static_server, args=(frontend_out_dir,), daemon=True)
    static_server_thread.start()
    print("Static file server thread started.")

    # 5. Wait a moment for servers to initialize
    time.sleep(2) # Adjust as needed

    # 6. Open web browser to the frontend
    frontend_url = f"http://localhost:{FRONTEND_SERVER_PORT}"
    print(f"Attempting to open web browser to: {frontend_url}")
    try:
        webbrowser.open(frontend_url)
    except Exception as e:
        print(f"Could not open web browser: {e}. Please navigate to {frontend_url} manually.")

    # Keep main thread alive while daemon threads run (or use ws_thread.join(), static_server_thread.join())
    # If servers are daemons, main can exit and daemons will be killed.
    # If we want to wait for them (e.g. for clean shutdown later):
    print("Application is running. Close this window or Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1) # Keep main thread alive
            # TODO: Add proper shutdown mechanism here for threads if needed
            # For now, relying on daemon threads + Ctrl+C / window close
    except KeyboardInterrupt:
        print("Shutting down application...")
        # TODO: Implement graceful shutdown for servers if possible
        # For uvicorn/http.server, this is tricky without more advanced process/thread management.
    finally:
        print("Exiting main application.")


if __name__ == '__main__':
    main()
