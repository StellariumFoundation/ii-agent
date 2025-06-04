import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import base64
import subprocess # For CalledProcessError
from pathlib import Path

from src.ii_agent.tools.advanced_tools.audio_tool import AudioTranscribeTool, AudioGenerateTool, SUPPORTED_AUDIO_FORMATS, AVAILABLE_VOICES
from src.ii_agent.utils import WorkspaceManager
from src.ii_agent.tools.base import ToolImplOutput
from openai import APIError # For mocking API errors

# Mock AzureOpenAI client if not available or to control behavior
try:
    from openai import AzureOpenAI
except ImportError:
    AzureOpenAI = MagicMock()


class TestAudioTranscribeTool(unittest.TestCase):
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_workspace_manager.workspace_path.side_effect = lambda p: Path("/fake/workspace") / p

        # Patch the AzureOpenAI client constructor within the tool's module
        self.azure_openai_patcher = patch('src.ii_agent.tools.advanced_tools.audio_tool.AzureOpenAI')
        self.MockAzureOpenAIClass = self.azure_openai_patcher.start()
        self.mock_openai_client_instance = MagicMock()
        self.MockAzureOpenAIClass.return_value = self.mock_openai_client_instance

        self.tool = AudioTranscribeTool(workspace_manager=self.mock_workspace_manager)

    def tearDown(self):
        self.azure_openai_patcher.stop()

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.is_file", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_audio_data")
    def test_run_impl_success(self, mock_file_open, mock_is_file, mock_exists):
        file_path_str = "audio.mp3" # Supported format
        mock_transcript_obj = MagicMock()
        mock_transcript_obj.text = "This is a test transcript."
        self.mock_openai_client_instance.audio.transcriptions.create.return_value = mock_transcript_obj

        tool_input = {"file_path": file_path_str}
        result = self.tool.run_impl(tool_input)

        full_path = self.mock_workspace_manager.workspace_path(Path(file_path_str))
        mock_file_open.assert_called_once_with(full_path, "rb")
        self.mock_openai_client_instance.audio.transcriptions.create.assert_called_once_with(
            model="gpt-4o-transcribe", file=mock_file_open.return_value
        )
        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.tool_output, "This is a test transcript.")
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_file_not_found(self):
        with patch("pathlib.Path.exists", return_value=False):
            tool_input = {"file_path": "nonexistent.mp3"}
            result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("File not found", result.tool_output)

    def test_run_impl_path_not_a_file(self):
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=False):
            tool_input = {"file_path": "directory_path"}
            result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("is not a file", result.tool_output)

    def test_run_impl_unsupported_format(self):
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=True):
            tool_input = {"file_path": "audio.txt"} # .txt is not supported
            result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("not supported for transcription", result.tool_output)

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.is_file", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data=b"data")
    def test_run_impl_openai_api_error(self, mock_file, mock_is_file, mock_exists):
        self.mock_openai_client_instance.audio.transcriptions.create.side_effect = APIError(
            message="API Error", request=MagicMock(), body=None
        )
        tool_input = {"file_path": "audio.wav"}
        result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("OpenAI API Error", result.tool_output)


class TestAudioGenerateTool(unittest.TestCase):
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_workspace_manager.workspace_path.side_effect = lambda p: Path("/fake/workspace") / p

        self.azure_openai_patcher = patch('src.ii_agent.tools.advanced_tools.audio_tool.AzureOpenAI')
        self.MockAzureOpenAIClass = self.azure_openai_patcher.start()
        self.mock_openai_client_instance = MagicMock()
        self.MockAzureOpenAIClass.return_value = self.mock_openai_client_instance

        # Mock ffmpeg check in __init__ to prevent actual subprocess call during test setup
        self.ffmpeg_check_patcher = patch.object(AudioGenerateTool, '_check_ffmpeg', return_value=None)
        self.mock_check_ffmpeg = self.ffmpeg_check_patcher.start()

        self.tool = AudioGenerateTool(workspace_manager=self.mock_workspace_manager)

    def tearDown(self):
        self.azure_openai_patcher.stop()
        self.ffmpeg_check_patcher.stop()

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run")
    @patch("os.remove")
    def test_run_impl_success(self, mock_os_remove, mock_subprocess_run, mock_file_open, mock_mkdir):
        tool_input = {
            "text": "Hello, this is a test audio.",
            "output_filename": "generated/speech.mp3",
            "voice": "alloy"
        }

        mock_completion_choice = MagicMock()
        mock_completion_choice.message.audio.data = base64.b64encode(b"fake_wav_data").decode('utf-8')
        mock_completion_response = MagicMock()
        mock_completion_response.choices = [mock_completion_choice]
        self.mock_openai_client_instance.chat.completions.create.return_value = mock_completion_response

        mock_subprocess_run.return_value = MagicMock(returncode=0) # Simulate ffmpeg success

        result = self.tool.run_impl(tool_input)

        self.assertTrue(result.auxiliary_data["success"])
        self.assertIn("Successfully generated audio", result.tool_output)
        self.assertEqual(result.auxiliary_data["output_path"], "generated/speech.mp3")

        # Check API call
        self.mock_openai_client_instance.chat.completions.create.assert_called_once()
        # Check file operations
        # Expected temp WAV path will have a hash name in 'uploads/'
        self.assertTrue(mock_file_open.call_args_list[0][0][0].match("*/uploads/*.wav")) # temp wav saved
        # Check ffmpeg call
        mock_subprocess_run.assert_called_once()
        self.assertEqual(mock_subprocess_run.call_args[0][0][0], "ffmpeg")
        self.assertIn("-i", mock_subprocess_run.call_args[0][0])
        self.assertIn(str(self.mock_workspace_manager.workspace_path(Path("generated/speech.mp3"))), mock_subprocess_run.call_args[0][0])
        # Check temp file removal
        self.assertTrue(mock_os_remove.called)


    def test_run_impl_invalid_output_filename(self):
        tool_input = {"text": "test", "output_filename": "speech.wav"} # Not .mp3
        result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("output_filename must end with .mp3", result.tool_output)

    @patch("pathlib.Path.mkdir")
    def test_run_impl_api_error(self, mock_mkdir):
        self.mock_openai_client_instance.chat.completions.create.side_effect = APIError(
            message="TTS API Error", request=MagicMock(), body=None
        )
        tool_input = {"text": "test", "output_filename": "error.mp3"}
        result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("OpenAI API Error", result.tool_output)

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg not found"))
    @patch("os.remove")
    def test_run_impl_ffmpeg_not_found(self, mock_os_remove, mock_subprocess_run, mock_file_open, mock_mkdir):
        # Mock LLM call to return some audio data
        mock_completion_choice = MagicMock()
        mock_completion_choice.message.audio.data = base64.b64encode(b"fake_wav_data").decode('utf-8')
        mock_completion_response = MagicMock()
        mock_completion_response.choices = [mock_completion_choice]
        self.mock_openai_client_instance.chat.completions.create.return_value = mock_completion_response

        tool_input = {"text": "test", "output_filename": "ffmpeg_fail.mp3"}
        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("ffmpeg command not found", result.tool_output)
        mock_os_remove.assert_called() # Temp WAV should still be cleaned up

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="ffmpeg error text")) # ffmpeg fails
    @patch("os.remove")
    def test_run_impl_ffmpeg_conversion_fails(self, mock_os_remove, mock_subprocess_run, mock_file_open, mock_mkdir):
        mock_completion_choice = MagicMock()
        mock_completion_choice.message.audio.data = base64.b64encode(b"fake_wav_data").decode('utf-8')
        mock_completion_response = MagicMock()
        mock_completion_response.choices = [mock_completion_choice]
        self.mock_openai_client_instance.chat.completions.create.return_value = mock_completion_response

        tool_input = {"text": "test", "output_filename": "ffmpeg_fail.mp3"}
        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Error converting audio to MP3 using ffmpeg", result.tool_output)
        mock_os_remove.assert_called()

    @patch('subprocess.run', side_effect=FileNotFoundError) # To test _check_ffmpeg
    def test_check_ffmpeg_warning(self, mock_sp_run):
        # This tests the warning printed during __init__ if ffmpeg is not found
        with patch('builtins.print') as mock_print:
            # Need to stop the class-level patch of _check_ffmpeg for this one test
            self.ffmpeg_check_patcher.stop()
            try:
                AudioGenerateTool(workspace_manager=self.mock_workspace_manager)
                # Check if print was called with the warning message
                ffmpeg_warning_found = False
                for call_args in mock_print.call_args_list:
                    if "ffmpeg` command not found" in call_args[0][0]:
                        ffmpeg_warning_found = True
                        break
                self.assertTrue(ffmpeg_warning_found)
            finally:
                 # Restart the patcher so other tests don't run actual _check_ffmpeg
                self.ffmpeg_check_patcher.start()


if __name__ == "__main__":
    unittest.main()
