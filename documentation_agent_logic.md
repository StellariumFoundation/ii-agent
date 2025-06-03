# Agent Logic: Orchestration with `AnthropicFC`

The core decision-making and operational flow of II Agent is managed by its agent orchestrator classes. The primary implementation, especially relevant for interactions with Anthropic's language models featuring function calling (tool use), is the `AnthropicFC` class.

## The `AnthropicFC` Class: Primary Orchestrator

The `AnthropicFC` class acts as the central nervous system of the agent. It inherits from `BaseAgent` (which in turn inherits from `LLMTool`, allowing the agent itself to be potentially treated as a tool by a higher-level system), but its main role is to manage the interaction between the user, the Language Model (LLM), the Memory Subsystem, and the Action & Tool Subsystem.

### Initialization

When an `AnthropicFC` instance is created, it's equipped with all the necessary components to function:

*   **`system_prompt` (str):** The foundational instructions that guide the LLM's persona, behavior, and objectives throughout the session.
*   **`client` (LLMClient):** An instance of an LLM client (e.g., for Anthropic's Claude API) used to send requests to and receive responses from the language model.
*   **`tools` (List[LLMTool]):** A list of all available tools that the agent can use. This list is passed to an `AgentToolManager` instance.
*   **`workspace_manager` (WorkspaceManager):** Manages file operations within the agent's designated workspace.
*   **`message_queue` (asyncio.Queue):** A queue for emitting `RealtimeEvent` objects, facilitating logging, database persistence, and potential real-time updates to user interfaces.
*   **`logger_for_agent_logs` (logging.Logger):** A dedicated logger for agent activities.
*   **`context_manager` (ContextManager):** An instance of a context management strategy (e.g., `LLMSummarizingContextManager`) used to initialize the `MessageHistory`.
*   **`max_output_tokens_per_turn` (int):** The maximum number of tokens the LLM is expected to generate in a single turn.
*   **`max_turns` (int):** The maximum number of conversational turns (LLM interactions) the agent will take before stopping if the task is not otherwise completed.
*   **`session_id` (Optional[uuid.UUID]):** A unique identifier for the current session, used for database logging of events.
*   **`interactive_mode` (bool):** Influences which completion tool is used by the `AgentToolManager` (`ReturnControlToUserTool` for interactive, `CompleteTool` for non-interactive).

Internally, `AnthropicFC` initializes:
*   An **`AgentToolManager`** with the provided `tools`.
*   A **`MessageHistory`** object with the provided `context_manager`.

## The Main Run Loop (`run_impl` method)

The heart of `AnthropicFC`'s operation is its `run_impl` method. This method implements the iterative process through which the agent reasons and acts:

1.  **Initialization & Input Processing:**
    *   The loop begins when the agent is called (e.g., via its `run_agent` wrapper). The primary input is an `instruction` from the user, potentially accompanied by `files`.
    *   User input, including paths to any attached files, is formatted and added to the `MessageHistory`. Image files are encoded and added as `ImageBlock` objects.

2.  **Iterative Turns (Loop):** The agent then enters a loop that continues for a configured `max_turns` or until the task is completed or interrupted. Each iteration represents a "turn" of conversation or thought for the agent.

    *   **A. Context Truncation:** At the beginning of each turn, `self.history.truncate()` is called. This invokes the configured `ContextManager` (e.g., `LLMSummarizingContextManager`) to ensure the `MessageHistory` sent to the LLM fits within its token budget, summarizing older parts if necessary.

    *   **B. LLM Consultation:** The agent prepares the request for the LLM. This includes:
        *   The (potentially truncated) `MessageHistory`.
        *   The list of available tool parameters (names, descriptions, input schemas) obtained from `self.tool_manager._validate_tool_parameters()`.
        *   The `system_prompt`.
        The request is then sent to the LLM via `self.client.generate()`.

    *   **C. Processing LLM's Response:** The LLM's response is added to `MessageHistory`. This response can contain:
        *   **Textual Content (`TextResult`):** The LLM's direct textual reply, thoughts, or plans.
        *   **Tool Call Requests (`ToolCall`):** Structured requests for the agent to use one or more tools, specifying the tool's name and its input parameters.

    *   **D. Action & Decision Making:**
        *   **No Tool Calls:** If the LLM's response contains no tool call requests, `AnthropicFC` currently assumes the task is complete or the LLM is providing a final answer. The last textual response from the LLM is typically returned as the result.
        *   **Tool Call Execution:** If the LLM requests a tool (currently, `AnthropicFC` processes one tool call per turn):
            1.  A `TOOL_CALL` event is emitted to the `message_queue`.
            2.  The agent orchestrator instructs `self.tool_manager.run_tool()` to execute the specified tool with the LLM-provided inputs.
            3.  The tool executes, and its output (a string or structured data) is captured.
            4.  This `tool_result` is added to `MessageHistory` as a `ToolFormattedResult` and a `TOOL_RESULT` event is emitted to the `message_queue`.
        *   **Stopping Conditions:** The loop can terminate if:
            *   The LLM makes no tool calls (implying task completion).
            *   An executed tool signals task completion (e.g., `ReturnControlToUserTool` via `self.tool_manager.should_stop()`).
            *   The `max_turns` limit is reached.
            *   An interruption signal is received (`self.interrupted` is set to `True`).

## Event Emission for Observability

Throughout its operation, `AnthropicFC` emits `RealtimeEvent` objects to the `message_queue`. This is handled by the `_process_messages` asynchronous task, which:

*   Saves every event to a database if a `session_id` is configured (via `DatabaseManager`).
*   Forwards events (except user messages) to a connected WebSocket client, enabling real-time UI updates or external monitoring.

Events include `TOOL_CALL`, `TOOL_RESULT`, `AGENT_RESPONSE`, `AGENT_THINKING` (if the LLM provides intermediate thoughts), errors, and more, providing a detailed trace of the agent's activities.

## Role of System Prompts

The `system_prompt` provided during `AnthropicFC` initialization plays a critical and continuous role:

*   **Behavioral Guidance:** It sets the LLM's persona, tone, and high-level instructions on how to approach tasks.
*   **Tool Usage Encouragement:** It often contains guidelines on when and how to use tools, encouraging the LLM to leverage its available capabilities.
*   **Response Formatting:** It might specify how the LLM should structure its responses or thoughts.
*   **Constraint Adherence:** It can include rules or constraints that the LLM should follow.

For specific benchmarks like GAIA, a specialized system prompt (e.g., `GAIA_SYSTEM_PROMPT`) is used. This prompt is tailored to the types of tasks and desired outcomes of the benchmark, further refining the LLM's behavior to optimize performance in that context. The system prompt is part of every call to `self.client.generate()`, ensuring it consistently influences the LLM's decision-making within the main loop.

By orchestrating these components within its main run loop, `AnthropicFC` enables II Agent to engage in complex, tool-augmented reasoning, manage its conversational memory effectively, and provide traceable, event-driven execution.
