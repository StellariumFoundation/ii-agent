import asyncio
import json
import logging
import uuid
import socket # For get_free_port
import websockets # type: ignore
from pathlib import Path # For workspace management later
import os # For env vars if needed by args parsing
# import argparse # Not using full argparse for simplicity with one CLI arg
import sys # For stderr, stdout, exit
import base64 # For decoding file content

# Global args container
class AppArgs:
    workspace: str = None # Expected to be set from CLI
    use_container_workspace: bool = False 
    project_id: str = None 
    region: str = None 
    logs_path: str = "agent.log" # Will be relative to workspace/logs
    minimize_stdout_logs: bool = False
    context_manager: str = "amortized-forgetting"
    docker_container_id: str = None
    needs_permission: bool = False

global_args = AppArgs()

# Placeholder for RealtimeEvent and EventType
class EventType:
    CONNECTION_ESTABLISHED = "connection_established"
    AGENT_INITIALIZED = "agent_initialized"
    ERROR = "error"
    QUERY = "query" 
    INIT_AGENT = "init_agent"
    # For File Upload via WebSocket
    FILE_UPLOAD_REQUEST = "FILE_UPLOAD_REQUEST"
    FILE_UPLOAD_SUCCESS = "FILE_UPLOAD_SUCCESS"
    FILE_UPLOAD_FAILURE = "FILE_UPLOAD_FAILURE"
    # Mock agent events
    AGENT_THINKING = "agent_thinking"
    AGENT_RESPONSE = "agent_response"

class RealtimeEvent:
    def __init__(self, type, content):
        self.type = type
        self.content = content
    def model_dump(self): 
        return {"type": self.type, "content": self.content}

class MockAgent:
    def __init__(self, message_queue, session_id, workspace_path, client_websocket):
        self.message_queue = message_queue 
        self.session_id = session_id
        self.workspace_path = workspace_path
        self.client_websocket = client_websocket 
        self.logger = logging.getLogger(f"MockAgent_{str(session_id)[:8]}")
        self.logger.info(f"MockAgent initialized for session {session_id} in {workspace_path}")
        self._message_processor_task = None

    def start_message_processing(self): 
        self.logger.info("MockAgent: start_message_processing called.")
        async def _mock_processor():
            while True:
                try:
                    event_to_send = await self.message_queue.get()
                    if self.client_websocket and self.client_websocket.open:
                        await self.client_websocket.send(json.dumps(event_to_send.model_dump()))
                    self.message_queue.task_done()
                except websockets.exceptions.ConnectionClosed:
                    self.logger.warning("MockAgent: WebSocket closed while forwarding message.")
                    break
                except asyncio.CancelledError:
                    self.logger.info("MockAgent: Message processor task cancelled.")
                    break
                except Exception as e_fwd:
                    self.logger.error(f"MockAgent: Error forwarding agent msg: {e_fwd}")
                    break 
        self._message_processor_task = asyncio.create_task(_mock_processor())
        return self._message_processor_task

    async def run_agent_async_stub(self, user_input, files, resume):
        self.logger.info(f"MockAgent: run_agent called with input: {user_input}")
        await asyncio.sleep(0.5) 
        await self.message_queue.put(RealtimeEvent(type=EventType.AGENT_THINKING, content={"text": "Thinking..."}))
        await asyncio.sleep(1)
        await self.message_queue.put(RealtimeEvent(type=EventType.AGENT_RESPONSE, content={"text": f"Mock response to: {user_input}"}))

    def cancel(self):
        self.logger.info("MockAgent: cancel called.")

    async def close_processor(self):
        if self._message_processor_task and not self._message_processor_task.done():
            self._message_processor_task.cancel()
            try:
                await self._message_processor_task
            except asyncio.CancelledError:
                self.logger.info("MockAgent: Message processor task successfully cancelled on close.")

active_agents: dict[websockets.WebSocketServerProtocol, MockAgent] = {} 
UPLOAD_SUBDIR_NAME = "uploads" # Define this constant

def get_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port

async def agent_ws_handler(websocket: websockets.WebSocketServerProtocol, path: str):
    session_uuid = uuid.uuid4()
    client_addr = websocket.remote_address
    logger = logging.getLogger("AgentWSHandler")
    logger.info(f"Client {client_addr} connected, new session: {session_uuid}")
    
    if not global_args.workspace:
        logger.critical("Workspace root path not configured by frontend before agent handling!")
        try:
            await websocket.send(json.dumps(RealtimeEvent(type=EventType.ERROR, content={"message": "Server misconfiguration: Workspace path not set."}).model_dump()))
        except Exception: pass
        await websocket.close()
        return

    workspace_root_for_sessions = Path(global_args.workspace) / "sessions"
    workspace_root_for_sessions.mkdir(parents=True, exist_ok=True)
    current_session_workspace_path = workspace_root_for_sessions / str(session_uuid)
    
    try:
        current_session_workspace_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Session workspace created/ensured at: {current_session_workspace_path}")
        # Ensure uploads directory exists for this session
        session_upload_dir = current_session_workspace_path / UPLOAD_SUBDIR_NAME
        session_upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Session uploads directory created/ensured at: {session_upload_dir}")
    except Exception as e_mkdir:
        logger.error(f"Error creating session workspace or uploads dir {current_session_workspace_path}: {e_mkdir}")
        try:
            await websocket.send(json.dumps(RealtimeEvent(type=EventType.ERROR, content={"message": f"Server error: Could not create workspace: {e_mkdir}"}).model_dump()))
        except Exception: pass
        await websocket.close()
        return

    agent = None 
    message_processor_task = None
    try:
        await websocket.send(json.dumps(
            RealtimeEvent(
                type=EventType.CONNECTION_ESTABLISHED,
                content={
                    "message": "Connected to Embedded II-Agent Backend",
                    "workspace_path": str(current_session_workspace_path),
                    "session_uuid": str(session_uuid)
                },
            ).model_dump()
        ))

        async for message_str in websocket:
            logger.debug(f"RX from {client_addr} for session {session_uuid}: {message_str[:200]}...") # Log snippet
            try:
                message = json.loads(message_str)
                msg_type = message.get("type")
                content = message.get("content", {})

                if msg_type == EventType.INIT_AGENT:
                    if agent: 
                        logger.warning(f"Agent already initialized for {session_uuid}. Re-initializing.")
                        await agent.close_processor() 
                    
                    message_queue = asyncio.Queue()
                    agent = MockAgent(message_queue, session_uuid, str(current_session_workspace_path), websocket)
                    active_agents[websocket] = agent
                    
                    if message_processor_task and not message_processor_task.done():
                        message_processor_task.cancel() # Cancel previous task if any
                    message_processor_task = agent.start_message_processing()
                    
                    await websocket.send(json.dumps(
                        RealtimeEvent(type=EventType.AGENT_INITIALIZED, content={"message": "Agent initialized"}).model_dump()
                    ))
                    logger.info(f"Agent initialized for session {session_uuid}")

                elif msg_type == EventType.QUERY:
                    if not agent:
                        await websocket.send(json.dumps(RealtimeEvent(type=EventType.ERROR, content={"message": "Agent not initialized"}).model_dump()))
                        continue
                    user_input = content.get("text", "")
                    asyncio.create_task(agent.run_agent_async_stub(user_input, [], False))
                    logger.info(f"Query received: '{user_input}' for session {session_uuid}")

                elif msg_type == EventType.FILE_UPLOAD_REQUEST:
                    file_name = content.get("fileName")
                    file_content_str = content.get("fileContent") # Base64 string or data URL
                    
                    if not file_name or file_content_str is None:
                        logger.warning(f"File upload request missing fileName or fileContent for session {session_uuid}")
                        await websocket.send(json.dumps(RealtimeEvent(type=EventType.FILE_UPLOAD_FAILURE, content={"originalName": file_name, "message": "Missing fileName or fileContent"}).model_dump()))
                        continue

                    try:
                        original_save_path = session_upload_dir / Path(file_name).name # Sanitize filename
                        final_save_path = original_save_path
                        counter = 1
                        while final_save_path.exists():
                            final_save_path = session_upload_dir / f"{original_save_path.stem}_{counter}{original_save_path.suffix}"
                            counter += 1
                        
                        file_data_bytes: bytes
                        if file_content_str.startswith('data:'):
                            try:
                                header, encoded = file_content_str.split(",", 1)
                                file_data_bytes = base64.b64decode(encoded)
                            except Exception as e_b64_hdr:
                                logger.error(f"Error decoding base64 with header for {file_name}: {e_b64_hdr}", exc_info=True)
                                await websocket.send(json.dumps(RealtimeEvent(type=EventType.FILE_UPLOAD_FAILURE, content={"originalName": file_name, "message": f"Invalid base64 header format: {e_b64_hdr}"}).model_dump()))
                                continue
                        else: 
                            try:
                                file_data_bytes = base64.b64decode(file_content_str)
                            except Exception as e_b64_raw:
                                logger.error(f"Error decoding raw base64 for {file_name}: {e_b64_raw}", exc_info=True)
                                await websocket.send(json.dumps(RealtimeEvent(type=EventType.FILE_UPLOAD_FAILURE, content={"originalName": file_name, "message": f"Invalid raw base64 content: {e_b64_raw}"}).model_dump()))
                                continue

                        with open(final_save_path, "wb") as f:
                            f.write(file_data_bytes)
                        
                        relative_path_to_session_ws = Path(UPLOAD_SUBDIR_NAME) / final_save_path.name
                        
                        await websocket.send(json.dumps(
                            RealtimeEvent(type=EventType.FILE_UPLOAD_SUCCESS, content={
                                "message": f"File '{file_name}' uploaded successfully as '{final_save_path.name}'.",
                                "filePathInWorkspace": str(relative_path_to_session_ws), 
                                "originalName": file_name
                            }).model_dump()
                        ))
                        logger.info(f"File '{file_name}' saved to {final_save_path} for session {session_uuid}")

                    except Exception as e_upload:
                        logger.error(f"File upload processing error for {file_name} (session {session_uuid}): {e_upload}", exc_info=True)
                        await websocket.send(json.dumps(RealtimeEvent(type=EventType.FILE_UPLOAD_FAILURE, content={"originalName": file_name, "message": str(e_upload)}).model_dump()))
                
                else:
                    logger.warning(f"Unknown message type: {msg_type} for session {session_uuid}")
                    await websocket.send(json.dumps(RealtimeEvent(type=EventType.ERROR, content={"message": f"Unknown message type: {msg_type}"}).model_dump()))

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from {client_addr} for session {session_uuid}")
                await websocket.send(json.dumps(RealtimeEvent(type=EventType.ERROR, content={"message": "Invalid JSON"}).model_dump()))
            except Exception as e_loop:
                logger.error(f"Error in message loop for {client_addr} (session {session_uuid}): {e_loop}", exc_info=True)
                if websocket.open:
                    await websocket.send(json.dumps(RealtimeEvent(type=EventType.ERROR, content={"message": str(e_loop)}).model_dump()))
    
    except websockets.exceptions.ConnectionClosedError:
        logger.info(f"Connection closed by client {client_addr} for session {session_uuid}.")
    except Exception as e_handler:
        logger.error(f"WebSocket handler error for {client_addr} (session {session_uuid}): {e_handler}", exc_info=True)
    finally:
        if agent: 
            await agent.close_processor() 
        if websocket in active_agents:
            del active_agents[websocket]
        logger.info(f"Cleaned up for session {session_uuid} from {client_addr}")

async def main_server(workspace_path_arg: str): 
    global_args.workspace = workspace_path_arg 
    if not global_args.workspace:
        print("embedded_backend_main.py: CRITICAL - Workspace path argument not provided or empty.", file=sys.stderr, flush=True)
        sys.exit(2) 

    log_dir = Path(global_args.workspace) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    global_args.logs_path = str(log_dir / "embedded_agent.log")

    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr), 
            logging.FileHandler(global_args.logs_path)
        ]
    )
    server_logger = logging.getLogger("EmbeddedServer")

    sessions_base_dir = Path(global_args.workspace) / "sessions"
    sessions_base_dir.mkdir(parents=True, exist_ok=True)
    server_logger.info(f"Base directory for session workspaces: {sessions_base_dir}")
    
    port = 0
    try:
        port = get_free_port()
    except Exception as e:
        server_logger.critical(f"Could not get a free port: {e}", exc_info=True)
        sys.exit(1)

    print(f"PORT:{port}", flush=True) 
    
    server_logger.info(f"Starting II-Agent Embedded WebSocket server on ws://localhost:{port}")
    server_logger.info(f"Using base workspace path: {global_args.workspace}")
    server_logger.info(f"Logging to: {global_args.logs_path}")

    try:
        async with websockets.serve(agent_ws_handler, "localhost", port, max_size=2**20 * 10): # Increased to 10MB limit for file uploads
            server_logger.info(f"Server started successfully on port {port}.")
            await asyncio.Future()  
    except Exception as e:
        server_logger.critical(f"Server failed to start or run: {e}", exc_info=True)
        sys.exit(1) 

if __name__ == "__main__":
    if len(sys.argv) > 1:
        workspace_arg_main = sys.argv[1]
    else:
        default_temp_workspace = "./default_app_data_temp_embedded"
        print(f"embedded_backend_main.py: WARNING - No workspace path provided via CLI arg. Using default '{default_temp_workspace}'", file=sys.stderr, flush=True)
        workspace_arg_main = default_temp_workspace
    
    global_args.project_id = os.getenv("PROJECT_ID") 
    global_args.region = os.getenv("REGION")       

    try:
        asyncio.run(main_server(workspace_arg_main))
    except KeyboardInterrupt:
        print("embedded_backend_main.py: Server shutting down (KeyboardInterrupt).", file=sys.stderr, flush=True)
    except SystemExit as e:
        if e.code != 0 and e.code is not None: 
             print(f"embedded_backend_main.py: Server exited with code {e.code}.", file=sys.stderr, flush=True)
    except Exception as e_outer:
        print(f"embedded_backend_main.py: CRITICAL error during server execution: {e_outer}", file=sys.stderr, flush=True)
        sys.exit(1) 
    finally:
        print("embedded_backend_main.py: Server process terminated.", file=sys.stderr, flush=True)
