import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
from pathlib import Path

# Import tools to be tested
from src.ii_agent.tools.advanced_tools.gemini.audio_tool import AudioTranscribeTool, AudioUnderstandingTool
# Import base and other necessary classes
from src.ii_agent.tools.advanced_tools.gemini.base import GeminiTool # For patching its client
from src.ii_agent.utils import WorkspaceManager
from src.ii_agent.tools.base import ToolImplOutput
# Attempting to fix import based on typical google cloud structure
from google.genai import types as genai_types # For constructing mock responses
import google.genai as genai # Ensure genai alias is available

# Mock genai client if not available or to control behavior
# try:
#     from google.cloud.aiplatform import generativeai as genai # Already imported and aliased
# except ImportError:
# genai = MagicMock() # genai should now be properly imported or an earlier error would occur


class CommonGeminiAudioToolTests(unittest.TestCase):
    """Common setup for Gemini audio tools."""
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_workspace_manager.workspace_path.side_effect = lambda p: Path("/fake/workspace") / p

        # Mock environment variable for API key
        self.env_patcher = patch.dict(os.environ, {"GEMINI_API_KEY": "test_gemini_key"})
        self.env_patcher.start()

        # Patch the genai.Client constructor used in GeminiTool base class
        self.genai_client_patcher = patch('google.genai.Client')
        self.MockGenaiClientConstructor = self.genai_client_patcher.start()

        self.mock_gemini_client_instance = MagicMock(spec=genai.Client)
        self.MockGenaiClientConstructor.return_value = self.mock_gemini_client_instance

        # This is what will be called by the tools: self.client.models.generate_content
        self.mock_generate_content_method = MagicMock()
        # Simulate the nested structure: client.models.generate_content
        self.mock_gemini_client_instance.models = MagicMock()
        self.mock_gemini_client_instance.models.generate_content = self.mock_generate_content_method


    def tearDown(self):
        self.genai_client_patcher.stop()
        self.env_patcher.stop()


class TestAudioTranscribeTool(CommonGeminiAudioToolTests):
    def setUp(self):
        super().setUp()
        self.tool = AudioTranscribeTool(workspace_manager=self.mock_workspace_manager, model="gemini-test-model")

    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_audio_bytes")
    def test_run_impl_success(self, mock_file):
        file_path = "audio/test.mp3"
        tool_input = {"file_path": file_path}

        mock_response = MagicMock()
        mock_response.text = "This is a transcript."
        self.mock_generate_content_method.return_value = mock_response

        result = self.tool.run_impl(tool_input)

        abs_path_str = str(self.mock_workspace_manager.workspace_path(file_path))
        mock_file.assert_called_once_with(abs_path_str, "rb")

        self.mock_generate_content_method.assert_called_once()
        args, kwargs = self.mock_generate_content_method.call_args
        self.assertEqual(kwargs['model'], "gemini-test-model")
        # Check contents passed to Gemini
        content_arg = kwargs['contents']
        self.assertIsInstance(content_arg, genai_types.Content)
        self.assertEqual(len(content_arg.parts), 2)
        self.assertEqual(content_arg.parts[0].text, "Provide a transcription of the audio")
        self.assertEqual(content_arg.parts[1].inline_data.data, b"fake_audio_bytes")
        self.assertEqual(content_arg.parts[1].inline_data.mime_type, "audio/mp3") # Hardcoded in tool

        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.tool_output, "This is a transcript.")
        self.assertEqual(result.tool_result_message, "This is a transcript.") # output_for_user is same as llm

    @patch("builtins.open", new_callable=mock_open, read_data=b"data")
    def test_run_impl_gemini_api_error(self, mock_file):
        self.mock_generate_content_method.side_effect = Exception("Gemini API failed")
        tool_input = {"file_path": "audio/error.wav"}

        with patch('builtins.print') as mock_print: # Suppress print(e)
            result = self.tool.run_impl(tool_input)

        self.assertEqual(result.tool_output, "Error analyzing the audio file, try again later.")
        mock_print.assert_called_once() # Check that error was printed by tool

    @patch("builtins.open", side_effect=FileNotFoundError("File not present"))
    def test_run_impl_file_not_found_error(self, mock_file):
        tool_input = {"file_path": "audio/absent.ogg"}
        with patch('builtins.print') as mock_print:
            result = self.tool.run_impl(tool_input)
        # The tool's general exception handler will catch FileNotFoundError from open()
        self.assertEqual(result.tool_output, "Error analyzing the audio file, try again later.")
        mock_print.assert_called_with(FileNotFoundError("File not present"))


class TestAudioUnderstandingTool(CommonGeminiAudioToolTests):
    def setUp(self):
        super().setUp()
        self.tool = AudioUnderstandingTool(workspace_manager=self.mock_workspace_manager, model="gemini-understand-model")

    @patch("builtins.open", new_callable=mock_open, read_data=b"more_audio_bytes")
    def test_run_impl_success(self, mock_file):
        file_path = "audio/meeting.aac"
        user_query = "Summarize the meeting."
        tool_input = {"file_path": file_path, "query": user_query}

        mock_response = MagicMock()
        mock_response.text = "The meeting was about project Alpha."
        self.mock_generate_content_method.return_value = mock_response

        result = self.tool.run_impl(tool_input)

        abs_path_str = str(self.mock_workspace_manager.workspace_path(file_path))
        mock_file.assert_called_once_with(abs_path_str, "rb")

        self.mock_generate_content_method.assert_called_once()
        args, kwargs = self.mock_generate_content_method.call_args
        self.assertEqual(kwargs['model'], "gemini-understand-model")
        content_arg = kwargs['contents']
        self.assertEqual(content_arg.parts[0].text, user_query) # User query is first
        self.assertEqual(content_arg.parts[1].inline_data.data, b"more_audio_bytes")
        self.assertEqual(content_arg.parts[1].inline_data.mime_type, "audio/mp3")


        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.tool_output, "The meeting was about project Alpha.")

    @patch("builtins.open", new_callable=mock_open, read_data=b"data")
    def test_run_impl_gemini_api_error_understanding(self, mock_file):
        self.mock_generate_content_method.side_effect = Exception("Gemini API understand error")
        tool_input = {"file_path": "audio/q.flac", "query": "What is this?"}

        with patch('builtins.print') as mock_print:
            result = self.tool.run_impl(tool_input)

        self.assertEqual(result.tool_output, "Error analyzing the audio file, try again later.")


if __name__ == "__main__":
    unittest.main()
