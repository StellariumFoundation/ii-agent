import unittest
from unittest.mock import patch, MagicMock
import os
from pathlib import Path

# Import tool to be tested
from src.ii_agent.tools.advanced_tools.gemini.video_tool import YoutubeVideoUnderstandingTool
# Import base and other necessary classes
from src.ii_agent.tools.advanced_tools.gemini.base import GeminiTool # For patching its client
from src.ii_agent.utils import WorkspaceManager
from src.ii_agent.tools.base import ToolImplOutput
# Attempting to fix import based on typical google cloud structure
from google.generativeai import types as genai_types # For constructing mock responses and FileData
import google.generativeai as genai # Ensure genai alias is available


# Mock genai client if not available or to control behavior
# try:
#     from google.cloud.aiplatform import generativeai as genai # Already imported and aliased
# except ImportError:
# genai = MagicMock() # genai should now be properly imported or an earlier error would occur


class TestYoutubeVideoUnderstandingTool(unittest.TestCase):
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        # WorkspaceManager is part of GeminiTool's __init__ but not directly used by this specific tool's run_impl

        self.env_patcher = patch.dict(os.environ, {"GEMINI_API_KEY": "test_gemini_key"})
        self.env_patcher.start()

        self.genai_client_patcher = patch('google.generativeai.GenerativeModel') # Changed from Client
        self.MockGenaiClientConstructor = self.genai_client_patcher.start()

        self.mock_gemini_client_instance = MagicMock(spec=genai.GenerativeModel) # Changed spec
        self.MockGenaiClientConstructor.return_value = self.mock_gemini_client_instance

        self.mock_generate_content_method = MagicMock()
        # Assuming generate_content is directly on the client instance now
        self.mock_gemini_client_instance.generate_content = self.mock_generate_content_method

        self.tool = YoutubeVideoUnderstandingTool(workspace_manager=self.mock_workspace_manager, model="gemini-video-model")

    def tearDown(self):
        self.genai_client_patcher.stop()
        self.env_patcher.stop()

    def test_run_impl_success(self):
        video_url = "https://www.youtube.com/watch?v=testvideo"
        user_query = "What is this video about?"
        tool_input = {"url": video_url, "query": user_query}

        # Mock the Gemini API response structure
        mock_part = MagicMock(spec=genai_types.Part)
        mock_part.text = "This video is about testing."
        mock_content = MagicMock(spec=genai_types.Content)
        mock_content.parts = [mock_part]
        mock_candidate = MagicMock()
        mock_candidate.content = mock_content
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        self.mock_generate_content_method.return_value = mock_response

        result = self.tool.run_impl(tool_input)

        self.mock_generate_content_method.assert_called_once()
        args, kwargs = self.mock_generate_content_method.call_args
        self.assertEqual(kwargs['model'], "gemini-video-model")

        # Check contents passed to Gemini
        content_arg = kwargs['contents']
        self.assertIsInstance(content_arg, genai_types.Content)
        self.assertEqual(len(content_arg.parts), 2)
        # Order of parts in the tool: FileData first, then text query
        self.assertIsInstance(content_arg.parts[0].file_data, genai_types.FileData)
        self.assertEqual(content_arg.parts[0].file_data.file_uri, video_url)
        self.assertEqual(content_arg.parts[1].text, user_query)

        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.tool_output, "This video is about testing.")
        self.assertEqual(result.tool_result_message, "This video is about testing.")

    def test_run_impl_gemini_api_error(self):
        self.mock_generate_content_method.side_effect = Exception("Gemini API video failed")
        tool_input = {"url": "https://www.youtube.com/watch?v=errorvideo", "query": "Does this error?"}

        with patch('builtins.print') as mock_print: # Suppress print(e)
            result = self.tool.run_impl(tool_input)

        self.assertEqual(result.tool_output, "Error analyzing the Youtube video, try again later.")
        mock_print.assert_called_once()

    def test_run_impl_malformed_response_no_candidates(self):
        mock_response = MagicMock()
        mock_response.candidates = [] # Empty candidates list
        self.mock_generate_content_method.return_value = mock_response
        tool_input = {"url": "https://www.youtube.com/watch?v=malformed1", "query": "Test"}

        with patch('builtins.print') as mock_print:
            result = self.tool.run_impl(tool_input)
        self.assertEqual(result.tool_output, "Error analyzing the Youtube video, try again later.")
        # Expect an IndexError when accessing candidates[0]
        self.assertTrue(any("list index out of range" in str(arg[0][0]) for arg in mock_print.call_args_list))


    def test_run_impl_malformed_response_no_parts(self):
        mock_content = MagicMock(spec=genai_types.Content)
        mock_content.parts = [] # Empty parts list
        mock_candidate = MagicMock()
        mock_candidate.content = mock_content
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        self.mock_generate_content_method.return_value = mock_response
        tool_input = {"url": "https://www.youtube.com/watch?v=malformed2", "query": "Test"}

        with patch('builtins.print') as mock_print:
            result = self.tool.run_impl(tool_input)
        self.assertEqual(result.tool_output, "Error analyzing the Youtube video, try again later.")
        # Expect an IndexError when accessing parts[0]
        self.assertTrue(any("list index out of range" in str(arg[0][0]) for arg in mock_print.call_args_list))


if __name__ == "__main__":
    unittest.main()
