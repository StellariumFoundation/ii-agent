import asyncio
import json
import sys
import websockets # type: ignore
import socket

def get_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port

async def echo_server(websocket, path):
    # Print to stderr that a client has connected
    client_addr = websocket.remote_address
    print(f"local_ws_server.py: Client {client_addr} connected.", file=sys.stderr, flush=True)
    try:
        async for message in websocket:
            print(f"local_ws_server.py: Received from {client_addr}: {message}", file=sys.stderr, flush=True)
            try:
                data = json.loads(message)
                data['processed_by_ws_python'] = True
                response = json.dumps(data)
                await websocket.send(response)
                print(f"local_ws_server.py: Sent to {client_addr}: {response}", file=sys.stderr, flush=True)
            except json.JSONDecodeError:
                error_response = json.dumps({"status": "error", "message": "Invalid JSON from WebSocket"})
                await websocket.send(error_response)
                print(f"local_ws_server.py: Sent error (Invalid JSON) to {client_addr}", file=sys.stderr, flush=True)
            except Exception as e_inner:
                error_response = json.dumps({"status": "error", "message": str(e_inner)})
                await websocket.send(error_response)
                print(f"local_ws_server.py: Sent error ({str(e_inner)}) to {client_addr}", file=sys.stderr, flush=True)
    except websockets.exceptions.ConnectionClosedError:
        print(f"local_ws_server.py: Client {client_addr} disconnected.", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"local_ws_server.py: Server error with client {client_addr}: {e}", file=sys.stderr, flush=True)
        # Attempt to send a final error message if the connection is still open
        if websocket.open:
            try:
                await websocket.send(json.dumps({"status": "error", "message": f"Server error: {e}"}))
            except Exception as e_send:
                print(f"local_ws_server.py: Could not send final error to client {client_addr}: {e_send}", file=sys.stderr, flush=True)


async def main():
    port = 0
    try:
        port = get_free_port()
    except Exception as e_port:
        print(f"local_ws_server.py: Error getting free port: {e_port}", file=sys.stderr, flush=True)
        sys.exit(1) # Exit if cannot get a port

    # This is the crucial line for Neutralinojs to capture the port.
    # Ensure it's the very first thing printed to stdout if possible, or clearly identifiable.
    print(f"PORT:{port}", flush=True) 
    
    print(f"local_ws_server.py: Attempting to start WebSocket server on ws://localhost:{port}", file=sys.stderr, flush=True)
    
    try:
        async with websockets.serve(echo_server, "localhost", port):
            print(f"local_ws_server.py: Server started successfully on port {port}.", file=sys.stderr, flush=True)
            await asyncio.Future()  # Run forever until cancelled
    except Exception as e_serve:
        print(f"local_ws_server.py: Failed to start server on port {port}: {e_serve}", file=sys.stderr, flush=True)
        # If server fails to start, this script might exit. Neutralinojs should detect process exit.
        sys.exit(1) # Exit if server fails to start

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("local_ws_server.py: KeyboardInterrupt, exiting.", file=sys.stderr, flush=True)
    except SystemExit as e:
        # This allows sys.exit(1) to properly terminate with an error code
        if e.code != 0:
             print(f"local_ws_server.py: Exiting with code {e.code}", file=sys.stderr, flush=True)
        raise # Re-raise to ensure proper exit status
    except Exception as e_outer:
        print(f"local_ws_server.py: Critical error in main execution: {e_outer}", file=sys.stderr, flush=True)
        sys.exit(1) # Ensure non-zero exit code for critical errors
