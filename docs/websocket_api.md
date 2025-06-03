# WebSocket API Documentation

The II-Agent provides a WebSocket API for real-time, interactive communication. This allows clients (like the provided web frontend or custom applications) to connect to the agent, send commands, and receive updates.

## Connection

*   **Endpoint:** `ws://<host>:<port>/ws` (e.g., `ws://localhost:8000/ws` by default)
*   **Query Parameters:**
    *   `device_id`: An optional client-generated unique identifier for the device or browser instance. This can be used to retrieve session history associated with that device.
*   **Protocol:** Standard WebSocket (RFC 6455)

## Message Format

All messages exchanged over WebSocket are expected to be in JSON format. The server sends messages typed according to the `EventType` enum found in `src/ii_agent/core/event.py`.

### Client-to-Server Messages

Clients send messages to the agent, which are typically JSON objects with a `type` field and a `content` field.

*   **`init_agent`**:
    *   **Purpose:** Initializes or re-initializes the agent for the WebSocket session. This is typically sent after connection establishment.
    *   **`content` Example:**
        ```json
        {
            "model_name": "claude-3-opus-20240229", // Or other supported model
            "tool_args": {
                "sequential_thinking": true,
                "memory_tool": "simple", // e.g., "simple", "compactify-memory", or "none"
                "browser": true,
                "pdf": true,
                "deep_research": false
                // ... other tool configurations
            },
            "thinking_tokens": 0, // For Anthropic models, influences if "thinking" blocks are requested
            "azure_model": false, // For OpenAI client, if using Azure
            "cot_model": false    // For OpenAI client, if it's a Chain-of-Thought optimized model
        }
        ```
    *   **Notes:**
        *   `tool_args`: Controls which optional tools are enabled. See `docs/tools_reference.md`.
        *   The agent for the connection is created/configured based on these settings.

*   **`query`**:
    *   **Purpose:** Sends a new question/task to the agent or continues an existing interaction.
    *   **`content` Example:**
        ```json
        {
            "text": "Write a python script to sort a list of numbers.",
            "resume": false, // `true` if this is a follow-up, `false` for a new query turn
            "files": [ // Optional: list of file paths relative to the agent's workspace/uploads
                "/uploads/my_document.pdf"
            ]
        }
        ```

*   **`edit_query`**:
    *   **Purpose:** Cancels the current agent operation, clears history back to the last user message, and then submits a new query (similar to `query`).
    *   **`content` Example:** (Same as `query`)
        ```json
        {
            "text": "Actually, sort them in descending order.",
            "resume": true, // Typically true when editing
            "files": []
        }
        ```

*   **`cancel`**:
    *   **Purpose:** Requests cancellation of the agent's current long-running operation.
    *   **`content`:** `{}` (empty object)

*   **`enhance_prompt`**:
    *   **Purpose:** Asks the LLM to refine or "enhance" a given prompt before execution.
    *   **`content` Example:**
        ```json
        {
            "model_name": "claude-3-sonnet-20240229",
            "text": "tell me about dogs",
            "files": []
        }
        ```

*   **`ping`**:
    *   **Purpose:** A simple message to keep the connection alive or check responsiveness.
    *   **`content`:** `{}` (empty object)


### Server-to-Client Messages (`RealtimeEvent` objects)

The server (agent) sends `RealtimeEvent` objects to the client. Each event has a `type` (from `EventType` enum) and a `content` payload.

*   **`EventType.CONNECTION_ESTABLISHED`**:
    *   **Purpose:** Sent by the server immediately after a WebSocket connection is accepted.
    *   **`content` Example:**
        ```json
        {
            "message": "Connected to Agent WebSocket Server",
            "workspace_path": "/path/to/current/session/workspace"
        }
        ```

*   **`EventType.AGENT_INITIALIZED`**:
    *   **Purpose:** Confirms that the agent has been initialized for the session based on a client's `init_agent` message.
    *   **`content` Example:** `{"message": "Agent initialized"}`

*   **`EventType.PROCESSING`**:
    *   **Purpose:** Indicates the agent has received a query and is starting to process it.
    *   **`content` Example:** `{"message": "Processing your request..."}`

*   **`EventType.AGENT_THINKING`**: (Primarily for Anthropic models with `thinking_tokens` enabled)
    *   **Purpose:** Streams intermediate "thinking" steps from the LLM.
    *   **`content` Example:** `{"text": "<thinking>I need to first find relevant documents.</thinking>"}`

*   **`EventType.TOOL_CALL`**:
    *   **Purpose:** Informs the client that the agent is about to execute a tool.
    *   **`content` Example:**
        ```json
        {
            "tool_call_id": "tool_call_123",
            "tool_name": "BashTool",
            "tool_input": {"command": "ls -la"}
        }
        ```

*   **`EventType.TOOL_RESULT`**:
    *   **Purpose:** Provides the result obtained from a tool execution.
    *   **`content` Example:**
        ```json
        {
            "tool_call_id": "tool_call_123",
            "tool_name": "BashTool",
            "result": "total 0\ndrwxr-xr-x 1 user group 0 Jan 1 00:00 ."
        }
        ```

*   **`EventType.AGENT_RESPONSE`**:
    *   **Purpose:** Provides a textual response from the agent (can be intermediate or final).
    *   **`content` Example:** `{"text": "Okay, I have listed the files in the current directory."}`

*   **`EventType.AGENT_RESPONSE_INTERRUPTED`**:
    *   **Purpose:** Sent if the agent's response generation was interrupted (e.g., by a `cancel` message).
    *   **`content` Example:** `{"text": "Agent interrupted by user."}`

*   **`EventType.ERROR`**:
    *   **Purpose:** Reports an error that occurred during agent processing or message handling.
    *   **`content` Example:** `{"message": "An error occurred: API key is invalid."}`

*   **`EventType.SYSTEM`**:
    *   **Purpose:** For system-level messages or acknowledgments (e.g., confirming a cancellation).
    *   **`content` Example:** `{"message": "Query cancelled"}`

*   **`EventType.PONG`**:
    *   **Purpose:** Response to a client's `ping` message.
    *   **`content`:** `{}` (empty object)

*   **`EventType.PROMPT_GENERATED`**:
    *   **Purpose:** Returns the result of an `enhance_prompt` request.
    *   **`content` Example:**
        ```json
        {
            "result": "Could you please provide a detailed explanation about the various breeds of dogs, their characteristics, and typical temperaments?",
            "original_request": "tell me about dogs"
        }
        ```
*   **Other Event Types:** Events like `BROWSER_USE` or `FILE_EDIT` may also be emitted to provide more granular insight into tool activities. Refer to `src/ii_agent/core/event.py` for the complete list.

## Session Management

*   Session identity can be implicitly managed by the WebSocket connection lifecycle.
*   The `ws_server.py` creates a unique `session_uuid` and corresponding workspace for each new WebSocket connection. This `session_uuid` is used internally for logging events to the database.
*   The `device_id` query parameter can be used by clients to associate multiple WebSocket sessions (potentially across time) with a single device, allowing retrieval of past session history via HTTP API endpoints (see `ws_server.py` for `/api/sessions/{device_id}`).

## API Endpoints (HTTP)

While the primary interaction is via WebSocket, `ws_server.py` also exposes some HTTP endpoints:

*   **`POST /api/upload`**:
    *   Allows uploading files to a session's workspace.
    *   Requires `session_id` (the UUID of the workspace, typically obtained from `CONNECTION_ESTABLISHED` WebSocket message's `workspace_path`'s last component) and file details in the JSON payload.
*   **`GET /api/sessions/{device_id}`**:
    *   Retrieves a list of past sessions associated with a given `device_id`.
*   **`GET /api/sessions/{session_id}/events`**:
    *   Retrieves all logged events for a specific `session_id`.
*   **`/workspace/...`**:
    *   Serves static files from the agent's workspace if `STATIC_FILE_BASE_URL` is configured to point to the server.

## Further Details

*   For the definitive list of server-to-client `EventType` values and their meanings, please refer to the `EventType` enum in `src/ii_agent/core/event.py`.
*   The exact structure of `tool_args` in the `init_agent` message should align with the configurations expected by `get_system_tools` in `src/ii_agent/tools/tool_manager.py`.

---
*Note: This documentation provides an overview. Specific message payloads and functionalities might evolve. Always refer to the agent's source code (especially `ws_server.py` and `src/ii_agent/core/event.py`) for the most up-to-date and precise details.*
```
