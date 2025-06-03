import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from src.ii_agent.tools.deep_research_tool import DeepResearchTool, get_event_loop, on_token
from src.ii_agent.tools.base import ToolImplOutput
# Assuming ReasoningAgent and ReportType are importable for type checking or direct use if not mocking everything
from ii_researcher.reasoning.agent import ReasoningAgent
from ii_researcher.reasoning.builders.report import ReportType


class TestDeepResearchTool(unittest.TestCase):
    def setUp(self):
        self.tool = DeepResearchTool()

    def test_initial_state(self):
        self.assertEqual(self.tool.answer, "")
        self.assertFalse(self.tool.should_stop)

    @patch('src.ii_agent.tools.deep_research_tool.ReasoningAgent')
    def test_run_impl_success(self, MockReasoningAgent):
        mock_agent_instance = MagicMock(spec=ReasoningAgent)
        # The run method is async, so mock it with AsyncMock
        mock_agent_instance.run = AsyncMock(return_value="Comprehensive research report.")
        MockReasoningAgent.return_value = mock_agent_instance

        query = "future of AI"
        tool_input = {"query": query}

        # Ensure get_event_loop provides a running loop for run_until_complete
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            with patch('builtins.print') as mock_print: # Suppress prints from tool
                result = self.tool.run_impl(tool_input)
        finally:
            loop.close() # Clean up the event loop
            asyncio.set_event_loop(None) # Reset the event loop for other tests


        MockReasoningAgent.assert_called_once_with(question=query, report_type=ReportType.BASIC)
        mock_agent_instance.run.assert_called_once_with(on_token=on_token, is_stream=True)

        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.output_for_llm, "Comprehensive research report.")
        self.assertEqual(result.output_for_user, "Task completed")
        self.assertEqual(self.tool.answer, "Comprehensive research report.")
        self.assertTrue(self.tool.should_stop)

    @patch('src.ii_agent.tools.deep_research_tool.ReasoningAgent')
    def test_run_impl_empty_result_from_agent(self, MockReasoningAgent):
        mock_agent_instance = MagicMock(spec=ReasoningAgent)
        mock_agent_instance.run = AsyncMock(return_value="") # Agent returns empty string
        MockReasoningAgent.return_value = mock_agent_instance

        tool_input = {"query": "niche topic"}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        with self.assertRaises(AssertionError) as context:
            with patch('builtins.print'):
                 self.tool.run_impl(tool_input)
        self.assertEqual(str(context.exception), "Model returned empty answer")

        loop.close()
        asyncio.set_event_loop(None)


    @patch('src.ii_agent.tools.deep_research_tool.ReasoningAgent')
    def test_run_impl_agent_run_raises_exception(self, MockReasoningAgent):
        mock_agent_instance = MagicMock(spec=ReasoningAgent)
        mock_agent_instance.run = AsyncMock(side_effect=Exception("Agent failed"))
        MockReasoningAgent.return_value = mock_agent_instance

        tool_input = {"query": "error query"}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # The tool's run_impl doesn't currently catch exceptions from agent.run()
        with self.assertRaises(Exception) as context:
            with patch('builtins.print'):
                self.tool.run_impl(tool_input)
        self.assertEqual(str(context.exception), "Agent failed")

        loop.close()
        asyncio.set_event_loop(None)


    def test_reset_method(self):
        self.tool.answer = "Some previous answer"
        self.assertTrue(self.tool.should_stop)

        self.tool.reset()
        self.assertEqual(self.tool.answer, "")
        self.assertFalse(self.tool.should_stop)

    def test_get_tool_start_message(self):
        query = "test query for start message"
        tool_input = {"query": query}
        self.assertEqual(self.tool.get_tool_start_message(tool_input), f"Performing deep research on {query}")

    def test_get_event_loop_creates_new_if_none(self):
        # Ensure no loop is running for this thread initially
        asyncio.set_event_loop(None)
        loop = get_event_loop()
        self.assertIsNotNone(loop)
        self.assertTrue(loop.is_running() or not loop.is_closed()) # New loop is not closed
        # Clean up by setting the loop and closing it if this test created it
        asyncio.set_event_loop(loop)
        loop.close()
        asyncio.set_event_loop(None)

    def test_get_event_loop_returns_existing(self):
        existing_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(existing_loop)

        returned_loop = get_event_loop()
        self.assertIs(returned_loop, existing_loop)

        existing_loop.close()
        asyncio.set_event_loop(None)


if __name__ == "__main__":
    unittest.main()
