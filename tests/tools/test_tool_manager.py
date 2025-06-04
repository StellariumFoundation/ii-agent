import os
import unittest
from unittest.mock import MagicMock, patch
import logging

from src.ii_agent.tools.tool_manager import AgentToolManager, get_system_tools # get_system_tools for potential context
from src.ii_agent.tools.base import LLMTool, ToolImplOutput # ToolImplOutput for run return, removed ToolCallParameters
from src.ii_agent.llm.base import ToolCall # Added ToolCall import
from src.ii_agent.llm.message_history import MessageHistory
from src.ii_agent.tools.complete_tool import CompleteTool, ReturnControlToUserTool

# Create a simple mock LLMTool for testing ToolManager
class MockLLMTool(LLMTool):
    name = "mock_tool"
    description = "A mock tool for testing."
    input_schema = {"type": "object", "properties": {"param": {"type": "string"}}}

    def __init__(self, name="mock_tool"):
        super().__init__()
        self.name = name # Allow dynamic naming for multiple mock tools
        self.run_impl_mock = MagicMock(return_value=ToolImplOutput("mock output", "mock user output"))
        # The base run method calls run_impl. We can mock run_impl or run.
        # For simplicity in testing what AgentToolManager calls, we'll mock `run`.
        self.run = MagicMock(return_value="mock_tool_result_direct_string") # run can return str or tuple

    def run_impl(self, tool_input: dict, message_history: MessageHistory | None = None) -> ToolImplOutput:
        return self.run_impl_mock(tool_input, message_history)

class TestAgentToolManager(unittest.TestCase):
    def setUp(self):
        self.mock_tool1 = MockLLMTool(name="tool1")
        self.mock_tool2 = MockLLMTool(name="tool2")
        self.mock_logger = MagicMock(spec=logging.Logger)

        self.tools_list = [self.mock_tool1, self.mock_tool2]
        self.manager = AgentToolManager(
            tools=self.tools_list,
            logger_for_agent_logs=self.mock_logger,
            interactive_mode=True # Uses ReturnControlToUserTool
        )

    def test_init_interactive_mode_true(self):
        self.assertEqual(self.manager.tools, self.tools_list)
        self.assertIsInstance(self.manager.complete_tool, ReturnControlToUserTool)
        self.assertEqual(self.manager.logger_for_agent_logs, self.mock_logger)

    def test_init_interactive_mode_false(self):
        manager_non_interactive = AgentToolManager(
            tools=self.tools_list,
            logger_for_agent_logs=self.mock_logger,
            interactive_mode=False # Uses CompleteTool
        )
        self.assertIsInstance(manager_non_interactive.complete_tool, CompleteTool)

    def test_get_tools(self):
        all_tools = self.manager.get_tools()
        self.assertEqual(len(all_tools), len(self.tools_list) + 1) # +1 for complete_tool
        self.assertIn(self.mock_tool1, all_tools)
        self.assertIn(self.mock_tool2, all_tools)
        self.assertIn(self.manager.complete_tool, all_tools)

    def test_get_tool_existing(self):
        self.assertIs(self.manager.get_tool("tool1"), self.mock_tool1)
        self.assertIs(self.manager.get_tool("tool2"), self.mock_tool2)
        # complete_tool (ReturnControlToUserTool) has name "return_control_to_user" by default
        self.assertIs(self.manager.get_tool(self.manager.complete_tool.name), self.manager.complete_tool)

    def test_get_tool_non_existing(self):
        with self.assertRaisesRegex(ValueError, "Tool with name non_existent_tool not found"):
            self.manager.get_tool("non_existent_tool")

    def test_run_tool_success_tool_returns_string(self):
        tool_params = ToolCall(tool_call_id="call1", tool_name="tool1", tool_input={"param": "value"}) # Changed to ToolCall
        mock_history = MagicMock(spec=MessageHistory)

        # mock_tool1.run is already a MagicMock from MockLLMTool setup
        self.mock_tool1.run.return_value = "Tool 1 direct string output"

        result = self.manager.run_tool(tool_params, mock_history)

        self.mock_tool1.run.assert_called_once_with(tool_params.tool_input, mock_history)
        self.assertEqual(result, "Tool 1 direct string output")
        self.mock_logger.info.assert_any_call("Running tool: tool1")
        self.mock_logger.info.assert_any_call(f"Tool input: {tool_params.tool_input}") # Accessing tool_input attribute
        self.mock_logger.info.assert_any_call(unittest.mock.ANY) # For the log with output

    def test_run_tool_success_tool_returns_tuple(self):
        tool_params = ToolCall(tool_call_id="call2", tool_name="tool2", tool_input={"param": "value2"}) # Changed to ToolCall
        mock_history = MagicMock(spec=MessageHistory)

        # Configure tool2 to return a tuple
        self.mock_tool2.run.return_value = ("Tool 2 output for LLM part", {"user_part": "some data"})

        result = self.manager.run_tool(tool_params, mock_history)

        self.mock_tool2.run.assert_called_once_with(tool_params.tool_input, mock_history)
        self.assertEqual(result, "Tool 2 output for LLM part") # run_tool extracts first part of tuple

    def test_run_tool_non_existent_tool(self):
        tool_params = ToolCall(tool_call_id="call_err", tool_name="unknown_tool", tool_input={}) # Changed to ToolCall
        mock_history = MagicMock(spec=MessageHistory)

        with self.assertRaisesRegex(ValueError, "Tool with name unknown_tool not found"):
            self.manager.run_tool(tool_params, mock_history)

    def test_should_stop(self):
        # Mock the complete_tool's should_stop property
        with patch.object(self.manager.complete_tool, 'should_stop', new_callable=unittest.mock.PropertyMock) as mock_should_stop_prop:
            mock_should_stop_prop.return_value = True
            self.assertTrue(self.manager.should_stop())

            mock_should_stop_prop.return_value = False
            self.assertFalse(self.manager.should_stop())

    def test_get_final_answer(self):
        expected_answer = "The task is done."
        with patch.object(self.manager.complete_tool, 'answer', new_callable=unittest.mock.PropertyMock) as mock_answer_prop:
            mock_answer_prop.return_value = expected_answer
            self.assertEqual(self.manager.get_final_answer(), expected_answer)

    def test_reset(self):
        # Mock the complete_tool's reset method
        self.manager.complete_tool.reset = MagicMock() # Attach mock to the instance
        self.manager.reset()
        self.manager.complete_tool.reset.assert_called_once()


# Limited tests for get_system_tools due to its complexity
# Focus on ensuring it returns a list and some default tools are present
class TestGetSystemTools(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True) # Ensure minimal env for predictability
    @patch('src.ii_agent.tools.tool_manager.create_bash_tool')
    @patch('src.ii_agent.tools.tool_manager.create_docker_bash_tool') # In case container_id is ever passed
    @patch('src.ii_agent.tools.tool_manager.Browser') # Mock Browser constructor
    def test_get_system_tools_basic_set(self, MockBrowser, mock_docker_bash, mock_bash):
        mock_llm_client = MagicMock(spec=LLMClient)
        mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        mock_workspace_manager.root = "/fake/ws"
        mock_message_queue = MagicMock(spec=asyncio.Queue)

        # Call with no tool_args to get the most default set
        tools = get_system_tools(
            client=mock_llm_client,
            workspace_manager=mock_workspace_manager,
            message_queue=mock_message_queue,
            tool_args=None # Test default set without optional tools
        )
        self.assertIsInstance(tools, list)
        self.assertTrue(len(tools) > 0) # Should have some default tools

        tool_names = [tool.name for tool in tools]
        self.assertIn("message_user", tool_names)
        self.assertIn("web_search", tool_names)
        self.assertIn("visit_webpage", tool_names)
        # Bash tool name depends on create_bash_tool mock's name attribute
        mock_bash.return_value.name = "bash" # Ensure the mock has a name

        # Re-call with the named mock
        tools = get_system_tools(
            client=mock_llm_client,
            workspace_manager=mock_workspace_manager,
            message_queue=mock_message_queue,
            tool_args=None
        )
        tool_names = [tool.name for tool in tools] # Re-evaluate names
        self.assertIn("bash", tool_names)


    @patch.dict(os.environ, {}, clear=True)
    @patch('src.ii_agent.tools.tool_manager.create_bash_tool')
    @patch('src.ii_agent.tools.tool_manager.Browser')
    def test_get_system_tools_with_tool_args(self, MockBrowser, mock_bash):
        mock_llm_client = MagicMock(spec=LLMClient)
        mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        mock_workspace_manager.root = "/fake/ws"
        mock_message_queue = MagicMock(spec=asyncio.Queue)

        tool_args_config = {
            "sequential_thinking": True,
            "deep_research": True,
            "memory_tool": "simple"
            # Not enabling tools that require more env vars for this test (e.g. media_generation)
        }
        tools = get_system_tools(
            client=mock_llm_client,
            workspace_manager=mock_workspace_manager,
            message_queue=mock_message_queue,
            tool_args=tool_args_config
        )
        tool_names = [tool.name for tool in tools]
        self.assertIn("sequential_thinking", tool_names)
        self.assertIn("deep_research", tool_names)
        self.assertIn("simple_memory", tool_names) # From SimpleMemoryTool

if __name__ == "__main__":
    unittest.main()
