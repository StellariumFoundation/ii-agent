# Developer Guide: Extending and Customizing II Agent

This guide provides practical instructions for developers looking to extend II Agent's capabilities, modify its behavior, or set up a development environment.

## Adding New Tools

Tools are the primary way to expand what II Agent can do. Here's how to create and integrate a new tool:

1.  **Create a New Tool Class:**
    *   Create a new Python file (e.g., `my_custom_tool.py`) typically within a relevant subdirectory of `src/ii_agent/tools/`.
    *   Define a new class that inherits from `LLMTool` (from `src/ii_agent/tools/base.py`).

    ```python
    from ii_agent.tools.base import LLMTool, ToolImplOutput
    from ii_agent.llm.message_history import MessageHistory # Optional
    from typing import Any, Optional

    class MyCustomTool(LLMTool):
        # ... implementation ...
    ```

2.  **Define `name`, `description`, and `input_schema`:**
    *   **`name` (str):** A unique, descriptive, snake_case name for your tool. This is how the LLM will refer to it.
    *   **`description` (str):** A detailed explanation of what the tool does, its purpose, when it should be used, and what kind of output it produces. This is **critical** for the LLM to understand and use your tool correctly.
    *   **`input_schema` (dict):** A JSON schema defining the expected input parameters, their types, and whether they are required.

    ```python
    class MyCustomTool(LLMTool):
        name = "my_custom_tool"
        description = "This tool performs a specific custom action. It is useful when you need to [describe specific scenario]. It expects [input details] and returns [output details]."
        input_schema = {
            "type": "object",
            "properties": {
                "required_param": {"type": "string", "description": "An example required parameter."},
                "optional_param": {"type": "integer", "description": "An optional parameter."}
            },
            "required": ["required_param"],
        }
    ```

3.  **Implement the `run_impl` Method:**
    *   This method contains the core logic of your tool. It takes `tool_input` (a dictionary validated against your `input_schema`) and an optional `message_history`.
    *   It should return a `ToolImplOutput` object, which includes:
        *   `tool_output` (str or list[dict]): The primary result to be sent back to the LLM.
        *   `tool_result_message` (str): A human-readable summary of what the tool did, for logging.
        *   `auxiliary_data` (dict, optional): Any additional data for logging.

    ```python
    def run_impl(
        self,
        tool_input: dict[str, Any],
        message_history: Optional[MessageHistory] = None, # If your tool needs conversation context
    ) -> ToolImplOutput:
        required_param = tool_input["required_param"]
        optional_param = tool_input.get("optional_param")

        # --- Your tool's logic here ---
        result_data = f"Processed {required_param} and {optional_param}"
        # --- End of tool's logic ---

        return ToolImplOutput(
            tool_output=result_data,
            tool_result_message=f"MyCustomTool successfully processed: {required_param}",
            auxiliary_data={"custom_log_info": "some_value"}
        )
    ```

4.  **Register the New Tool:**
    *   To make the tool available to the agent, it needs to be added to the list of tools that `AgentToolManager` manages.
    *   The primary way to do this is by modifying the `get_system_tools` function in `src/ii_agent/tools/tool_manager.py`.
    *   Import your new tool class and add an instance of it to the `tools` list, often within a conditional block if its availability depends on configuration (`tool_args`) or environment variables.

    ```python
    # In src/ii_agent/tools/tool_manager.py
    # ... other imports
    from .my_custom_tool import MyCustomTool # Example import

    def get_system_tools(...) -> list[LLMTool]:
        # ... existing tool instantiations
        tools = [
            # ...
        ]

        # Add your custom tool
        if tool_args and tool_args.get("enable_my_custom_tool", False): # Or other condition
            tools.append(MyCustomTool())

        return tools
    ```
    *   Alternatively, if you are instantiating an agent directly (like in `run_gaia.py`), you can add your tool instance to the list of tools passed to the agent's constructor.

## Modifying System Prompts

System prompts are fundamental to shaping the LLM's behavior.

*   **Location:**
    *   General system prompts: `src/ii_agent/prompts/system_prompt.py` (contains `SYSTEM_PROMPT` and `SYSTEM_PROMPT_WITH_SEQ_THINKING`).
    *   GAIA-specific prompt: `src/ii_agent/prompts/gaia_system_prompt.py`.
*   **Effective Prompt Engineering:**
    *   **Clarity and Specificity:** Clearly define the agent's role, desired response style, constraints, and how it should approach tasks.
    *   **Tool Usage Guidance:** Explicitly encourage or guide tool usage. You might list preferred tools for certain scenarios or general rules for when to seek external information or action.
    *   **Iterative Refinement:** Prompt engineering is often an iterative process. Test changes and observe their impact on agent behavior.
*   **Caution:** Small changes to system prompts can significantly alter agent performance and reliability. Thoroughly test any modifications.

## Changing Context Management Strategy

The agent's memory handling can be adjusted:

*   **Switching Implementations:** If you create a new `ContextManager` subclass, you would change it where the context manager is instantiated (e.g., in `run_gaia.py` or your custom agent setup script) and pass it to the `MessageHistory` constructor.
*   **Adjusting `LLMSummarizingContextManager`:**
    *   Parameters like `token_budget`, `max_size` (max number of turns before summarization), and `keep_first` (initial turns to always keep) can be modified when `LLMSummarizingContextManager` is instantiated. This will affect how frequently summarization occurs and how much history is retained verbatim.

## Customizing Agent Behavior

*   **Modifying `AnthropicFC`:** For deep customizations to the agent's core loop or decision-making logic, you might consider modifying `src/ii_agent/agents/anthropic_fc.py`. However, this is complex and should be done with a thorough understanding of the existing architecture to avoid unintended consequences.
*   **LLM Clients:** The system is designed to potentially support different LLM backends. An `LLMClient` (from `src/ii_agent/llm/base.py`) needs to be implemented for a new LLM API, and then this new client can be passed to the agent (e.g., `AnthropicFC`).

## Running and Testing

*   **`run_gaia.py` as an Example:** The `run_gaia.py` script provides a comprehensive example of how to initialize and run the `AnthropicFC` agent for a set of tasks. It demonstrates workspace management, tool configuration for a specific benchmark, and results in logging. You can adapt it for custom evaluations.
*   **Smaller Test Scripts:** For testing new tools or specific features in isolation, it's highly recommended to create smaller, dedicated Python scripts. These scripts can instantiate the agent (or just the tool and `AgentToolManager`) with minimal setup, allowing for faster iteration and debugging.

    ```python
    # Example minimal script for testing a tool
    # (This is conceptual and needs adaptation to your project structure)
    # from ii_agent.tools.my_custom_tool import MyCustomTool
    # from ii_agent.tools.tool_manager import AgentToolManager
    # import logging

    # if __name__ == "__main__":
    #     logger = logging.getLogger("test_tool")
    #     # Dummy tool manager setup
    #     my_tool = MyCustomTool()
    #     tool_manager = AgentToolManager(tools=[my_tool], logger_for_agent_logs=logger, interactive_mode=False)

    #     # Simulate tool call parameters that the LLM would generate
    #     mock_tool_params = {
    #         "tool_name": "my_custom_tool",
    #         "tool_input": {"required_param": "test_value"}
    #     }

    #     # Directly test the tool via a simplified path if needed, or its run method
    #     # result = my_tool.run(mock_tool_params["tool_input"])
    #     # print(f"Tool output: {result}")

    #     # Or test through the tool manager (more integrated)
    #     # from ii_agent.llm.message_history import ToolCallParameters # Assuming this structure
    #     # tool_call_params_obj = ToolCallParameters(**mock_tool_params)
    #     # result = tool_manager.run_tool(tool_call_params_obj, history=None) # May need a mock history
    #     # print(f"Tool output via manager: {result}")
    ```

## Environment Setup

*   **API Keys:** Many LLMs and external services (like search APIs used by tools) require API keys. These are typically configured via environment variables (e.g., `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`). Refer to specific tool implementations or LLM client documentation for required variables.
*   **Python Version:** Ensure you are using a compatible Python version as specified by the project (often found in `pyproject.toml` or CI configurations). The project uses Python 3.10.12 as seen in system prompts.
*   **Dependencies:** Project dependencies are managed using `pyproject.toml` and a `uv.lock` file (indicating usage of `uv` as a package manager/resolver, similar to Poetry or PDM). Use `uv pip install -r requirements.txt` (if a requirements file is generated) or `uv sync` (if using `uv` directly with `pyproject.toml`) to install dependencies in your virtual environment.

By following these guidelines, developers can effectively extend, customize, and test II Agent to suit new applications and research directions.
