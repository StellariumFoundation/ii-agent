import unittest
from unittest.mock import MagicMock, patch

from src.ii_agent.tools.memory.compactify_memory import CompactifyMemoryTool
from src.ii_agent.llm.context_manager.base import ContextManager # For type hinting and mocking spec
from src.ii_agent.llm.message_history import MessageHistory # For type hinting and mocking spec
from src.ii_agent.tools.base import ToolImplOutput
from src.ii_agent.llm.base import LLMMessages, UserContentBlock, TextPrompt # For sample messages

class TestCompactifyMemoryTool(unittest.TestCase):
    def setUp(self):
        self.mock_context_manager = MagicMock(spec=ContextManager)
        self.tool = CompactifyMemoryTool(context_manager=self.mock_context_manager)

    def test_run_impl_success(self):
        mock_message_history = MagicMock(spec=MessageHistory)

        original_messages: LLMMessages = [
            [UserContentBlock(content=TextPrompt(text="Message 1"))],
            [UserContentBlock(content=TextPrompt(text="Message 2"))],
        ]
        compacted_messages: LLMMessages = [
            [UserContentBlock(content=TextPrompt(text="Compacted Message"))]
        ]

        mock_message_history.get_messages_for_llm.return_value = original_messages
        self.mock_context_manager.apply_truncation.return_value = compacted_messages

        tool_input = {} # No input parameters for this tool
        result = self.tool.run_impl(tool_input, message_history=mock_message_history)

        mock_message_history.get_messages_for_llm.assert_called_once()
        self.mock_context_manager.apply_truncation.assert_called_once_with(original_messages)
        mock_message_history.set_message_list.assert_called_once_with(compacted_messages)

        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.tool_output, "Memory compactified.")
        self.assertEqual(result.tool_result_message, "Memory compactified.")
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_no_message_history_provided(self):
        tool_input = {}
        result = self.tool.run_impl(tool_input, message_history=None)

        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.tool_output, "Message history is required to compactify memory.")
        self.assertFalse(result.auxiliary_data["success"])
        self.mock_context_manager.apply_truncation.assert_not_called()

    def test_run_impl_context_manager_returns_same_messages(self):
        # Scenario: history doesn't need compaction, apply_truncation returns original
        mock_message_history = MagicMock(spec=MessageHistory)
        original_messages: LLMMessages = [[UserContentBlock(content=TextPrompt(text="Short history"))]]

        mock_message_history.get_messages_for_llm.return_value = original_messages
        # Context manager decides no compaction is needed
        self.mock_context_manager.apply_truncation.return_value = original_messages

        tool_input = {}
        result = self.tool.run_impl(tool_input, message_history=mock_message_history)

        mock_message_history.set_message_list.assert_called_once_with(original_messages)
        self.assertTrue(result.auxiliary_data["success"])
        self.assertEqual(result.tool_output, "Memory compactified.")


if __name__ == "__main__":
    unittest.main()
