# II Agent: Architectural Deep Dive & Developer Guide

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
    *   **Details:** Built around the `LLMTool` base class, with concrete tool implementations (e.g., `WebSearchTool`, `BashTool`, `SequentialThinkingTool`). The `AgentToolManager` is responsible for discovering, managing, and safely executing these tools based on requests from the Main Agent Orchestrator. This is detailed in the "Action & Tool Subsystem" section.

### Component Interaction Flow

The interaction between these components follows a general pattern:

1.  **Input:** The **Main Agent Orchestrator** receives an initial instruction or query from the user. This input is added to the **Memory Subsystem** (`MessageHistory`).
2.  **Context Preparation:** The Orchestrator, before querying the LLM, ensures the current `MessageHistory` is within token limits by calling the `truncate()` method of the `ContextManager` within the **Memory Subsystem**.
3.  **LLM Consultation & Decision Making:** The Orchestrator sends the prepared history (including the current query, past interactions, and system prompt) to the **LLM Client**. The LLM processes this context and returns a response, which might be a direct textual answer, a request to call tools, or a combination.
4.  **Action Execution (Tool Use):** If the LLM requests a tool call, the **Main Agent Orchestrator** directs the **Tool Subsystem** (`AgentToolManager`) to execute the tool. The tool performs its action, and its result is returned to the Orchestrator.
5.  **Memory Update & Iteration:** The Orchestrator adds the LLM's response and any tool results to the **Memory Subsystem**. If the task isn't complete, the loop repeats from step 2, allowing the agent to iterate and build upon prior actions.
6.  **Output & Task Completion:** When the task is complete (either by the LLM's indication or a tool's signal), the Orchestrator finalizes the process and provides the final response.
7.  **Eventing (Throughout):** Various components can generate `RealtimeEvent` objects (e.g., for tool calls, results, agent thoughts) which are typically put on a message queue for logging, database persistence, or UI updates.

This cyclical process allows II Agent to handle complex, multi-step tasks by building context and iteratively refining its approach.

## 3. Memory Management in II Agent

Effective memory management is crucial for enabling II Agent to handle long, complex conversations and multi-step tasks while staying within the token limits of LLMs.

### `MessageHistory`: Tracking the Conversation

*   **Role:** Records the chronological sequence of all interactions: user inputs (text and images), agent's textual responses, tool calls, and tool results.
*   **Structure:** Stores history as a list of "turns," each turn being a list of `GeneralContentBlock` objects (e.g., `TextPrompt`, `TextResult`, `ToolCall`, `ToolFormattedResult`, `ImageBlock`), allowing differentiation of information types.
*   **Integrity:** Includes mechanisms like `_ensure_tool_call_integrity` to clean up orphaned tool calls or results.
*   **Interface:** Provides methods for adding turns, retrieving pending tool calls, adding tool results, and formatting messages for the LLM.

### `ContextManager`: Abstracting Compression Strategies

This abstract base class defines the interface for context management.

*   **Responsibility:** Ensures the conversation history provided to the LLM does not exceed its token budget.
*   **Token Counting:** Implements `count_tokens` with logic aware of different content block types (e.g., estimating costs for images, only counting thinking blocks in the last turn).
*   **Truncation Logic:** Defines `should_truncate()` (to check if budget is exceeded) and `apply_truncation()` (an abstract method for specific condensation strategies). `apply_truncation_if_needed()` is the public method that invokes the strategy.

### `LLMSummarizingContextManager`: Intelligent Context Compression

This implementation of `ContextManager` uses an LLM to summarize older parts of the conversation.

*   **Mechanism:**
    1.  **Triggering:** Summarization occurs if the token count exceeds `token_budget` OR if the number of message turns exceeds `max_size`.
    2.  **Segmentation:** Divides history into `head` (initial messages, always kept, defined by `keep_first`), `tail` (most recent messages), and `forgotten_events` (messages between head and tail, targeted for summarization).
    3.  **Summarization Prompt:** A detailed prompt instructs a summarizer LLM to extract key information (user context, completed/pending tasks, current state, coding-specific details) from `forgotten_events`, considering any `<PREVIOUS SUMMARY>`.
    4.  **History Reconstruction:** Replaces `forgotten_events` with a single `TextPrompt` containing the new summary ("Conversation Summary: ..."). The history becomes `head` + `summary` + `tail`.
*   **Benefits:** Retains vital information from earlier parts of long conversations in a compressed format.
*   **Configuration:** Key parameters: `token_budget`, `max_size` (max turns), `keep_first`.

### Memory-Related Tools

*   **`CompactifyMemoryTool`:** Allows the agent to proactively trigger memory compaction using the configured `ContextManager`. The LLM might call this if it anticipates needing more context space.
*   **`SimpleMemoryTool`:** Provides a persistent, string-based key-value scratchpad for temporary notes, reminders, or intermediate calculations, separate from the main `MessageHistory`.

### Importance for Agent Performance

This memory system allows II Agent to:
*   Maintain long-term coherence by not losing critical early information.
*   Stay within LLM token limits, preventing errors.
*   Make informed decisions based on a rich (though partially summarized) history.

## 4. Action & Tool Subsystem

II Agent's ability to perform actions and interact with environments is powered by its Action & Tool Subsystem.

### `LLMTool`: The Foundation for Agent Capabilities

This abstract base class defines a standardized interface for all tools.

*   **`name` (str):** Unique identifier for the tool.
*   **`description` (str):** Detailed explanation of the tool's function, usage context, inputs, and outputs. **Crucial for LLM's tool selection.**
*   **`input_schema` (dict):** JSON schema for expected input parameters, aiding LLM input formulation and validation.
*   **`run_impl(...) -> ToolImplOutput` (abstract method):** Core logic of the tool, returning `ToolImplOutput` (containing output for LLM and logging data).

Clarity of `description` and `input_schema` is vital for effective tool use by the LLM.

### `AgentToolManager`: Managing and Executing Tools

*   **Role:**
    *   **Discovery and Loading:** Manages available `LLMTool` instances. The `get_system_tools()` function assembles tools, potentially based on configuration (`tool_args`) and environment settings (conditional loading).
    *   **Provision to Agent:** Provides the agent orchestrator with available tool parameters for the LLM.
    *   **Execution:** Finds and invokes tools by name based on LLM requests, handling input validation and logging.

### Tool Execution Flow

1.  **LLM Decision:** Agent orchestrator queries LLM with `MessageHistory` and available tools.
2.  **Tool Call Request:** LLM response may include a request specifying `tool_name` and `tool_input`.
3.  **Delegation:** Agent orchestrator passes request to `AgentToolManager`.
4.  **Invocation:** `AgentToolManager` finds the tool, validates input, and calls its `run_impl()` method.
5.  **Result Processing:** Tool returns `ToolImplOutput`.
6.  **Memory Update:** Agent orchestrator adds tool output to `MessageHistory` as `ToolFormattedResult`.
7.  **Iteration:** Updated `MessageHistory` is used for the next LLM consultation.

### Showcase of Key Tools

*   **`SequentialThinkingTool`:** Guides the LLM through structured, iterative problem decomposition, planning, and revision. Essential for complex reasoning.
*   **Browser Tools (e.g., `BrowserNavigationTool`, `BrowserViewTool`, `BrowserClickTool`):** Enable interaction with live websites (navigation, content viewing, form interaction).
*   **`WebSearchTool`:** Performs web searches to find information.
*   **`BashTool` (and `DockerBashTool`):** Executes shell commands in a controlled environment for file operations, script running, etc.
*   **`StrReplaceEditorTool`:** Allows precise, targeted modifications to files.

### Extensibility

New tools can be created by subclassing `LLMTool` and implementing its methods. They are then registered via `get_system_tools` or by directly passing them to the agent constructor.

## 5. Agent Logic: Orchestration with `AnthropicFC`

The `AnthropicFC` class is the primary orchestrator for II Agent, especially when using Anthropic's models with function calling.

### Initialization

`AnthropicFC` is initialized with:
*   `system_prompt` (str): Foundational instructions for the LLM.
*   `client` (LLMClient): For communication with the LLM.
*   `tools` (List[LLMTool]): Passed to an internal `AgentToolManager`.
*   `workspace_manager` (WorkspaceManager): For file operations.
*   `message_queue` (asyncio.Queue): For emitting `RealtimeEvent` objects.
*   `logger_for_agent_logs` (logging.Logger).
*   `context_manager` (ContextManager): Used to initialize `MessageHistory`.
*   `max_output_tokens_per_turn`, `max_turns`, `session_id`, `interactive_mode`.

### The Main Run Loop (`run_impl` method)

This method implements the agent's iterative reasoning and action cycle:

1.  **Input Processing:** User `instruction` (and any `files`) are added to `MessageHistory`. Image files become `ImageBlock` objects.
2.  **Iterative Turns (Loop up to `max_turns`):**
    *   **A. Context Truncation:** `self.history.truncate()` is called to ensure the history fits the LLM's token budget, using the configured `ContextManager`.
    *   **B. LLM Consultation:** The agent sends the (potentially truncated) `MessageHistory`, available tool parameters, and `system_prompt` to the LLM via `self.client.generate()`.
    *   **C. Processing LLM's Response:** The LLM's response (text and/or tool call requests) is added to `MessageHistory`.
    *   **D. Action & Decision Making:**
        *   **No Tool Calls:** If no tools are called, the task is considered complete. The last textual response is returned.
        *   **Tool Call Execution:** If a tool is requested:
            1.  A `TOOL_CALL` event is emitted.
            2.  `self.tool_manager.run_tool()` executes the tool.
            3.  The `tool_result` is added to `MessageHistory`, and a `TOOL_RESULT` event is emitted.
        *   **Stopping Conditions:** The loop ends if no tool is called, a tool signals completion (via `self.tool_manager.should_stop()`), `max_turns` is reached, or an interruption occurs.

### Event Emission for Observability

`AnthropicFC` uses its `message_queue` to emit `RealtimeEvent` objects (e.g., `TOOL_CALL`, `TOOL_RESULT`, `AGENT_RESPONSE`). An asynchronous `_process_messages` task handles:
*   Saving events to a database (if `session_id` is present).
*   Forwarding events to a WebSocket client for potential UI updates.

### Role of System Prompts

The `system_prompt` (general or specialized like `GAIA_SYSTEM_PROMPT`) is critical:
*   It guides the LLM's persona, behavior, and task approach.
*   It often encourages or provides rules for tool usage.
*   It can influence response formatting and constraint adherence.
It's included in every LLM call, consistently shaping the agent's decisions.

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

## 7. Developer Guide: Extending and Customizing II Agent

This guide provides practical instructions for developers.

### Adding New Tools

1.  **Create Tool Class:** Inherit from `LLMTool` (in `src/ii_agent/tools/base.py`).
2.  **Define Attributes:** Set `name` (str, snake_case), `description` (str, detailed for LLM), and `input_schema` (dict, JSON schema for parameters).
3.  **Implement `run_impl`:** Contains the tool's core logic. Takes `tool_input` (dict) and optional `message_history`. Returns `ToolImplOutput` (with `tool_output` for LLM and `tool_result_message` for logging).
4.  **Register Tool:** Modify `get_system_tools` in `src/ii_agent/tools/tool_manager.py` to include an instance of your new tool, often conditionally based on `tool_args`. Or, pass it directly to the agent constructor if instantiating manually.

### Modifying System Prompts

*   **Location:** `src/ii_agent/prompts/system_prompt.py` (general), `src/ii_agent/prompts/gaia_system_prompt.py` (GAIA-specific).
*   **Prompt Engineering Tips:** Be clear and specific. Guide tool usage. Iterate and test.
*   **Caution:** Changes can significantly impact performance; test thoroughly.

### Changing Context Management Strategy

*   **Switching Implementations:** If a new `ContextManager` subclass is created, update its instantiation (e.g., in `run_gaia.py`) and pass it to `MessageHistory`.
*   **Adjusting `LLMSummarizingContextManager`:** Modify parameters like `token_budget`, `max_size`, `keep_first` during its instantiation.

### Customizing Agent Behavior

*   **Modifying `AnthropicFC`:** Advanced changes to the core loop in `src/ii_agent/agents/anthropic_fc.py` are possible but require care.
*   **LLM Clients:** Implement a new `LLMClient` (from `src/ii_agent/llm/base.py`) for different LLM backends and pass it to the agent.

### Running and Testing

*   **`run_gaia.py`:** A comprehensive example for running tasks and evaluations.
*   **Smaller Test Scripts:** Recommended for isolating and testing new tools or features quickly. Create minimal scripts to instantiate the component you're testing.

### Environment Setup

*   **API Keys:** Configure via environment variables (e.g., `ANTHROPIC_API_KEY`).
*   **Python Version:** Project uses Python 3.10.12 (as per system prompts). Check `pyproject.toml`.
*   **Dependencies:** Managed by `pyproject.toml` and `uv.lock`. Use `uv sync` or `uv pip install -r requirements.txt` (if available) in your virtual environment.

By following these guidelines, developers can effectively extend, customize, and test II Agent.
