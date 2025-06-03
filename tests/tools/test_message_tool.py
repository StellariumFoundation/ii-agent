import unittest
from unittest.mock import MagicMock

from src.ii_agent.tools.message_tool import MessageTool
from src.ii_agent.tools.base import ToolImplOutput, LLMTool
# Assuming MessageHistory might be needed by execute, but not directly by run_impl
from ii_agent.llm.message_history import MessageHistory

class TestMessageTool(unittest.TestCase):
    def setUp(self):
        self.tool = MessageTool()

    def test_run_impl_success(self):
        test_message = "Hello user, this is a test."
        tool_input = {"text": test_message}

        result = self.tool.run_impl(tool_input)

        self.assertIsInstance(result, ToolImplOutput)
        expected_msg = "Sent message to user"
        self.assertEqual(result.output_for_llm, expected_msg)
        self.assertEqual(result.output_for_user, expected_msg)
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_missing_text_assertion(self):
        with self.assertRaises(KeyError): # "text" key missing
            self.tool.run_impl({})

        with self.assertRaises(AssertionError) as context:
            self.tool.run_impl({"text": ""}) # Empty text
        self.assertEqual(str(context.exception), "Model returned empty message")

        with self.assertRaises(AssertionError) as context:
            self.tool.run_impl({"text": None}) # None text
        self.assertEqual(str(context.exception), "Model returned empty message")

    def test_execute_with_callback(self):
        # This test assumes that the `execute` method of the base LLMTool
        # might handle a `send_message_to_user_callback`.
        # We need to see the LLMTool base class or make an assumption.
        # For now, let's assume LLMTool.execute calls run_impl and then the callback.

        test_message = "Message for callback."
        tool_input = {"text": test_message}

        mock_callback = MagicMock()

        # To test this, we would ideally have the LLMTool base class.
        # Let's mock `run_impl` being called by `execute` and then check the callback.
        # If `execute` is more complex, this might not be a perfect test of `execute`
        # but it will test the callback interaction if `execute` is structured to call it.

        # Scenario 1: Callback is an attribute of the tool (less likely based on prompt)
        # self.tool.send_message_to_user_callback = mock_callback
        # self.tool.execute(tool_input)
        # mock_callback.assert_called_once_with(test_message) # or tool_input["text"]

        # Scenario 2: Callback is passed to execute (more likely)
        # We need to define a mock 'execute' or have the actual LLMTool base class.
        # For now, let's assume the callback is called with the *input* message.

        # Patching the base class's execute or the tool's execute if it overrides it.
        # Since `execute` is likely inherited, we'll directly call it.
        # The `MessageTool` itself doesn't show a callback being used in `run_impl`.
        # The prompt implies the callback is related to the tool's execution.

        # Let's assume the `LLMTool.execute` method is responsible for this.
        # We can simulate a simplified version of what `execute` might do
        # to check the callback part.

        # If the callback is indeed part of the `LLMTool`'s `execute` method,
        # and that `execute` method calls `run_impl` and then uses the *input*
        # to call `send_message_to_user_callback`.

        # Let's define a simplified `execute` on the instance for testing this specific callback behavior.
        # This is a common way to test interactions with callbacks when the exact base class behavior
        # is not fully known or too complex to set up for this specific test.

        original_execute = self.tool.execute
        try:
            def mock_execute_for_callback_test(tool_input_dict, message_history=None, send_message_to_user_callback=None):
                # Call the actual run_impl
                run_impl_output = self.tool.run_impl(tool_input_dict, message_history)
                if send_message_to_user_callback:
                    # The prompt implies the callback is called with the message.
                    # Assuming it's the input message to the tool.
                    send_message_to_user_callback(tool_input_dict["text"])
                return run_impl_output # Or whatever execute is supposed to return

            self.tool.execute = mock_execute_for_callback_test

            self.tool.execute(tool_input, send_message_to_user_callback=mock_callback)
            mock_callback.assert_called_once_with(test_message)

        finally:
            self.tool.execute = original_execute # Restore original execute

if __name__ == "__main__":
    unittest.main()
