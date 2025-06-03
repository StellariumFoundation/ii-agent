# GAIA Benchmark Setup & Execution

The GAIA (General AI Assistants) benchmark is a challenging suite of tasks designed to evaluate the capabilities of AI assistants on complex, real-world problems. II Agent uses the `run_gaia.py` script to specifically configure and execute evaluations against this dataset. This section details how the agent is set up and run for these evaluations.

## Purpose of `run_gaia.py`

The `run_gaia.py` script serves as the primary harness for:
*   Loading questions from the GAIA dataset.
*   Initializing and configuring the II Agent (specifically the `AnthropicFC` implementation) with a setup optimized for GAIA tasks.
*   Iterating through dataset questions, managing individual task environments.
*   Running the agent to obtain answers for each question.
*   Logging detailed results, including agent interactions, tool usage, and final predictions, for subsequent analysis and scoring.

## Agent Initialization for GAIA

Within `run_gaia.py`, the `AnthropicFC` agent is instantiated with a specific configuration tailored for the benchmark:

*   **LLM Client:** The script initializes an LLM client, typically configured for Anthropic's models (as `AnthropicFC` implies). This is done via `get_client("anthropic-direct", ...)`.
*   **System Prompts:** A crucial part of the GAIA setup is the use of a specialized system prompt. `GAIA_SYSTEM_PROMPT` (from `src/ii_agent/prompts/gaia_system_prompt.py`) is passed to the `AnthropicFC` agent. This prompt guides the LLM's behavior, encouraging it to use tools effectively and adhere to the problem-solving style required for GAIA tasks.
*   **Message History and Context Management:**
    *   A `TokenCounter` is initialized.
    *   An `LLMSummarizingContextManager` is set up with the LLM client and token counter. This manager is then used to initialize the `MessageHistory` object within the `AnthropicFC` agent, enabling intelligent context compression for potentially long GAIA tasks.
*   **Non-Interactive Mode:** The agent is run with `interactive_mode=False`, meaning it will continue processing each GAIA task until it reaches a conclusion (completion, error, or max turns) without requiring intermediate user feedback.

## Tool Configuration for GAIA

Unlike the dynamic tool loading via `get_system_tools` found in `AgentToolManager` for more general setups, `run_gaia.py` (specifically in its `answer_single_question` function) manually instantiates and provides a curated list of tools to the `AnthropicFC` agent. This selection is optimized for the types of tasks prevalent in the GAIA dataset:

*   **Core Reasoning & Interaction:**
    *   `SequentialThinkingTool`: For breaking down complex problems.
    *   `WebSearchTool`: For information retrieval.
    *   `VisitWebpageTool`: For fetching content from URLs.
    *   `StrReplaceEditorTool`: For file editing.
    *   `BashTool`: For shell command execution (file operations, running scripts).
    *   `TextInspectorTool`: For analyzing text content.
*   **Browser Interaction:** A full suite of browser tools (`BrowserNavigationTool`, `BrowserViewTool`, `BrowserClickTool`, `BrowserEnterTextTool`, etc.) is typically included, allowing the agent to interact with dynamic web pages.
*   **Multimedia & Specialized Tools:**
    *   `DisplayImageTool`: For handling images.
    *   `YoutubeVideoUnderstandingTool`, `AudioUnderstandingTool`, `AudioTranscribeTool`, `YoutubeTranscriptTool`: For tasks involving video or audio content.

This explicit tool configuration ensures that the agent is equipped with all necessary capabilities known to be useful for GAIA.

## Task Processing Loop

The `run_gaia.py` script implements a loop to process multiple questions from the dataset:

1.  **Dataset Loading:** It loads the specified GAIA dataset split (e.g., "validation", "test") using the Hugging Face `datasets` library, also handling the local download and caching of the dataset.
2.  **Task Filtering & Resumption:** The script can filter tasks (e.g., by UUID or index range) and can resume from previous runs by checking an output JSONL file for already answered questions.
3.  **Iteration:** For each selected GAIA question:
    *   The `answer_single_question` asynchronous function is called.
    *   This function sets up a dedicated environment for the task (see Workspace Management below).
    *   It augments the GAIA question with additional instructions emphasizing correctness and thoroughness.
    *   The agent's `run_agent` method is invoked with this augmented question and any associated files.
4.  **Concurrency:** The script supports concurrent task processing using `asyncio.Semaphore` to run multiple `answer_single_question` instances in parallel, speeding up evaluation.

## Workspace Management

For each GAIA task, `run_gaia.py` creates a dedicated workspace directory (e.g., `workspace/<task_id>`).

*   **Isolation:** This ensures that file operations performed by the agent for one task do not interfere with others.
*   **File Provisioning:** If a GAIA question includes associated files (e.g., documents, images), these are copied into an `uploads` subdirectory within the task's workspace. The agent is then provided with paths to these files within its workspace.
*   **`WorkspaceManager`:** An instance of `WorkspaceManager` is created for each task, configured with the path to its dedicated workspace. The agent uses this manager for all file system interactions, ensuring paths are correctly resolved within its isolated environment.

## Data Logging for Evaluation

Comprehensive logging is essential for evaluating the agent's performance:

*   **Agent Logs:** General agent activities, LLM interactions, and errors are logged to a file specified by command-line arguments.
*   **Output JSONL File:** The primary output for evaluation is a JSONL file where each line corresponds to a processed GAIA task. This entry includes:
    *   The original question and task details.
    *   The agent's final predicted answer (`prediction`).
    *   Information on whether iteration limits were exceeded or errors occurred.
    *   Start and end times for processing.
    *   The `task_id` (which also serves as the `workspace_id`).
*   **Database Logging:** `run_gaia.py` also initializes a `DatabaseManager`. If a `session_id` (derived from `task_id`) is used when creating the agent, all `RealtimeEvent`s (tool calls, tool results, agent thoughts, etc.) for that task are saved to a database, providing an extremely granular trace for debugging and detailed analysis.

## Customization for Developers

Developers can adapt `run_gaia.py` as a template for their own custom evaluations or for testing different agent configurations:

*   **Different Datasets:** Modify the `load_gaia_dataset` function to load custom datasets.
*   **Agent Variants:** Instantiate different agent classes or `AnthropicFC` with different parameters (e.g., different system prompts, models, `max_turns`).
*   **Toolsets:** Change the manually curated list of tools in `answer_single_question` to test the impact of adding/removing specific capabilities.
*   **Context Managers:** Experiment with different `ContextManager` strategies or configurations.

By understanding the structure of `run_gaia.py`, developers can gain insights into end-to-end agent operation and systematically evaluate the impact of architectural or configuration changes.
