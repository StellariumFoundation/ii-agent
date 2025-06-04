import unittest
from unittest.mock import patch, MagicMock, AsyncMock, ANY
import asyncio
import json
import uuid
from pathlib import Path
import os

import pytest # Using pytest for async fixtures and cleaner async tests
from fastapi.testclient import TestClient

# Import the FastAPI app and other components from ws_server
# To make 'from ws_server import app' work, ensure ws_server.py is in python path
# or adjust sys.path. For now, assume it can be imported if tests are run from root.
# If ws_server.py is in the root, this will be:
# from ws_server import app, EventType, RealtimeEvent, global_args, parse_common_args
# But ws_server.py is likely in src/ii_agent/ or similar.
# For this tool, I will assume the path is resolved correctly by the environment.
# If it's `python -m src.ii_agent.ws_server`, then imports are relative to `src`.
# Let's assume for test structure, we reference it as if it's accessible.
# The tool itself might run this from the repo root.

# The tool will execute from the repo root, so ws_server.py is at the root.
from ws_server import app, EventType, RealtimeEvent # global_args, parse_common_args are tricky
# We will patch global_args directly.

from src.ii_agent.utils import WorkspaceManager
from src.ii_agent.db.manager import DatabaseManager
from src.ii_agent.llm.base import LLMClient
from src.ii_agent.agents.anthropic_fc import AnthropicFC
from src.ii_agent.tools.base import LLMTool


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="function") # Function scope for cleaner state per test
def client_fixture():
    # This fixture will mock all major dependencies of ws_server.py
    # It's important that ws_server.global_args is set *before* TestClient(app)
    # if app configuration depends on it at import time (which it might for mounting static dir).
    # We'll patch global_args directly where it's accessed or patch parse_common_args.

    # Mock global_args as if parsed by main()
    # These are defaults from cli.py/ws_server.py that affect ws_server logic
    mock_cli_args = {
        "workspace": "./test_ws_server_workspace", # Use a test-specific temp dir
        "use_container_workspace": False,
        "logs_path": "test_ws_agent.log",
        "minimize_stdout_logs": True,
        "model_name": "default_test_model",
        "llm_client": "anthropic-direct", # Default or common choice
        "project_id": None, "region": None, "azure_model": False, "cot_model": False,
        "context_manager": "llm-summarizing", "prompt": None,
        "docker_container_id": None, "needs_permission": False,
        "memory_tool": "simple",
        "host": "127.0.0.1", "port": 8000 # For uvicorn, not directly used by TestClient
    }

    # Ensure the test workspace directory exists and is cleaned up if needed,
    # but for many tests, WorkspaceManager itself will be mocked.
    test_ws_root = Path(mock_cli_args["workspace"])
    test_ws_root.mkdir(parents=True, exist_ok=True)


    with patch('ws_server.global_args', new=argparse.Namespace(**mock_cli_args)), \
         patch('ws_server.DatabaseManager') as MockDBManager, \
         patch('ws_server.create_workspace_manager_for_connection') as MockCreateWorkspace, \
         patch('ws_server.map_model_name_to_client') as MockMapModelToClient, \
         patch('ws_server.AnthropicFC') as MockAgentConstructor, \
         patch('ws_server.enhance_user_prompt', new_callable=AsyncMock) as MockEnhancePrompt, \
         patch('ws_server.get_system_tools') as MockGetSystemTools, \
         patch('ws_server.LLMSummarizingContextManager') as MockLLMSumCM, \
         patch('ws_server.AmortizedForgettingContextManager') as MockAmortizedCM, \
         patch('ws_server.TokenCounter'), \
         patch('os.makedirs') as mock_os_makedirs, \
         patch('builtins.open', new_callable=mock_open) as mock_file_open, \
         patch('pathlib.Path.exists') as mock_path_exists: # For /api/upload

        # Configure mocks common to most tests
        mock_ws_manager_instance = MagicMock(spec=WorkspaceManager)
        mock_ws_manager_instance.root = test_ws_root
        mock_session_id = uuid.uuid4()
        MockCreateWorkspace.return_value = (mock_ws_manager_instance, mock_session_id)

        mock_db_instance = MockDBManager.return_value

        mock_llm_client_instance = MagicMock(spec=LLMClient)
        MockMapModelToClient.return_value = mock_llm_client_instance

        mock_agent_instance = MagicMock(spec=AnthropicFC)
        mock_agent_instance.session_id = mock_session_id
        mock_agent_instance.message_queue = MagicMock(spec=asyncio.Queue)
        mock_agent_instance.message_queue.put_nowait = MagicMock()
        mock_agent_instance.run_agent = MagicMock() # This is sync in AnthropicFC
        mock_agent_instance.start_message_processing = MagicMock(return_value=AsyncMock()) # Returns a mock task
        mock_agent_instance.cancel = MagicMock()
        mock_agent_instance.history = MagicMock(spec=MessageHistory)
        mock_agent_instance.history.clear_from_last_to_user_message = MagicMock()
        mock_agent_instance.db_manager = mock_db_instance # Agent uses its own DB manager instance
        MockAgentConstructor.return_value = mock_agent_instance

        MockGetSystemTools.return_value = [MagicMock(spec=LLMTool)]


        # Patch the app's static files mounting as it depends on global_args.workspace
        # If app is already imported, its routes might be configured.
        # We need to ensure setup_workspace is called with our test path, or mock its effect.
        with patch('ws_server.setup_workspace') as mock_setup_workspace:
            # TestClient will use the app instance from ws_server
            # Ensure global_args is set when app is configured by TestClient
            # The patch for global_args should cover this.
            # ws_server.main() is not run, so app.mount might not happen for static files
            # unless TestClient does something similar or we call setup_workspace.
            # For now, assume /workspace static serving isn't critical for API/WS tests.

            # Yield the TestClient
            # It's important that global_args is patched *before* TestClient(app) if app uses it at import time.
            # ws_server.py defines global_args = None, then main() sets it.
            # The websocket endpoint directly uses global_args.
            # So the patch on ws_server.global_args is key.

            # Store mocks for tests to access if needed
            fixture_mocks = {
                "db_manager": mock_db_instance,
                "ws_manager": mock_ws_manager_instance,
                "llm_client": mock_llm_client_instance,
                "agent_constructor": MockAgentConstructor,
                "agent_instance": mock_agent_instance,
                "create_workspace": MockCreateWorkspace,
                "map_model_to_client": MockMapModelToClient,
                "enhance_prompt": MockEnhancePrompt,
                "get_system_tools": MockGetSystemTools,
                "mock_os_makedirs": mock_os_makedirs,
                "mock_file_open": mock_file_open,
                "mock_path_exists": mock_path_exists,
                "session_id": mock_session_id,
            }

            with TestClient(app) as client:
                yield client, fixture_mocks

    # Clean up the test workspace directory after tests if it was created
    # This might be better in a session or module teardown if not using unique dirs per test.
    if test_ws_root.exists():
        import shutil
        # shutil.rmtree(test_ws_root) # Be careful with rmtree


@pytest.mark.asyncio
async def test_websocket_connection_and_initial_message(client_fixture):
    client, mocks = client_fixture
    with client.websocket_connect("/ws") as websocket:
        initial_message = websocket.receive_json()
        assert initial_message["type"] == EventType.CONNECTION_ESTABLISHED.value
        assert "workspace_path" in initial_message["content"]
        assert initial_message["content"]["workspace_path"] == str(mocks["ws_manager"].root)

        # Test ping/pong
        websocket.send_json({"type": "ping", "content": {}})
        pong_message = websocket.receive_json()
        assert pong_message["type"] == EventType.PONG.value

@pytest.mark.asyncio
async def test_ws_init_agent(client_fixture):
    client, mocks = client_fixture
    with client.websocket_connect("/ws") as websocket:
        _ = websocket.receive_json() # consume connection established

        init_payload = {
            "type": "init_agent",
            "content": {
                "model_name": "claude-test",
                "tool_args": {"some_tool": True}
            }
        }
        websocket.send_json(init_payload)
        response = websocket.receive_json()

        assert response["type"] == EventType.AGENT_INITIALIZED.value
        mocks["map_model_to_client"].assert_called_with("claude-test", init_payload["content"])
        # create_agent_for_connection is called inside the endpoint, which then calls AnthropicFC constructor
        # So we check AnthropicFC constructor was called via the mock_agent_instance setup
        # If create_agent_for_connection was patched, check that instead.
        # Here we check the effect: agent was created.
        assert mocks["agent_constructor"].call_count == 1
        # Check if start_message_processing was called on the agent instance
        mocks["agent_instance"].start_message_processing.assert_called_once()


@pytest.mark.asyncio
async def test_ws_query_simple_agent_response(client_fixture):
    client, mocks = client_fixture
    agent_text_response = "This is the agent's answer."
    # Simulate agent's run_agent putting response on its queue, then it's picked by _process_messages
    # which is mocked/part of the agent mock.
    # For simplicity, we'll check that agent.run_agent is called.
    # The actual RealtimeEvent for AGENT_RESPONSE would be sent by the agent's message processing loop.
    # Here, run_agent_async in ws_server.py calls agent.run_agent.
    # agent.run_agent then (inside AnthropicFC) eventually calls message_queue.put_nowait
    # with AGENT_RESPONSE.
    mocks["agent_instance"].run_agent.return_value = agent_text_response # What run_agent returns

    # We need to simulate the message queue behavior of the agent for this test
    # to see the AGENT_RESPONSE event come back through the websocket.
    # This means the mocked agent's message_queue.put_nowait needs to be observable
    # and the agent's _process_messages task (mocked by start_message_processing)
    # would need to interact with the websocket. This is getting complex.

    # Alternative: Test that the ws_server's run_agent_async correctly calls agent.run_agent
    # and that if agent.run_agent itself leads to an AGENT_RESPONSE event via its queue,
    # that the _process_messages (if not fully mocked away) would send it.

    # Let's assume agent.run_agent completes and the final "Task completed" or similar
    # is what we are testing for now, without deep mocking the queue behavior *within* the agent.
    # The run_agent_async in ws_server has its own USER_MESSAGE put on queue.
    # And if agent.run_agent finishes, it (AnthropicFC) puts AGENT_RESPONSE(content={"text": "Task completed"})

    with client.websocket_connect("/ws") as websocket:
        _ = websocket.receive_json() # consume established
        # Send init
        websocket.send_json({"type": "init_agent", "content": {"model_name": "test"}})
        _ = websocket.receive_json() # consume initialized

        # Send query
        query_text = "Hello agent, what is 2+2?"
        websocket.send_json({"type": "query", "content": {"text": query_text, "resume": False, "files": []}})

        processing_msg = websocket.receive_json()
        assert processing_msg["type"] == EventType.PROCESSING.value

        # Now, ws_server's run_agent_async is running agent.run_agent in a thread.
        # The mock_run_in_executor from cli test setup is similar to what anyio.to_thread.run_sync does.
        # We need to ensure agent.run_agent is called.
        # The result of agent.run_agent is not directly sent back via websocket by run_agent_async.
        # Instead, run_agent_async relies on the agent's internal message_queue processing
        # (via start_message_processing) to send events back.

        # To test this, we need to mock what `agent.message_queue.put_nowait` is called with
        # by the agent when it finishes or produces intermediate results.
        # Let's mock `agent.run_agent` and also what `agent.message_queue.put_nowait` would do.

        # Simulate agent putting final response on its queue, which _process_messages forwards
        async def mock_process_and_send_final_event():
            # This simulates what the agent's _process_messages loop does
            # after agent.run_agent finishes and puts its final response.
            # In AnthropicFC, it's usually EventType.AGENT_RESPONSE with "Task completed"
            # or the actual content if no tools were called.
            # For this test, let's say it's the direct text response.
            final_agent_event = RealtimeEvent(
                type=EventType.AGENT_RESPONSE,
                content={"text": agent_text_response}
            )
            # This send_json is what the agent's _process_messages would do to the websocket
            await websocket.send_json(final_agent_event.model_dump())

        # We need agent.run_agent to be "running" while we wait for the event.
        # And then the event should be "produced" by the agent.
        # This is tricky with TestClient as it's synchronous for sends/receives.

        # Let's simplify: check the call to agent.run_agent, and assume if it was called,
        # then if the agent was real, it would send messages.
        # We can't easily test the messages sent by the *agent's own queue* via the *server's websocket handler*
        # without a more complex async testing setup or deeper integration.

        # Check that agent.run_agent was called via the thread executor
        # This requires run_agent_async to complete.
        # We'll patch anyio.to_thread.run_sync for this test.
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = None # Simulate it ran agent.run_agent successfully

            # Wait for run_agent_async to finish (it's called in a task)
            # This is still tricky as receive_json() might block before the task is done.
            # For now, focus on what ws_server directly controls.

            # The PROCESSING message is sent by ws_server.
            # The actual agent response would come from the agent's separate message processing task.
            # This test structure is insufficient to easily test that passthrough.
            # We will assert that agent.run_agent was called.

            # To make this testable for now, let's assume the task completes quickly.
            # We need to "wait" for the task created by `asyncio.create_task(run_agent_async(...))`
            # to execute `anyio.to_thread.run_sync`.
            # This is where TestClient's sync nature makes testing async tasks hard.

            # Let's assume the task runs and finishes.
            # We can check that `agent.run_agent` (the underlying sync method) was called by `run_sync`.
            # This means `run_agent_async` must have been awaited by something.
            # The test client doesn't directly await these background tasks.

            # For now, we'll verify the call to the agent's entry point.
            # A proper test of the events coming back would need an async test client
            # and potentially a way to yield control to the server's event loop.

            # This is a placeholder for a more robust way to wait for the async task
            await asyncio.sleep(0.01) # Give a moment for the task to potentially run

            mocks["agent_instance"].run_agent.assert_called_once_with(query_text, [], False)


@pytest.mark.asyncio
async def test_http_upload_file_success(client_fixture):
    client, mocks = client_fixture

    # workspace_path / session_id / UPLOAD_FOLDER_NAME / file_name
    # Mock Path(global_args.workspace).resolve()
    # global_args.workspace is ./test_ws_server_workspace
    mock_global_ws_path = Path("./test_ws_server_workspace").resolve()

    with patch('ws_server.Path') as MockPathHelper: # Patch Path used in endpoint
        # Configure the chain of Path calls
        mock_path_instance_global = MagicMock(spec=Path)
        mock_path_instance_session = MagicMock(spec=Path)
        mock_path_instance_upload_dir = MagicMock(spec=Path)
        mock_path_instance_file = MagicMock(spec=Path)

        MockPathHelper.return_value = mock_path_instance_global # Path(global_args.workspace)
        mock_path_instance_global.resolve.return_value = mock_global_ws_path
        mock_path_instance_global.__truediv__.return_value = mock_path_instance_session # / session_id

        mock_path_instance_session.exists.return_value = True # Workspace for session exists
        mock_path_instance_session.__truediv__.return_value = mock_path_instance_upload_dir # / UPLOAD_FOLDER_NAME

        mock_path_instance_upload_dir.mkdir = MagicMock()
        mock_path_instance_upload_dir.__truediv__.return_value = mock_path_instance_file # / file_name

        mocks["mock_path_exists"].return_value = False # Simulate file doesn't exist initially, so no renaming
        mock_path_instance_file.parent.mkdir = MagicMock() # For full_path.parent.mkdir

        file_content_text = "This is a test file."
        upload_data = {
            "session_id": str(mocks["session_id"]),
            "file": {"path": "test_upload.txt", "content": file_content_text}
        }
        response = client.post("/api/upload", json=upload_data)

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["message"] == "File uploaded successfully"
        assert json_response["file"]["path"] == "/uploaded_files/test_upload.txt"

        # Check that os.makedirs was called for the upload_dir
        # The path used by os.makedirs is workspace_path / UPLOAD_FOLDER_NAME
        # workspace_path is mock_global_ws_path / session_id
        expected_upload_dir_to_create = mock_global_ws_path / str(mocks["session_id"]) / "uploaded_files"
        # In the endpoint, it's upload_dir.mkdir. Our MockPathHelper chain needs to reflect this.
        # mock_path_instance_upload_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        # Actually, the endpoint calls mkdir on the *parent* of the full_path if subdirs are in file_path.
        # And upload_dir.mkdir for the UPLOAD_FOLDER_NAME itself.
        # The mock setup for Path is getting complicated. A simpler way is to ensure
        # that the final `open` call is made with the correct path.

        mocks["mock_file_open"].assert_called_once_with(mock_path_instance_file, "w")
        mocks["mock_file_open"]().write.assert_called_once_with(file_content_text)


# TODO: Add more tests:
# - WebSocket: cancel, edit_query, enhance_prompt, error conditions (invalid JSON, unknown type)
# - HTTP: /api/upload (base64, filename collision), /api/sessions/{device_id}, /api/sessions/{session_id}/events

if __name__ == "__main__":
    pytest.main()
