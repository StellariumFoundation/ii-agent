# Core Architecture Overview

II Agent is built upon a modular architecture designed to separate concerns and enable sophisticated, multi-turn, tool-assisted reasoning. At a high level, the system comprises several key components that work in concert to process information, make decisions, and execute tasks.

The primary components are:

1.  **Main Agent Orchestrator (`AnthropicFC` class):**
    *   **Role:** This is the central "brain" of the agent. It manages the overall lifecycle of a task, from receiving user input to generating a final response. It orchestrates the flow of information and control between all other components.
    *   **Details:** Implemented in classes like `AnthropicFC` (for Anthropic models with function calling), it contains the main operational loop.

2.  **Language Model (LLM) Client (`LLMClient` implementations):**
    *   **Role:** This component is responsible for all direct communication with the underlying large language model (e.g., Anthropic's Claude). It handles prompt formatting, sending requests to the LLM API, and receiving the LLM's responses (which may include text generation and tool call requests).
    *   **Details:** Abstracted via `LLMClient` (e.g., `ii_agent.llm.anthropic.AnthropicLLMClient`), allowing for different LLM backends.

3.  **Memory Subsystem (`MessageHistory` & `ContextManager`):**
    *   **Role:** This subsystem is responsible for maintaining the agent's understanding of the current task and conversation. It stores the history of interactions (user prompts, agent replies, tool usage) and employs strategies to manage this history within the LLM's context window limitations.
    *   **Details:** Primarily consists of the `MessageHistory` class, which holds the sequence of events, and `ContextManager` implementations (like `LLMSummarizingContextManager`) that handle context compression and truncation.

4.  **Tool Subsystem (`LLMTool`, `AgentToolManager`):**
    *   **Role:** This provides the agent with its capabilities to interact with its environment and perform actions beyond simple text generation. Tools can range from file system operations and web browsing to code execution and complex reasoning aids.
    *   **Details:** Built around the `LLMTool` base class, with concrete tool implementations (e.g., `WebSearchTool`, `BashTool`, `SequentialThinkingTool`). The `AgentToolManager` is responsible for discovering, managing, and safely executing these tools based on requests from the Main Agent Orchestrator (which are in turn based on LLM outputs).

## Component Interaction Flow

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
