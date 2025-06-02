import sys
import json
import time

def main():
    # Optional: print a startup message to stderr for debugging with Neutralino
    print("stdio_echo.py: Process started.", file=sys.stderr, flush=True)
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                # End of input or pipe closed
                print("stdio_echo.py: stdin closed, exiting.", file=sys.stderr, flush=True)
                break
            
            line = line.strip()
            if not line: # Skip empty lines if any
                continue

            # print(f"stdio_echo.py: Received raw line: '{line}'", file=sys.stderr, flush=True)
            
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                error_response = {"status": "error", "message": "Invalid JSON input", "error": str(e), "original_input": line}
                print(json.dumps(error_response), flush=True)
                print(f"stdio_echo.py: JSONDecodeError: {str(e)} for input '{line}'", file=sys.stderr, flush=True)
                continue

            # Process the data (e.g., add a 'received' flag)
            data['processed_by_python'] = True
            data['timestamp_py'] = time.time()
            
            response_json = json.dumps(data)
            print(response_json, flush=True) # Send response to stdout
            # print(f"stdio_echo.py: Sent response: {response_json}", file=sys.stderr, flush=True)

        except KeyboardInterrupt:
            print("stdio_echo.py: KeyboardInterrupt, exiting.", file=sys.stderr, flush=True)
            break
        except Exception as e:
            # Generic error logging to stderr
            print(f"stdio_echo.py: Error - {str(e)}", file=sys.stderr, flush=True)
            # Attempt to send an error response to stdout if possible
            try:
                error_response = {"status": "error", "message": "Python script internal error", "error": str(e)}
                print(json.dumps(error_response), flush=True)
            except Exception as e_resp:
                print(f"stdio_echo.py: Could not send error to stdout - {str(e_resp)}", file=sys.stderr, flush=True)
            break # Exit on other errors too to prevent busy loops

if __name__ == "__main__":
    main()
