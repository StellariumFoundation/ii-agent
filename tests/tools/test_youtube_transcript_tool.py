import unittest
from unittest.mock import patch, MagicMock, mock_open

from src.ii_agent.tools.youtube_transcript_tool import YoutubeTranscriptTool
from src.ii_agent.tools.base import ToolImplOutput
import json # For creating mock JSON responses
import requests # Added to fix NameError

# Mock yt_dlp if it's not available or to control its behavior
try:
    import yt_dlp
except ImportError:
    yt_dlp = MagicMock()


class TestYoutubeTranscriptTool(unittest.TestCase):
    def setUp(self):
        self.tool = YoutubeTranscriptTool()

    @patch('requests.get')
    @patch('yt_dlp.YoutubeDL') # Patch where YoutubeDL is imported/used
    def test_run_impl_success_manual_subtitles(self, mock_youtube_dl_constructor, mock_requests_get):
        mock_ydl_instance = MagicMock()
        mock_youtube_dl_constructor.return_value.__enter__.return_value = mock_ydl_instance # For context manager

        video_url = "https://www.youtube.com/watch?v=testvideo"
        subtitle_url = "http://example.com/subtitle.json"

        mock_info = {
            "subtitles": {
                "en": [{"url": subtitle_url, "ext": "json"}] # Assuming JSON format based on code
            },
            "automatic_captions": {}
        }
        mock_ydl_instance.extract_info.return_value = mock_info

        mock_subtitle_response = MagicMock()
        mock_subtitle_response.json.return_value = {
            "events": [
                {"segs": [{"utf8": "Hello "}, {"utf8": "world."}]},
                {"segs": [{"utf8": " This is "}, {"utf8": "a test."}]}
            ]
        }
        mock_requests_get.return_value = mock_subtitle_response

        tool_input = {"url": video_url}
        result = self.tool.run_impl(tool_input)

        mock_youtube_dl_constructor.assert_called_once_with({
            "quiet": True, "no_warnings": True, "writesubtitles": True,
            "writeautomaticsub": True, "skip_download": True,
        })
        mock_ydl_instance.extract_info.assert_called_once_with(video_url, download=False)
        mock_requests_get.assert_called_once_with(subtitle_url)
        mock_subtitle_response.raise_for_status.assert_called_once()

        self.assertIsInstance(result, ToolImplOutput)
        expected_transcript = "Hello world. This is a test."
        self.assertEqual(result.tool_output, expected_transcript)
        self.assertEqual(result.tool_result_message, expected_transcript) # tool_result_message is same as tool_output

    @patch('requests.get')
    @patch('yt_dlp.YoutubeDL')
    def test_run_impl_success_auto_captions(self, mock_youtube_dl_constructor, mock_requests_get):
        mock_ydl_instance = MagicMock()
        mock_youtube_dl_constructor.return_value.__enter__.return_value = mock_ydl_instance
        video_url = "https://www.youtube.com/watch?v=autocap"
        caption_url = "http://example.com/caption.json"

        mock_info = {
            "subtitles": {}, # No manual subtitles
            "automatic_captions": {
                "en": [{"url": caption_url, "ext": "json"}]
            }
        }
        mock_ydl_instance.extract_info.return_value = mock_info

        mock_caption_response = MagicMock()
        mock_caption_response.json.return_value = {"events": [{"segs": [{"utf8": "Auto caption."}]}]}
        mock_requests_get.return_value = mock_caption_response

        result = self.tool.run_impl({"url": video_url})

        self.assertEqual(result.tool_output, "Auto caption.")

    @patch('yt_dlp.YoutubeDL')
    def test_run_impl_no_english_subtitles(self, mock_youtube_dl_constructor):
        mock_ydl_instance = MagicMock()
        mock_youtube_dl_constructor.return_value.__enter__.return_value = mock_ydl_instance
        mock_info = {"subtitles": {"fr": [...]}, "automatic_captions": {"de": [...]}} # No 'en'
        mock_ydl_instance.extract_info.return_value = mock_info

        # The tool's run_impl returns a string message directly in this case, not ToolImplOutput
        result_str = self.tool.run_impl({"url": "http://youtube.com/no_en_subs"})
        self.assertEqual(result_str, "No subtitles available for the requested language.")


    @patch('yt_dlp.YoutubeDL')
    def test_run_impl_yt_dlp_exception(self, mock_youtube_dl_constructor):
        mock_ydl_instance = MagicMock()
        mock_youtube_dl_constructor.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_instance.extract_info.side_effect = Exception("yt_dlp failed")

        # The tool's run_impl catches all exceptions and returns ""
        with patch('builtins.print') as mock_print: # Suppress print
            result_str = self.tool.run_impl({"url": "http://youtube.com/fail"})
            self.assertEqual(result_str, "")
            mock_print.assert_called_with("Error fetching subtitles: yt_dlp failed")


    @patch('requests.get')
    @patch('yt_dlp.YoutubeDL')
    def test_run_impl_requests_exception(self, mock_youtube_dl_constructor, mock_requests_get):
        mock_ydl_instance = MagicMock()
        mock_youtube_dl_constructor.return_value.__enter__.return_value = mock_ydl_instance
        mock_info = {"subtitles": {"en": [{"url": "http://bad.url/sub.json"}]}, "automatic_captions": {}}
        mock_ydl_instance.extract_info.return_value = mock_info

        mock_requests_get.side_effect = requests.exceptions.RequestException("Network failed")

        with patch('builtins.print') as mock_print:
            result_str = self.tool.run_impl({"url": "http://youtube.com/net_fail"})
            self.assertEqual(result_str, "")
            mock_print.assert_called_with("Error fetching subtitles: Network failed")

    @patch('requests.get')
    @patch('yt_dlp.YoutubeDL')
    def test_run_impl_malformed_subtitle_json(self, mock_youtube_dl_constructor, mock_requests_get):
        mock_ydl_instance = MagicMock()
        mock_youtube_dl_constructor.return_value.__enter__.return_value = mock_ydl_instance
        mock_info = {"subtitles": {"en": [{"url": "http://example.com/malformed.json"}]}, "automatic_captions": {}}
        mock_ydl_instance.extract_info.return_value = mock_info

        mock_subtitle_response = MagicMock()
        mock_subtitle_response.json.return_value = {"no_events_here": "..."} # Missing "events"
        mock_requests_get.return_value = mock_subtitle_response

        # This will likely raise a TypeError or KeyError when processing events, caught by the general Exception
        with patch('builtins.print') as mock_print:
            result_str = self.tool.run_impl({"url": "http://youtube.com/malformed"})
            self.assertEqual(result_str, "")
            # Check that print was called, the exact error message might vary
            self.assertTrue(mock_print.call_args[0][0].startswith("Error fetching subtitles:"))


if __name__ == "__main__":
    unittest.main()
