import unittest
from unittest.mock import patch, MagicMock, AsyncMock # AsyncMock if client.generate is async
import asyncio
import logging

from src.ii_agent.utils.prompt_generator import enhance_user_prompt
from src.ii_agent.llm.base import LLMClient, TextPrompt, TextResult # For type hinting and constructing responses

# Suppress logger output during tests for this module
logging.getLogger("prompt_generator").setLevel(logging.CRITICAL + 1)

class TestEnhanceUserPrompt(unittest.TestCase):

    def setUp(self):
        self.mock_llm_client = MagicMock(spec=LLMClient)
        # Assuming client.generate is a standard method. If it's async, this needs to be AsyncMock.
        # The calling code `response_blocks, _ = client.generate(...)` suggests it's not async.
        # If it were async, enhance_user_prompt would need to be `async def` and awaited.
        # The function signature is `async def enhance_user_prompt`, so client.generate *should* be awaited
        # if it's an async method. The provided code does not `await client.generate`.
        # This implies client.generate might be synchronous, or there's a slight inconsistency.
        # For now, will mock client.generate as synchronous. If tests reveal it needs to be async,
        # self.mock_llm_client.generate will be changed to AsyncMock.

        # Re-evaluating: enhance_user_prompt IS async def.
        # Therefore, client.generate is likely an async method or a method on an async client.
        # However, the call is `client.generate(...)` not `await client.generate(...)`.
        # This is a contradiction. I will assume client.generate is synchronous based on the direct call.
        # If it's meant to be async, the `enhance_user_prompt` code needs `await`.
        # Let's proceed by mocking it as synchronous. The test will fail if it's truly async
        # and not awaited, or if the mock type is wrong.
        #
        # UPDATE after seeing AnthropicFC: client.generate *is* synchronous in the base LLMClient type used there.
        # So, MagicMock for client.generate is fine.

    async def _run_enhance_prompt(self, client, user_input, files, temp=0.7, tokens=2048):
        # Helper to run the async function enhance_user_prompt
        return await enhance_user_prompt(client, user_input, files, temp, tokens)

    def test_successful_enhancement_no_files(self):
        user_input = "make a cool app"
        files = []
        expected_enhanced_prompt = "Create a revolutionary mobile application with a sleek UI and robust backend."

        self.mock_llm_client.generate.return_value = ([TextResult(text=expected_enhanced_prompt)], {"usage": {}}) # Simulate LLM response

        success, message, enhanced_prompt = asyncio.run(
            self._run_enhance_prompt(self.mock_llm_client, user_input, files)
        )

        self.assertTrue(success)
        self.assertEqual(message, "Prompt enhanced successfully")
        self.assertEqual(enhanced_prompt, expected_enhanced_prompt)

        self.mock_llm_client.generate.assert_called_once()
        call_args = self.mock_llm_client.generate.call_args
        # Check system prompt passed
        self.assertIn("expert at enhancing user requests", call_args.kwargs["system_prompt"])
        # Check user message passed to LLM
        llm_user_message_content = call_args.kwargs["messages"][0][0].text
        self.assertIn(f"Enhance this request into a detailed prompt: {user_input}", llm_user_message_content)
        self.assertIn("Additional context - \n", llm_user_message_content) # Empty file context

    def test_successful_enhancement_with_files(self):
        user_input = "summarize these documents"
        files = ["./docs/doc1.txt", "src/code.py"]
        expected_enhanced_prompt = "Provide a concise summary of the key points from docs/doc1.txt and src/code.py."

        self.mock_llm_client.generate.return_value = ([TextResult(text=expected_enhanced_prompt)], {})

        success, message, enhanced_prompt = asyncio.run(
            self._run_enhance_prompt(self.mock_llm_client, user_input, files)
        )

        self.assertTrue(success)
        self.assertEqual(enhanced_prompt, expected_enhanced_prompt)

        llm_user_message_content = self.mock_llm_client.generate.call_args.kwargs["messages"][0][0].text
        self.assertIn("Referenced files:", llm_user_message_content)
        self.assertIn("- docs/doc1.txt", llm_user_message_content) # Leading ./ should be stripped by tool
        self.assertIn("- src/code.py", llm_user_message_content)


    def test_llm_generate_returns_multiple_text_blocks(self):
        user_input = "explain quantum physics"
        # Simulate LLM returning multiple text blocks
        self.mock_llm_client.generate.return_value = (
            [TextResult(text="Part 1. "), TextResult(text="Part 2.")], {}
        )

        success, _, enhanced_prompt = asyncio.run(
            self._run_enhance_prompt(self.mock_llm_client, user_input, [])
        )
        self.assertTrue(success)
        self.assertEqual(enhanced_prompt, "Part 1. Part 2.") # Should concatenate

    def test_llm_generate_returns_no_text_blocks(self):
        user_input = "what if no text"
        # Simulate LLM returning no usable text blocks (e.g. only other types or empty list)
        self.mock_llm_client.generate.return_value = ([], {})

        success, _, enhanced_prompt = asyncio.run(
            self._run_enhance_prompt(self.mock_llm_client, user_input, [])
        )
        self.assertTrue(success) # Still success, but prompt is empty
        self.assertEqual(enhanced_prompt, "")


    @patch('src.ii_agent.utils.prompt_generator.logger') # Patch the logger in the module
    def test_llm_generate_raises_exception(self, mock_logger):
        user_input = "trigger error"
        error_message = "LLM API exploded"
        self.mock_llm_client.generate.side_effect = Exception(error_message)

        success, message, enhanced_prompt = asyncio.run(
            self._run_enhance_prompt(self.mock_llm_client, user_input, [])
        )

        self.assertFalse(success)
        self.assertIn(f"Error enhancing prompt: {error_message}", message)
        self.assertIsNone(enhanced_prompt)
        mock_logger.error.assert_any_call(f"Error enhancing prompt: {error_message}")
        mock_logger.error.assert_any_call(unittest.mock.ANY) # For traceback


if __name__ == "__main__":
    unittest.main()
