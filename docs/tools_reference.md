# Tools Reference

The II-Agent comes with a variety of built-in tools. Some are enabled by default, while others can be activated or configured via `tool_args` during agent initialization (e.g., through CLI arguments or WebSocket messages).

## General Tool Configuration

Tool arguments (`tool_args`) are typically passed as a JSON object. For example, to enable a specific tool you might pass `{"tool_name": true}`. Refer to the main agent configuration documentation for how `tool_args` are supplied.

## Core Tools (Often Enabled by Default or Core Functionality)

*   **`BashTool`**:
    *   **Purpose**: Allows the agent to execute shell commands within a bash environment.
    *   **Activation**: Typically enabled by default.
    *   **`tool_args`**: None usually required for basic activation.

*   **`StrReplaceEditorTool`** (formerly referred to as CodeEditorTool in planning):
    *   **Purpose**: Enables the agent to write, read, and make targeted modifications to files within its workspace.
    *   **Activation**: Typically enabled by default.
    *   **`tool_args`**: None usually required.

*   **`CompleteTool` / `ReturnControlToUserTool`**:
    *   **Purpose**: Allows the agent to signal task completion or return control to the user in interactive mode.
    *   **Activation**: Core functionality, always available (variant depends on interactive mode).
    *   **`tool_args`**: None.

*   **`MessageTool`**:
    *   **Purpose**: Allows the agent to send a message to the user (often used for clarification or updates).
    *   **Activation**: Core functionality, always available.
    *   **`tool_args`**: None.

## Optional & Configurable Tools

This section lists tools that might require specific `tool_args` to enable or configure. The exact flags for `tool_args` are typically found in how `get_system_tools` in `src/ii_agent/tools/tool_manager.py` is called by `cli.py` or `ws_server.py`.

*   **`SequentialThinkingTool`**:
    *   **Purpose**: Guides the agent to think step-by-step before performing an action, useful for complex tasks.
    *   **Activation**: Can be enabled via `tool_args`.
    *   **`tool_args` Example**: `{"sequential_thinking": true}` (as seen in `ws_server.py`)

*   **Memory Tools (`CompactifyMemoryTool`, `SimpleMemoryTool`)**:
    *   **Purpose**:
        *   `CompactifyMemoryTool`: Allows the agent to proactively trigger memory summarization.
        *   `SimpleMemoryTool`: Provides a key-value scratchpad for the agent.
    *   **Activation**: Can be enabled via `tool_args` (using the `--memory-tool` CLI arg which translates to a `tool_args` value).
    *   **`tool_args` Example**: `{"memory_tool": "compactify-memory"}` or `{"memory_tool": "simple"}` (derived from `cli.py` logic for `--memory-tool`)

*   **`WebSearchTool`**:
    *   **Purpose**: Enables the agent to search the web. Requires API keys for search providers.
    *   **Activation**: Enabled if relevant API keys (e.g., `TAVILY_API_KEY`, `SERPAPI_API_KEY`, `JINA_API_KEY`) are provided in the environment.
    *   **`tool_args`**: No specific `tool_args` for basic activation, relies on env vars.

*   **`VisitWebpageTool`**:
    *   **Purpose**: Allows the agent to fetch and parse content from web pages.
    *   **Activation**: Typically available. May use `FIRECRAWL_API_KEY` (if provided) for enhanced crawling capabilities.
    *   **`tool_args`**: None for basic use.

*   **Browser Tools Suite (e.g., `BrowserNavigationTool`, `BrowserClickTool`, etc.)**:
    *   **Purpose**: Provides comprehensive web browser interaction capabilities.
    *   **Activation**: Can be enabled via `tool_args`.
    *   **`tool_args` Example**: `{"browser": true}` (as seen in `cli.py`)

*   **`ImageSearchTool`**:
    *   **Purpose**: Enables the agent to search for images. Requires `SERPAPI_API_KEY`.
    *   **Activation**: Enabled if `SERPAPI_API_KEY` is provided in the environment.
    *   **`tool_args`**: None for basic use, relies on env var.

*   **`DeepResearchTool`**:
    *   **Purpose**: Performs in-depth research on a topic by combining search and page visiting.
    *   **Activation**: Can be enabled via `tool_args`.
    *   **`tool_args` Example**: `{"deep_research": true}` (as seen in `cli.py` default, though set to `False`)

*   **`PdfTextExtractTool`**:
    *   **Purpose**: Extracts text content from PDF files.
    *   **Activation**: Can be enabled via `tool_args`.
    *   **`tool_args` Example**: `{"pdf": true}` (as seen in `cli.py`)

*   **Media Generation Tools (e.g., `ImageGenerateTool`, `VideoGenerateFromTextTool`, `AudioGenerateTool`, `AudioTranscribeTool`)**:
    *   **Purpose**: Tools for generating and transcribing media content.
    *   **Activation**: Can be enabled via `tool_args` and typically require specific API keys/environment setup (e.g., Google Cloud for some image/video, Azure OpenAI for some audio).
    *   **`tool_args` Examples**:
        *   `{"media_generation": true}` (general flag, as seen in `cli.py`)
        *   `{"video_generation": true}` (often conditional on `media_generation`, as seen in `tool_manager.py`)
        *   `{"audio_generation": true}` (as seen in `cli.py`)

---
*Note: This list is not exhaustive and primarily covers commonly used or explicitly configurable tools. Some tools are enabled based on environment variable presence (like API keys). The exact structure of `tool_args` and how they are passed can be further investigated in `cli.py` (for command-line usage) and `ws_server.py` (for WebSocket agent initialization). Please refer to the agent's source code, particularly `src/ii_agent/tools/tool_manager.py` in the `get_system_tools` function, for the most up-to-date list of tools and their conditional activation logic.*
