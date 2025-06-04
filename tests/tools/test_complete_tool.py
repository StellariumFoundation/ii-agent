import unittest
from unittest.mock import MagicMock

from src.ii_agent.tools.complete_tool import CompleteTool, ReturnControlToUserTool # Importing both for now, focusing on CompleteTool
from src.ii_agent.tools.base import ToolImplOutput
# from ii_agent.llm.message_history import MessageHistory # Not strictly needed for these tests if run_impl doesn't rely heavily on it


class TestCompleteTool(unittest.TestCase):
    def setUp(self):
        self.tool = CompleteTool()

    def test_initial_state(self):
        self.assertEqual(self.tool.answer, "")
        self.assertFalse(self.tool.should_stop)

    def test_run_impl_success(self):
        test_answer = "This is the final answer."
        tool_input = {"answer": test_answer}

        # The execute method from the base class LLMTool calls run_impl.
        # We can test run_impl directly as it contains the core logic.
        # Or, if we want to test the full flow as called by an agent, we'd call execute.
        # For this tool, run_impl is simple enough.
        result = self.tool.run_impl(tool_input)

        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.tool_output, "Task completed")
        self.assertEqual(result.tool_result_message, "Task completed")
        self.assertEqual(self.tool.answer, test_answer)
        self.assertTrue(self.tool.should_stop)

    def test_run_impl_missing_answer_assertion(self):
        # The code asserts `tool_input["answer"]`. If "answer" key is missing, it's a KeyError.
        # If "answer" key exists but value is None/empty, it's an AssertionError.
        with self.assertRaises(KeyError):
            self.tool.run_impl({})

        with self.assertRaises(AssertionError) as context:
            self.tool.run_impl({"answer": ""}) # Empty answer
        self.assertEqual(str(context.exception), "Model returned empty answer")

        with self.assertRaises(AssertionError) as context:
            self.tool.run_impl({"answer": None}) # None answer
        self.assertEqual(str(context.exception), "Model returned empty answer")


    def test_reset_method(self):
        self.tool.run_impl({"answer": "Some answer"})
        self.assertTrue(self.tool.should_stop)
        self.assertNotEqual(self.tool.answer, "")

        self.tool.reset()
        self.assertEqual(self.tool.answer, "")
        self.assertFalse(self.tool.should_stop)

    def test_get_tool_start_message(self):
        self.assertEqual(self.tool.get_tool_start_message({"answer": "test"}), "")


class TestReturnControlToUserTool(unittest.TestCase):
    def setUp(self):
        self.tool = ReturnControlToUserTool()

    def test_initial_state_return_control(self):
        self.assertEqual(self.tool.answer, "")
        self.assertFalse(self.tool.should_stop)

    def test_run_impl_success_return_control(self):
        # Input schema is empty, so any valid dict is fine, or even an empty one.
        tool_input = {}
        result = self.tool.run_impl(tool_input)

        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.tool_output, "Task completed")
        self.assertEqual(result.tool_result_message, "Task completed")
        self.assertEqual(self.tool.answer, "Task completed") # Sets a fixed answer
        self.assertTrue(self.tool.should_stop)

    def test_reset_method_return_control(self):
        self.tool.run_impl({})
        self.assertTrue(self.tool.should_stop)
        self.assertEqual(self.tool.answer, "Task completed")

        self.tool.reset()
        self.assertEqual(self.tool.answer, "")
        self.assertFalse(self.tool.should_stop)

    def test_get_tool_start_message_return_control(self):
        self.assertEqual(self.tool.get_tool_start_message({}), "")


if __name__ == "__main__":
    unittest.main()
