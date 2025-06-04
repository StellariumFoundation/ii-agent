import unittest
from unittest.mock import patch, MagicMock, AsyncMock # AsyncMock for LLM client
import asyncio

from src.ii_agent.tools.presentation_tool import PresentationTool
from src.ii_agent.tools.base import ToolImplOutput # Removed ToolCallParameters
from src.ii_agent.llm.message_history import MessageHistory
from src.ii_agent.llm.base import TextPrompt, AssistantContentBlock, ToolCall, TextResult # For constructing mock LLM responses
from src.ii_agent.utils import WorkspaceManager
from src.ii_agent.tools.bash_tool import BashTool
from src.ii_agent.tools.str_replace_tool_relative import StrReplaceEditorTool
from src.ii_agent.tools.advanced_tools.image_search_tool import ImageSearchTool
from src.ii_agent.llm.context_manager.base import ContextManager


class TestPresentationTool(unittest.TestCase):
    def setUp(self):
        self.mock_llm_client = MagicMock()
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_workspace_manager.root = "/fake/workspace" # Ensure root is a string or Path-like
        self.mock_message_queue = MagicMock(spec=asyncio.Queue)
        self.mock_context_manager = MagicMock(spec=ContextManager)

        # Mock tools that PresentationTool initializes
        self.mock_bash_tool_instance = MagicMock(spec=BashTool)
        self.mock_str_replace_tool_instance = MagicMock(spec=StrReplaceEditorTool)
        self.mock_image_search_tool_instance = MagicMock(spec=ImageSearchTool)

        # Patch the constructors or factory functions of these tools
        self.patch_create_bash_tool = patch('src.ii_agent.tools.presentation_tool.create_bash_tool', return_value=self.mock_bash_tool_instance)
        self.patch_str_replace_editor_tool = patch('src.ii_agent.tools.presentation_tool.StrReplaceEditorTool', return_value=self.mock_str_replace_tool_instance)
        self.patch_image_search_tool = patch('src.ii_agent.tools.presentation_tool.ImageSearchTool', return_value=self.mock_image_search_tool_instance)

        self.mock_create_bash_tool = self.patch_create_bash_tool.start()
        self.mock_str_replace_editor_tool_constructor = self.patch_str_replace_editor_tool.start()
        self.mock_image_search_tool_constructor = self.patch_image_search_tool.start()

        # Assume ImageSearchTool is available for consistent tool list
        self.mock_image_search_tool_instance.is_available.return_value = True

        self.tool = PresentationTool(
            client=self.mock_llm_client,
            workspace_manager=self.mock_workspace_manager,
            message_queue=self.mock_message_queue,
            context_manager=self.mock_context_manager,
            ask_user_permission=False
        )

    def tearDown(self):
        self.patch_create_bash_tool.stop()
        self.patch_str_replace_editor_tool.stop()
        self.patch_image_search_tool.stop()

    def test_init_action_success(self):
        # Mock bash tool successes
        self.mock_bash_tool_instance.run_impl.side_effect = [
            ToolImplOutput("cloned", "cloned", auxiliary_data={"success": True}), # Git clone
            ToolImplOutput("installed", "installed", auxiliary_data={"success": True}) # npm install
        ]
        # Mock LLM response for the loop part after init (e.g., no tool calls, just text response)
        self.mock_llm_client.generate.return_value = ([TextResult(text="Init setup seems complete.")], {})


        tool_input = {"action": "init", "description": "Initialize presentation for project X"}
        result = self.tool.run_impl(tool_input)

        self.mock_bash_tool_instance.run_impl.assert_any_call(
            {"command": f"git clone https://github.com/khoangothe/reveal.js.git {self.mock_workspace_manager.root}/presentation/reveal.js"}
        )
        self.mock_bash_tool_instance.run_impl.assert_any_call(
            {"command": f"cd {self.mock_workspace_manager.root}/presentation/reveal.js && npm install && cd {self.mock_workspace_manager.root}"}
        )
        self.assertTrue(result.auxiliary_data["success"])
        self.assertEqual(result.tool_output, "Init setup seems complete.")

    def test_init_action_git_clone_fails(self):
        self.mock_bash_tool_instance.run_impl.return_value = ToolImplOutput(
            "clone failed", "clone failed", auxiliary_data={"success": False}
        ) # Git clone fails

        tool_input = {"action": "init", "description": "Init"}
        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Failed to clone reveal.js repository", result.tool_output)

    def test_init_action_npm_install_fails(self):
        self.mock_bash_tool_instance.run_impl.side_effect = [
            ToolImplOutput("cloned", "cloned", auxiliary_data={"success": True}), # Git clone success
            ToolImplOutput("npm failed", "npm failed", auxiliary_data={"success": False}) # npm install fails
        ]
        tool_input = {"action": "init", "description": "Init"}
        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Failed to install dependencies", result.tool_output)

    def test_non_init_action_single_llm_turn_no_tool_call(self):
        # Test 'create' action, simulating LLM returns text without calling sub-tools
        final_text_response = "Slide created based on your description."
        self.mock_llm_client.generate.return_value = ([TextResult(text=final_text_response)], {})

        tool_input = {"action": "create", "description": "Create an intro slide"}
        result = self.tool.run_impl(tool_input)

        self.assertTrue(result.auxiliary_data["success"])
        self.assertEqual(result.tool_output, final_text_response)
        # Check that history was updated
        # self.tool.history is reset in init, so for non-init, it uses the instance's history
        self.assertEqual(self.tool.history.get_messages_for_llm()[-1].content[0].text, final_text_response)


    def test_non_init_action_llm_calls_sub_tool_then_completes(self):
        # Test 'update' action.
        # 1st LLM call: requests StrReplaceEditorTool
        # 2nd LLM call: provides final text response

        tool_call_id = "call_str_replace_123"
        mock_tool_call = ToolCall(
            tool_call_id=tool_call_id,
            tool_name="str_replace_editor",
            tool_input={"command": "str_replace", "path": "slides/intro.html", "old_str": "old", "new_str": "new"}
        )

        self.mock_llm_client.generate.side_effect = [
            ([mock_tool_call], {}), # First call - LLM calls a tool
            ([TextResult(text="Update complete.")], {}) # Second call - LLM gives text response
        ]

        # Mock the StrReplaceEditorTool's run method
        self.mock_str_replace_tool_instance.run.return_value = ("Content replaced successfully.", {}) # Tool run returns tuple

        tool_input = {"action": "update", "description": "Update the intro slide"}
        result = self.tool.run_impl(tool_input)

        self.assertTrue(result.auxiliary_data["success"])
        self.assertEqual(result.tool_output, "Update complete.")

        self.assertEqual(self.mock_llm_client.generate.call_count, 2)
        self.mock_str_replace_tool_instance.run.assert_called_once()
        # Check history for tool call and result
        messages = self.tool.history.get_messages()
        self.assertIsInstance(messages[-2].content[0], ToolCall) # Assistant's tool call
        self.assertEqual(messages[-2].content[0].tool_call_id, tool_call_id)
        self.assertIsInstance(messages[-1].content[0], ToolFormattedResult) # User's tool result (simulated)
        self.assertEqual(messages[-1].content[0].tool_output, "Content replaced successfully.")


    def test_non_init_action_max_turns_exceeded(self):
        # Simulate LLM always calling a tool, leading to max_turns
        self.tool.max_turns = 2 # Set low for test

        mock_tool_call = ToolCall(tool_call_id="call_loop", tool_name="str_replace_editor", tool_input={"command": "view", "path": "."})
        self.mock_llm_client.generate.return_value = ([mock_tool_call], {})
        self.mock_str_replace_tool_instance.run.return_value = ("Viewed.", {})

        tool_input = {"action": "final_check", "description": "Loop check"}
        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn(f"Action 'final_check' did not complete after {self.tool.max_turns} turns", result.tool_output)
        self.assertEqual(self.mock_llm_client.generate.call_count, self.tool.max_turns)


if __name__ == "__main__":
    unittest.main()
