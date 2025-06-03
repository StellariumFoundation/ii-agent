# II Agent: Developer Guide and Architectural Deep Dive

## 1. Introduction

Welcome to the developer documentation for **II Agent**, an advanced AI assistant engineered for tackling complex, real-world tasks that demand sophisticated reasoning, research, and tool utilization.

II Agent has demonstrated exceptional capabilities, notably achieving strong performance on the challenging **GAIA benchmark**. This success underscores its proficiency in understanding intricate problems and navigating multi-step solution paths that often require interaction with diverse information sources and execution environments.

At the heart of II Agent's performance are two key architectural pillars:

1.  **Sophisticated Memory Management:** The agent employs an intelligent context management system that goes beyond simple history truncation. By leveraging LLM-driven summarization, it maintains a rich, long-term understanding of the conversational and operational context, ensuring that critical information is preserved even during extended interactions.
2.  **Versatile Action Toolkit & Orchestration:** II Agent is equipped with a comprehensive suite of tools enabling it to interact with filesystems, execute code in sandboxed environments, browse the web, process multimedia content, and even engage in structured, sequential thinking to break down complex problems. A robust agent core orchestrates these tools based on LLM-driven decisions, allowing for dynamic and adaptive task execution.

The purpose of this document is to provide developers with a comprehensive understanding of II Agent's architecture and implementation. We will delve into the core components, data flows, and design choices that underpin its capabilities, offering insights into how these elements contribute to its robust performance on benchmarks like GAIA and its potential for tackling a wide array of complex AI-driven tasks.

Whether you're looking to extend the agent's functionalities, integrate it into other systems, or simply understand the mechanics behind a high-performing AI agent, this documentation will serve as your guide.

## 2. Core Architecture Overview

II Agent is built upon a modular architecture designed to separate concerns and enable sophisticated, multi-turn, tool-assisted reasoning. At a high level, the system comprises several key components that work in concert to process information, make decisions, and execute tasks.

The primary components are:

1.  **Main Agent Orchestrator (`AnthropicFC` class):**
    *   **Role:** This is the central "brain" of the agent. It manages the overall lifecycle of a task, from receiving user input to generating a final response. It orchestrates the flow of information and control between all other components.
    *   **Details:** Implemented in classes like `AnthropicFC` (for Anthropic models with function calling), it contains the main operational loop. This will be detailed further in the "Agent Logic" section.

2.  **Language Model (LLM) Client (`LLMClient` implementations):**
    *   **Role:** This component is responsible for all direct communication with the underlying large language model (e.g., Anthropic's Claude). It handles prompt formatting, sending requests to the LLM API, and receiving the LLM's responses (which may include text generation and tool call requests).
    *   **Details:** Abstracted via `LLMClient` (e.g., `ii_agent.llm.anthropic.AnthropicLLMClient`), allowing for different LLM backends.

3.  **Memory Subsystem (`MessageHistory` & `ContextManager`):**
    *   **Role:** This subsystem is responsible for maintaining the agent's understanding of the current task and conversation. It stores the history of interactions (user prompts, agent replies, tool usage) and employs strategies to manage this history within the LLM's context window limitations.
    *   **Details:** Primarily consists of the `MessageHistory` class, which holds the sequence of events, and `ContextManager` implementations (like `LLMSummarizingContextManager`) that handle context compression and truncation. This is explored in detail in the "Memory Management" section.

4.  **Tool Subsystem (`LLMTool`, `AgentToolManager`):**
    *   **Role:** This provides the agent with its capabilities to interact with its environment and perform actions beyond simple text generation. Tools can range from file system operations and web browsing to code execution and complex reasoning aids.
    *   **Details:** Built around the `LLMTool` base class, with concrete tool implementations (e.g., `WebSearchTool`, `BashTool`, `SequentialThinkingTool`). The `AgentToolManager` is responsible for discovering, managing, and safely executing these tools based on requests from the Main Agent Orchestrator (which are in turn based on LLM outputs). This is detailed in the "Action & Tool Subsystem" section.

### Component Interaction Flow

The interaction between these components follows a general pattern:

1.  **Input:** The **Main Agent Orchestrator** receives an initial instruction or query from the user (e.g., via `run_agent` method in `AnthropicFC`). This input is added to the **Memory Subsystem** (`MessageHistory`).

2.  **Context Preparation:** The Orchestrator, before querying the LLM, ensures the current `MessageHistory` is within token limits by calling the `truncate()` method of the `ContextManager` within the **Memory Subsystem**.

3.  **LLM Consultation & Decision Making:** The Orchestrator sends the prepared history (including the current query, past interactions, and system prompt) to the **LLM Client**. The LLM processes this context and returns a response. This response might be:
    *   A direct textual answer.
    *   A request to call one or more tools (function calls), specifying the tool name and input parameters.
    *   A combination of text and tool calls.

4.  **Action Execution (Tool Use):**
    *   If the LLM requests a tool call, the **Main Agent Orchestrator** instructs the **Tool Subsystem** (specifically, the `AgentToolManager`) to execute the specified tool with the given parameters.
    *   The `AgentToolManager` invokes the tool's `run()` method. The tool performs its action (e.g., searches the web, writes to a file).
    *   The result of the tool execution is captured by the `AgentToolManager` and returned to the Orchestrator.

5.  **Memory Update & Iteration:**
    *   The Orchestrator adds the LLM's textual response (if any) and the tool call results to the **Memory Subsystem** (`MessageHistory`).
    *   If the task is not yet complete (e.g., the LLM needs to process tool results or the invoked tool doesn't signal completion), the loop repeats from step 2 (Context Preparation). The agent iterates, using the updated history to inform the LLM for subsequent decisions and actions.

6.  **Output & Task Completion:**
    *   When the LLM indicates the task is complete (typically by not requesting further tool calls) or a tool signals completion (e.g., `ReturnControlToUserTool`), the **Main Agent Orchestrator** finalizes the process.
    *   The final response (usually the last textual output from the LLM or a result from a completion tool) is provided.

7.  **Eventing (Throughout):**
    *   Throughout this entire process, various components (especially the Main Agent Orchestrator and tools) may generate `RealtimeEvent` objects that are placed onto a message queue. These events can be used for logging, database persistence (`DatabaseManager`), and real-time updates to external interfaces (like a WebSocket connection).

This cyclical process of memory update, LLM consultation, and action execution allows II Agent to handle complex, multi-step tasks by building context and iteratively refining its approach.

## 3. Memory Management in II Agent

Effective memory management is crucial for enabling II Agent to handle long, complex conversations and multi-step tasks while staying within the token limits of Large Language Models (LLMs). This section delves into the key components responsible for tracking dialogue history and applying context compression strategies.

### `MessageHistory`: Tracking the Conversation

The `MessageHistory` class is the cornerstone of the agent's short-term and long-term memory.

*   **Role:** It meticulously records the chronological sequence of all interactions within a session. This includes:
    *   User inputs (text prompts and image attachments).
    *   Agent's textual responses.
    *   Tool calls initiated by the agent (based on LLM requests).
    *   Results returned from tool executions.
*   **Structure:** The history is stored as a list of "turns," where each turn is itself a list of `GeneralContentBlock` objects (e.g., `TextPrompt`, `TextResult`, `ToolCall`, `ToolFormattedResult`, `ImageBlock`). This structured format allows the agent and the LLM to differentiate between various types of information and understand the flow of the dialogue accurately.
*   **Integrity:** `MessageHistory` includes mechanisms like `_ensure_tool_call_integrity` to clean up any orphaned tool calls or results, ensuring the LLM receives a coherent and consistent history.
*   **Interface:** It provides methods to add user and assistant turns, retrieve pending tool calls, add tool call results, and get messages formatted for the LLM.

### `ContextManager`: Abstracting Compression Strategies

The `ContextManager` is an abstract base class that defines the interface for various context management strategies.

*   **Responsibility:** Its primary responsibility is to ensure that the conversation history provided to the LLM does not exceed its predefined token budget.
*   **Token Counting:** It implements a `count_tokens` method, which intelligently calculates the token cost of a list of message turns. This method is aware of different content block types and applies specific counting logic (e.g., estimating costs for images, only counting thinking blocks in the last turn).
*   **Truncation Logic:**
    *   `should_truncate()`: Determines if the current history exceeds the token budget.
    *   `apply_truncation_if_needed()`: A final method that calls the specific truncation strategy if needed.
    *   `apply_truncation()`: An abstract method that concrete subclasses must implement to define how the history should be condensed.

### `LLMSummarizingContextManager`: Intelligent Context Compression

This is a sophisticated implementation of `ContextManager` that uses an LLM to summarize older parts of the conversation, rather than simply truncating them.

*   **Mechanism:**
    1.  **Triggering Conditions:** Summarization is triggered if the total token count exceeds the `token_budget` OR if the number of distinct message turns exceeds a configured `max_size`.
    2.  **History Segmentation:** When triggered, it divides the history into three parts:
        *   `head`: A configurable number of initial messages (defined by `keep_first`) are always preserved (e.g., the system prompt and initial user query).
        *   `tail`: A calculated number of the most recent messages are also preserved to maintain immediate context.
        *   `forgotten_events`: The messages between the `head` and `tail` (potentially including a previous summary) become candidates for summarization.
    3.  **Summarization Prompt:** A detailed prompt is constructed and sent to an LLM. This prompt instructs the summarizer LLM to extract key information, including:
        *   `USER_CONTEXT`: Essential user requirements and goals.
        *   `COMPLETED`: Tasks completed so far.
        *   `PENDING`: Tasks yet to be done.
        *   `CURRENT_STATE`: Relevant variables or state.
        *   Specific fields for coding tasks (`CODE_STATE`, `TESTS`, `CHANGES`, etc.).
        The prompt also includes any `<PREVIOUS SUMMARY>` to allow for continuous, rolling summarization.
    4.  **History Reconstruction:** The `LLMSummarizingContextManager` replaces the `forgotten_events` in the `MessageHistory` with a single new `TextPrompt` containing the LLM-generated summary, prefixed with "Conversation Summary:". The history then consists of `head` + `summary` + `tail`.
*   **Benefits:** This approach aims to retain vital information from earlier in the conversation in a compressed format, allowing the agent to maintain long-term context and coherence.
*   **Configuration:** Key parameters include `token_budget`, `max_size` (max number of turns before summarization), and `keep_first` (number of initial turns to always keep).

### Memory-Related Tools

II Agent also provides tools that allow the agent (or the LLM guiding it) to interact with its memory systems more explicitly.

*   **`CompactifyMemoryTool`:**
    *   **Role:** This tool allows the agent to proactively trigger the memory compaction process using the currently configured `ContextManager` (e.g., `LLMSummarizingContextManager`).
    *   **Function:** When called, it invokes the context manager's `apply_truncation_if_needed` method on the current `MessageHistory`. This can be useful if the agent anticipates needing more context space for an upcoming complex operation or if it wants to explicitly consolidate its understanding.
    *   **Usage:** The LLM might decide to call this tool if it recognizes the conversation history is becoming very long or if it's about to undertake a particularly token-intensive step.

*   **`SimpleMemoryTool`:**
    *   **Role:** This tool provides a persistent, string-based key-value scratchpad for the agent. It's a simpler form of memory, distinct from the conversational `MessageHistory`.
    *   **Function:** It typically supports operations like:
        *   Writing a string value to a specified key.
        *   Reading the string value associated with a key.
        *   Appending to an existing string value.
        *   Deleting a key-value pair.
    *   **Usage:** The agent can use this to store temporary notes, reminders, intermediate calculations, or small pieces of information it needs to recall later within the same session, without cluttering the main conversational history meant for the LLM's primary context.

### Importance for Agent Performance

The combination of detailed `MessageHistory` tracking and intelligent context management via `LLMSummarizingContextManager` is vital for II Agent's ability to perform well on complex, long-running tasks like those in the GAIA benchmark. It allows the agent to:

*   **Maintain Long-Term Coherence:** By not losing critical early instructions or facts.
*   **Stay Within LLM Limits:** Preventing errors and ensuring the LLM can process the provided context.
*   **Make Informed Decisions:** By having access to a richer, albeit summarized, history.

The explicit memory tools (`CompactifyMemoryTool`, `SimpleMemoryTool`) offer additional layers of control and utility, further enhancing the agent's ability to manage and leverage information effectively.

## 4. Action & Tool Subsystem

II Agent's ability to perform actions, interact with environments, and go beyond simple text generation is powered by its robust Action & Tool Subsystem. This subsystem allows the agent to leverage a wide array of capabilities to accomplish complex tasks.

> **A note on terminology:** 'Tool Use' is the general concept of the agent utilizing external functionalities. 'Function Calling' is a specific mechanism some LLM providers (like Anthropic with `AnthropicFC`) use to implement tool use, where the LLM predicts a 'function call' that the agent then executes.

### `LLMTool`: The Foundation for Agent Capabilities

The `LLMTool` class is an abstract base class that defines a standardized interface for all tools available to II Agent. Every tool must inherit from `LLMTool`.

Its core components are:

*   **`name` (str):** A unique identifier for the tool. This is the name the LLM will use when requesting the tool's execution.
*   **`description` (str):** A detailed natural language description of what the tool does, when it should be used, and what its expected inputs and outputs are. **This description is critical**, as the LLM relies heavily on it to determine the appropriateness of the tool for a given situation.
*   **`input_schema` (dict):** A JSON schema defining the structure and data types of the parameters the tool expects. This schema helps the LLM formulate valid inputs for the tool and allows for input validation before execution.
*   **`run_impl(tool_input: dict, message_history: Optional[MessageHistory]) -> ToolImplOutput` (abstract method):** This is the core method that concrete tool classes must implement. It contains the actual logic for the tool's operation. It takes the validated `tool_input` and an optional `message_history` (for context-aware tools) and returns a `ToolImplOutput` object (which includes the primary output for the LLM and logging information).

The clarity and accuracy of the `description` and `input_schema` directly impact the LLM's ability to effectively and correctly utilize a tool.

### `AgentToolManager`: Managing and Executing Tools

The `AgentToolManager` is a central component responsible for the lifecycle and execution of tools within the agent.

*   **Role:**
    *   **Discovery and Loading:** It holds and manages all the `LLMTool` instances that are available to the agent during a session. The `get_system_tools()` function plays a key role here, dynamically assembling a list of tools based on configuration (`tool_args`) and environment settings. This allows for conditional loading of tools, meaning the agent's capabilities can be tailored (e.g., enabling browser tools or advanced media tools only when needed).
    *   **Provision to Agent:** It provides the main agent orchestrator (e.g., `AnthropicFC`) with the list of available tools and their parameters, which are then typically passed to the LLM to inform it of its available actions.
    *   **Execution:** When the LLM requests a tool call, the `AgentToolManager` is responsible for finding the correct tool by name and invoking its `run()` method with the parameters provided by the LLM. It also handles logging of tool execution.

### Tool Execution Flow

The process of using a tool typically follows this sequence:

1.  **LLM Decision:** The main agent orchestrator (e.g., `AnthropicFC`) queries the LLM with the current `MessageHistory` and the list of available tools (names, descriptions, schemas). The LLM analyzes the request and decides if a tool is needed to proceed.
2.  **Tool Call Request:** If the LLM decides to use a tool, its response will include a structured request, specifying the `tool_name` and `tool_input` (parameters).
3.  **Delegation to `AgentToolManager`:** The agent orchestrator receives this tool call request from the LLM. It then passes these details (`ToolCallParameters`) to the `AgentToolManager`'s `run_tool()` method.
4.  **Tool Invocation:** The `AgentToolManager` looks up the specified tool by its name and calls its `run()` method (which, in turn, validates the input against the tool's schema and then calls `run_impl()`).
5.  **Result Processing:** The tool executes its logic and returns a `ToolImplOutput`. The primary `tool_output` string (or list of dicts) from this object is what gets passed back.
6.  **Memory Update:** The agent orchestrator adds the tool's output to the `MessageHistory` as a `ToolFormattedResult`, associating it with the original `ToolCall`.
7.  **Iteration:** This updated `MessageHistory` (now including the outcome of the tool's action) is then used in the next cycle of LLM consultation, allowing the agent to process the tool's results and decide on subsequent steps.

### Showcase of Key Tools

II Agent is equipped with a variety of tools, and its architecture is designed to be extensible. Here are some of the key tools that contribute to its performance:

*   **`SequentialThinkingTool`:**
    *   This tool is paramount for complex reasoning. It guides the LLM through a structured, iterative process of breaking down problems, planning, and revising thoughts, enabling more robust solutions to challenging tasks.

*   **Browser Tools (e.g., `BrowserNavigationTool`, `BrowserViewTool`, `BrowserClickTool`, `BrowserEnterTextTool`, `BrowserScrollDownTool`):**
    *   This suite of tools provides the agent with the ability to interact with live websites. It can navigate to URLs, view page content (often processed to be LLM-friendly), click on elements, enter text into forms, and scroll, effectively allowing the agent to "use" a web browser to gather information or perform actions.

*   **`WebSearchTool`:**
    *   Enables the agent to perform web searches using search engines to find information relevant to the user's query or ongoing task. This is often a precursor to using browser tools to visit specific pages.

*   **`BashTool` (and `DockerBashTool`):**
    *   Provides a powerful capability to execute shell commands within a controlled environment (either the host system's workspace or a dedicated Docker container via `DockerBashTool`). This allows for file system operations (listing, reading, writing), running scripts, and general code execution.

*   **`StrReplaceEditorTool`:**
    *   Offers a precise way to make modifications to files within the agent's workspace. Instead of rewriting entire files, the agent can specify search patterns and replacement strings, enabling targeted edits to code or text documents.

### Extensibility

The tool subsystem is designed for extensibility. Developers can create new tools by subclassing `LLMTool`, defining its `name`, `description`, `input_schema`, and implementing its `run_impl` method. These new tools can then be registered with the system via `get_system_tools` (often by modifying the conditional logic based on `tool_args` or other configurations), expanding the agent's capabilities.

### Configuring Tools with `tool_args`

The `get_system_tools()` function in `src/ii_agent/tools/tool_manager.py` accepts a `tool_args` dictionary. This dictionary allows for conditional loading and configuration of certain tools at runtime, providing flexibility in tailoring the agent's capabilities for different scenarios.

**How `tool_args` is Populated:**

*   **Via Command-Line Interface (`cli.py`):**
    When running the agent via `cli.py`, command-line flags are parsed and translated into a `tool_args` dictionary. For example, the `--memory-tool simple` CLI argument would result in `tool_args` containing an entry like `{"memory_tool": "simple"}`, which `get_system_tools` then uses to instantiate `SimpleMemoryTool`. Other tools might be enabled or disabled by boolean flags that populate `tool_args` (e.g., `{"deep_research": True}`).

    *Example (conceptual from `cli.py`):*
    ```python
    # In cli.py (simplified)
    args = parser.parse_args()
    tool_args_config = {
        "deep_research": args.deep_research_flag, # Assuming a CLI flag
        "pdf": True, # Example of a tool enabled by default in CLI
        "memory_tool": args.memory_tool # e.g., "simple", "compactify-memory", "none"
        # ... other tool configurations based on CLI args
    }
    tools = get_system_tools(..., tool_args=tool_args_config)
    ```

*   **Via WebSocket Server (`ws_server.py`):**
    When the agent is initialized via a WebSocket connection (typically through an `init_agent` message), the client can send a `tool_args` JSON object within the message payload. The `ws_server.py` then passes this dictionary to `get_system_tools`.

    *Example (JSON payload for `init_agent` WebSocket message):*
    ```json
    {
        "type": "init_agent",
        "content": {
            "model_name": "claude-3-opus-20240229",
            "tool_args": {
                "sequential_thinking": true,
                "browser": true,
                "pdf": false, // Example: disabling a tool
                "memory_tool": "simple"
            }
            // ... other options
        }
    }
    ```

*   **Manual Instantiation (`run_gaia.py`):**
    It's important to note that not all execution paths use the dynamic `tool_args` mechanism with `get_system_tools`. For instance, `run_gaia.py` manually instantiates a specific list of tools tailored for the GAIA benchmark tasks and passes them directly to the agent constructor. In such cases, `tool_args` as described above is not used.

Refer to `docs/tools_reference.md` for a list of tools and their potential configuration via `tool_args`. The most definitive source for how `tool_args` are interpreted is the `get_system_tools` function in `src/ii_agent/tools/tool_manager.py`.

By combining a well-defined tool interface (`LLMTool`), a robust management system (`AgentToolManager`), and a diverse set of built-in tools, II Agent can perform a wide range of actions necessary to address complex, real-world problems like those presented in the GAIA benchmark.

## 5. Agent Logic: Orchestration with `AnthropicFC`

The core decision-making and operational flow of II Agent is managed by its agent orchestrator classes. The primary implementation, especially relevant for interactions with Anthropic's language models featuring function calling (tool use), is the `AnthropicFC` class.

### The `AnthropicFC` Class: Primary Orchestrator

The `AnthropicFC` class acts as the central nervous system of the agent. It inherits from `BaseAgent` (which in turn inherits from `LLMTool`, allowing the agent itself to be potentially treated as a tool by a higher-level system), but its main role is to manage the interaction between the user, the Language Model (LLM), the Memory Subsystem, and the Action & Tool Subsystem.

#### Initialization

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

#### The Main Run Loop (`run_impl` method)

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

#### Event Emission for Observability

Throughout its operation, `AnthropicFC` emits `RealtimeEvent` objects to the `message_queue`. This is handled by the `_process_messages` asynchronous task, which:

*   Saves every event to a database if a `session_id` is configured (via `DatabaseManager`).
*   Forwards events (except user messages) to a connected WebSocket client, enabling real-time UI updates or external monitoring.

Events include `TOOL_CALL`, `TOOL_RESULT`, `AGENT_RESPONSE`, `AGENT_THINKING` (if the LLM provides intermediate thoughts), errors, and more, providing a detailed trace of the agent's activities.

#### Role of System Prompts

The `system_prompt` provided during `AnthropicFC` initialization plays a critical and continuous role:

*   **Behavioral Guidance:** It sets the LLM's persona, tone, and high-level instructions on how to approach tasks.
*   **Tool Usage Encouragement:** It often contains guidelines on when and how to use tools, encouraging the LLM to leverage its available capabilities.
*   **Response Formatting:** It might specify how the LLM should structure its responses or thoughts.
*   **Constraint Adherence:** It can include rules or constraints that the LLM should follow.

For specific benchmarks like GAIA, a specialized system prompt (e.g., `GAIA_SYSTEM_PROMPT`) is used. This prompt is tailored to the types of tasks and desired outcomes of the benchmark, further refining the LLM's behavior to optimize performance in that context. The system prompt is part of every call to `self.client.generate()`, ensuring it consistently influences the LLM's decision-making within the main loop.

By orchestrating these components within its main run loop, `AnthropicFC` enables II Agent to engage in complex, tool-augmented reasoning, manage its conversational memory effectively, and provide traceable, event-driven execution.

## 6. GAIA Benchmark Setup & Execution

The `run_gaia.py` script is used to evaluate II Agent against the GAIA benchmark.

### Purpose of `run_gaia.py`

*   Loads GAIA dataset questions.
*   Initializes `AnthropicFC` with a GAIA-optimized configuration.
*   Manages task environments and iterates through questions.
*   Logs detailed results for analysis.

### Agent Initialization for GAIA

*   **LLM Client:** Typically an Anthropic client.
*   **System Prompts:** Uses `GAIA_SYSTEM_PROMPT` for tailored guidance.
*   **Memory:** `LLMSummarizingContextManager` is used for `MessageHistory`.
*   **Mode:** `interactive_mode=False` for automated execution.

### Tool Configuration for GAIA

`run_gaia.py` manually instantiates a curated list of tools suitable for GAIA tasks, including `SequentialThinkingTool`, web search/browsing tools, `BashTool`, `StrReplaceEditorTool`, and multimedia tools.

### Task Processing Loop

*   Loads dataset, filters tasks, and can resume previous runs.
*   Uses `answer_single_question` (often concurrently) to process each task. This function sets up the environment, augments the question, and calls `agent.run_agent()`.

### Workspace Management

*   Creates a dedicated workspace directory (`workspace/<task_id>`) for each task, managed by a `WorkspaceManager` instance.
*   Associated files for GAIA questions are copied into this workspace.

### Data Logging for Evaluation

*   General agent logs are saved to a file.
*   A primary JSONL output file records per-task details: question, prediction, errors, timings, and workspace ID.
*   If a `session_id` is used, all `RealtimeEvent`s are logged to a database for granular tracing.

### Customization for Developers by Adapting `run_gaia.py`

Developers can use `run_gaia.py` as a template to:
*   Evaluate on custom datasets.
*   Test different agent configurations (prompts, models, tools).
*   Experiment with context management strategies.

## 7. Extending and Customizing II Agent

This section provides practical instructions for developers looking to extend II Agent's capabilities, modify its behavior, or set up a development environment.

### Adding New Tools

Tools are the primary way to expand what II Agent can do. Here's how to create and integrate a new tool:

1.  **Create a New Tool Class:**
    *   Create a new Python file (e.g., `my_custom_tool.py`) typically within a relevant subdirectory of `src/ii_agent/tools/`.
    *   Define a new class that inherits from `LLMTool` (from `src/ii_agent/tools/base.py`).

2.  **Define `name`, `description`, and `input_schema`:**
    *   **`name` (str):** A unique, descriptive, snake_case name for your tool. This is how the LLM will refer to it.
    *   **`description` (str):** A detailed explanation of what the tool does, its purpose, when it should be used, and what kind of output it produces. This is **critical** for the LLM to understand and use your tool correctly.
    *   **`input_schema` (dict):** A JSON schema defining the expected input parameters, their types, and whether they are required.

3.  **Implement the `run_impl` Method:**
    *   This method contains the core logic of your tool. It takes `tool_input` (a dictionary validated against your `input_schema`) and an optional `message_history`.
    *   It should return a `ToolImplOutput` object.

4.  **Register the New Tool:**
    *   To make the tool available to the agent, it needs to be added to the list of tools that `AgentToolManager` manages.
    *   The primary way to do this is by modifying the `get_system_tools` function in `src/ii_agent/tools/tool_manager.py`.
    *   Import your new tool class and add an instance of it to the `tools` list, often within a conditional block if its availability depends on configuration (`tool_args`) or environment variables.
    *   Alternatively, if you are instantiating an agent directly (like in `run_gaia.py`), you can add your tool instance to the list of tools passed to the agent's constructor.

### Modifying System Prompts

*   **Location:**
    *   General system prompts: `src/ii_agent/prompts/system_prompt.py`.
    *   GAIA-specific prompt: `src/ii_agent/prompts/gaia_system_prompt.py`.
*   **Effective Prompt Engineering:**
    *   **Clarity and Specificity:** Clearly define the agent's role, desired response style, constraints, and how it should approach tasks.
    *   **Tool Usage Guidance:** Explicitly encourage or guide tool usage.
    *   **Iterative Refinement:** Prompt engineering is often an iterative process. Test changes and observe their impact on agent behavior.
*   **Caution:** Small changes to system prompts can significantly alter agent performance and reliability. Thoroughly test any modifications.

### Changing Context Management Strategy

*   **Switching Implementations:** If you create a new `ContextManager` subclass, you would change it where the context manager is instantiated (e.g., in `run_gaia.py` or your custom agent setup script) and pass it to the `MessageHistory` constructor.
*   **Adjusting `LLMSummarizingContextManager`:**
    *   Parameters like `token_budget`, `max_size` (max number of turns before summarization), and `keep_first` (initial turns to always keep) can be modified when `LLMSummarizingContextManager` is instantiated.

### Testing Your Custom Tools

Developing robust tools requires thorough testing. It's highly recommended to test your tools in isolation before integrating them into the main agent.

**Key Principles:**

*   **Unit Testing:** Focus on testing individual methods of your tool class with various inputs, including edge cases.
*   **Isolation:** Test the tool independently of the LLM and the main agent loop as much as possible.
*   **Mocking Dependencies:** If your tool interacts with external APIs, databases, or services, use mocking libraries (like Python's `unittest.mock`) to simulate these dependencies. This makes your tests faster, more reliable, and avoids external service costs or rate limits during testing.

**Example Test Script Template:**

Below is a basic template you can adapt for testing your custom tool.

```python
# Example Test Script for a Custom Tool
import asyncio
import unittest.mock # For mocking dependencies

# Assuming your tool and its base classes are structured like this:
# from src.ii_agent.tools.base import ToolImplOutput # Adjust if your base class/output differ
# from src.ii_agent.tools.my_custom_tool_module import YourCustomTool # Import your tool

# Mock ToolImplOutput if it's complex or for simplicity in this example
class MockToolImplOutput:
    def __init__(self, tool_output, tool_result_message="", auxiliary_data=None):
        self.tool_output = tool_output
        self.tool_result_message = tool_result_message
        self.auxiliary_data = auxiliary_data if auxiliary_data is not None else {}

# Example: A mock for a dependency your tool might have
class MockExternalService:
    async def fetch_data(self, query: str):
        print(f"[MockExternalService] Received query: {query}")
        if query == "valid_query":
            return {"status": "success", "data": "mocked_data"}
        return {"status": "error", "data": "not_found"}

# Define YourCustomTool here for runnable example, or import it
class YourCustomTool: # Replace with your actual tool import
    name = "your_custom_tool"
    description = "A custom tool for testing."
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }

    def __init__(self, external_service=None):
        self.external_service = external_service

    async def run_impl(self, tool_input: dict, message_history=None) -> MockToolImplOutput:
        print(f"[{self.name}] Running with input: {tool_input}")
        query = tool_input.get("query")
        if self.external_service:
            service_response = await self.external_service.fetch_data(query)
            output = f"Service response: {service_response}"
            return MockToolImplOutput(tool_output=output, tool_result_message="Fetched from service")
        else:
            output = f"Processed query: {query}"
            return MockToolImplOutput(tool_output=output, tool_result_message="Processed directly")

async def main():
    # Instantiate your tool
    # If it has dependencies, you might inject mocks here
    mock_service = MockExternalService()
    tool_under_test = YourCustomTool(external_service=mock_service)
    # tool_under_test_no_deps = YourCustomTool()


    print(f"Testing {tool_under_test.name}...")

    # Test case 1: With mocked external service
    test_input_1 = {"query": "valid_query"}
    print(f"\nTest Case 1 Input: {test_input_1}")
    result_1 = await tool_under_test.run_impl(test_input_1)
    print(f"Output: {result_1.tool_output}")
    print(f"Result Message: {result_1.tool_result_message}")
    # Add assertions here:
    # assert "mocked_data" in result_1.tool_output

    # Test case 2: Another scenario
    # test_input_2 = {"query": "another_value"}
    # print(f"\nTest Case 2 Input: {test_input_2}")
    # result_2 = await tool_under_test_no_deps.run_impl(test_input_2) # Example with a different instance or input
    # print(f"Output: {result_2.tool_output}")
    # print(f"Result Message: {result_2.tool_result_message}")
    # assert "another_value" in result_2.tool_output

    print("\nAll tests for YourCustomTool completed.")

if __name__ == "__main__":
    asyncio.run(main())
```

**Running Tests:**
Save your test script (e.g., `test_my_tool.py`) and run it directly: `python test_my_tool.py`. Integrate such scripts into your development workflow and consider adding them to a dedicated `tests/tools/` directory if you build a suite of tool tests.

### Error Handling in the Agent

Understanding how errors are managed is important both for using the agent and for developing new tools.

*   **Tool-Originated Errors:**
    *   When developing a custom tool, if the tool encounters an unrecoverable error or an invalid state, it should generally raise a Python exception (e.g., `ValueError`, `RuntimeError`, or a custom exception type).
    *   Provide clear and descriptive error messages in your exceptions, as these messages are often what the agent or user will see.

*   **AgentToolManager Error Catching:**
    *   The `AgentToolManager` (specifically its `run_tool` method) has a try-except block that catches exceptions raised during the execution of a tool's `run` or `run_impl` method.
    *   When an exception is caught, the `AgentToolManager` typically formats the error into a user-friendly string. This string usually includes the name of the tool that failed and the error message from the exception. This formatted error string then becomes the "output" of the tool for that turn.

*   **Communication of Errors:**
    *   **To the LLM:** The formatted error string from the `AgentToolManager` is passed back to the LLM as the result of the tool call. This allows the LLM to understand that the tool execution failed and potentially try a different approach or inform the user.
    *   **To the User/Client:**
        *   **WebSocket API:** For agents running via `ws_server.py`, an `EventType.ERROR` event is usually emitted to the client, containing the error message. More granular tool errors might also be part of the `EventType.TOOL_RESULT` if the tool itself handles an error and returns a specific error message as its output.
        *   **CLI:** In `cli.py`, errors encountered during tool execution are typically logged to the console and the agent log file.

*   **Best Practices for Custom Tools:**
    *   Catch expected exceptions within your tool if you can handle them gracefully or provide a more specific error message as the tool's output.
    *   For unexpected or unrecoverable issues, let exceptions propagate to be caught by the `AgentToolManager`.
    *   Use informative error messages in your exceptions.

By following these principles, error information can flow effectively through the system, aiding in debugging and allowing the LLM and users to react appropriately to tool failures.

### Customizing Agent Behavior

*   **Modifying `AnthropicFC`:** For deep customizations to the agent's core loop or decision-making logic, you might consider modifying `src/ii_agent/agents/anthropic_fc.py`. However, this is complex and should be done with a thorough understanding of the existing architecture.
*   **LLM Clients:** The system is designed to potentially support different LLM backends. An `LLMClient` (from `src/ii_agent/llm/base.py`) needs to be implemented for a new LLM API, and then this new client can be passed to the agent.

### Running and Testing

*   **`run_gaia.py` as an Example:** The `run_gaia.py` script provides a comprehensive example of how to initialize and run the `AnthropicFC` agent for a set of tasks.
*   **Smaller Test Scripts:** For testing new tools or specific features in isolation, it's highly recommended to create smaller, dedicated Python scripts.

### Environment Setup

*   **API Keys:** Configure via environment variables (e.g., `ANTHROPIC_API_KEY`). Refer to specific tool implementations or LLM client documentation for required variables.
*   **Python Version:** Ensure you are using a compatible Python version (Python 3.10+; `pyproject.toml` specifies ">=3.10", system prompts mention 3.10.12).
*   **Dependencies:** Project dependencies are managed using `pyproject.toml` and a `uv.lock` file. Use `uv pip install -r requirements.txt` (if generated) or `uv sync` in your virtual environment.

By following these guidelines, developers can effectively extend, customize, and test II Agent to suit new applications and research directions.
