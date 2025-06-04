import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import time # For mocking time.sleep
import uuid # For mocking uuid.uuid4
from pathlib import Path

# Import tools and helpers to be tested/mocked
from src.ii_agent.tools.advanced_tools.video_gen_tool import (
    VideoGenerateFromTextTool,
    VideoGenerateFromImageTool,
    download_gcs_file, # For standalone testing if desired, or via tool
    upload_to_gcs,
    delete_gcs_blob,
    _get_gcs_client # To patch this helper
)
from src.ii_agent.utils import WorkspaceManager
from src.ii_agent.tools.base import ToolImplOutput

# Mock Google Cloud clients if not available or to control behavior
try:
    from google import genai
    from google.genai import types as genai_types
    from google.cloud import storage
    from google.auth.exceptions import DefaultCredentialsError
except ImportError:
    genai = MagicMock()
    genai_types = MagicMock()
    storage = MagicMock()
    DefaultCredentialsError = Exception # So it can be caught

# --- Start of GCS Helper Function Tests (Optional, but good practice) ---
class TestGCSHelpers(unittest.TestCase):
    @patch('src.ii_agent.tools.advanced_tools.video_gen_tool.storage.Client')
    def test_get_gcs_client_success(self, MockStorageClient):
        mock_client_instance = MockStorageClient.return_value
        client = _get_gcs_client()
        self.assertIs(client, mock_client_instance)
        MockStorageClient.assert_called_once()

    @patch('src.ii_agent.tools.advanced_tools.video_gen_tool.storage.Client', side_effect=DefaultCredentialsError("No creds"))
    def test_get_gcs_client_auth_error(self, MockStorageClient):
        with self.assertRaises(DefaultCredentialsError), patch('builtins.print') as mock_print:
            _get_gcs_client()
        mock_print.assert_any_call(unittest.mock.ANY) # Check if error was printed

    # TODO: Add tests for download_gcs_file, upload_to_gcs, delete_gcs_blob
    # These would involve mocking storage.Client, bucket, blob, and their methods.
    # For brevity in this combined response, focusing on the main tools first.

# --- End of GCS Helper Function Tests ---


class CommonVideoGenToolTests(unittest.TestCase):
    """Common setup for VideoGen tools."""
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_workspace_manager.workspace_path.side_effect = lambda p: Path("/fake/workspace") / p
        self.mock_workspace_manager.file_server_port = 8080 # For URL generation

        self.env_vars = {
            "GOOGLE_CLOUD_PROJECT": "test-gcp-project",
            "GOOGLE_CLOUD_REGION": "us-central1",
            "VEO_GCS_OUTPUT_BUCKET": "gs://fake-veo-bucket"
        }

        self.env_patcher = patch.dict(os.environ, self.env_vars, clear=True)
        self.env_patcher.start()

        # Patch genai.Client (used by Veo model)
        self.genai_client_patcher = patch('google.genai.Client')
        self.MockGenaiClientConstructor = self.genai_client_patcher.start()
        self.mock_veo_client_instance = MagicMock(spec=genai.Client)
        self.MockGenaiClientConstructor.return_value = self.mock_veo_client_instance

        # Mock methods on the Veo client instance
        self.mock_generate_videos_method = MagicMock()
        self.mock_operations_get_method = MagicMock()
        self.mock_veo_client_instance.models.generate_videos = self.mock_generate_videos_method
        self.mock_veo_client_instance.operations.get = self.mock_operations_get_method

        # Patch GCS interactions (used by helper functions called by tools)
        self.gcs_client_patcher = patch('src.ii_agent.tools.advanced_tools.video_gen_tool._get_gcs_client')
        self.mock_get_gcs_client_func = self.gcs_client_patcher.start()
        self.mock_gcs_client_instance = MagicMock(spec=storage.Client)
        self.mock_get_gcs_client_func.return_value = self.mock_gcs_client_instance

        # Mock specific GCS blob operations often chained: client.bucket().blob().method()
        self.mock_gcs_blob = MagicMock(spec=storage.Blob)
        mock_gcs_bucket = MagicMock(spec=storage.Bucket)
        mock_gcs_bucket.blob.return_value = self.mock_gcs_blob
        self.mock_gcs_client_instance.bucket.return_value = mock_gcs_bucket

        # Mock time.sleep and uuid.uuid4
        self.sleep_patcher = patch('time.sleep', return_value=None) # Speed up polling
        self.mock_sleep = self.sleep_patcher.start()

        self.uuid_patcher = patch('uuid.uuid4')
        self.mock_uuid4 = self.uuid_patcher.start()
        self.mock_uuid4.return_value = MagicMock(hex="testuuid1234")


    def tearDown(self):
        self.env_patcher.stop()
        self.genai_client_patcher.stop()
        self.gcs_client_patcher.stop()
        self.sleep_patcher.stop()
        self.uuid_patcher.stop()


class TestVideoGenerateFromTextTool(CommonVideoGenToolTests):
    def setUp(self):
        super().setUp()
        self.tool = VideoGenerateFromTextTool(workspace_manager=self.mock_workspace_manager)

    @patch("pathlib.Path.mkdir")
    def test_run_impl_success(self, mock_path_mkdir):
        tool_input = {
            "prompt": "A beautiful sunset",
            "output_filename": "sunset.mp4",
            "duration_seconds": "5" # String, as per schema, converted to int in tool
        }

        # Mock Veo operation sequence
        mock_initial_op = MagicMock()
        mock_initial_op.done = False
        self.mock_generate_videos_method.return_value = mock_initial_op

        mock_final_op = MagicMock()
        mock_final_op.done = True
        mock_final_op.error = None
        # Simulate response structure
        mock_video_data = MagicMock()
        mock_video_data.uri = "gs://fake-veo-bucket/testuuid1234_actual_output.mp4"
        mock_generated_video = MagicMock()
        mock_generated_video.video = mock_video_data
        mock_op_result = MagicMock()
        mock_op_result.generated_videos = [mock_generated_video]
        mock_final_op.result = mock_op_result
        self.mock_operations_get_method.return_value = mock_final_op

        # Mock GCS download and delete (which are patched at module level for helpers)
        with patch('src.ii_agent.tools.advanced_tools.video_gen_tool.download_gcs_file', return_value=None) as mock_download, \
             patch('src.ii_agent.tools.advanced_tools.video_gen_tool.delete_gcs_blob', return_value=None) as mock_delete:

            result = self.tool.run_impl(tool_input)

        self.assertTrue(result.auxiliary_data["success"], msg=result.tool_output)
        self.assertIn("Successfully generated video", result.tool_output)
        self.assertEqual(result.auxiliary_data["output_path"], "sunset.mp4")

        self.mock_generate_videos_method.assert_called_once()
        call_kwargs = self.mock_generate_videos_method.call_args.kwargs
        self.assertEqual(call_kwargs["prompt"], "A beautiful sunset")
        self.assertEqual(call_kwargs["config"].duration_seconds, 5)
        self.assertEqual(call_kwargs["config"].output_gcs_uri, "gs://fake-veo-bucket/veo_temp_output_testuuid1234.mp4")

        mock_download.assert_called_once_with(
            "gs://fake-veo-bucket/testuuid1234_actual_output.mp4",
            Path("/fake/workspace/sunset.mp4")
        )
        mock_delete.assert_called_once_with("gs://fake-veo-bucket/testuuid1234_actual_output.mp4")

    def test_run_impl_invalid_output_filename(self):
        tool_input = {"prompt": "test", "output_filename": "video.mkv"} # Not .mp4
        result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("output_filename must end with .mp4", result.tool_output)

    @patch('time.sleep', return_value=None) # Ensure sleep is also patched here if setUp's doesn't cover it
    def test_run_impl_timeout(self, mock_sleep_override):
        self.tool.max_wait_time_seconds = 10 # Short timeout for test
        self.tool.polling_interval_seconds = 3

        mock_op = MagicMock()
        mock_op.done = False # Always not done
        self.mock_generate_videos_method.return_value = mock_op
        self.mock_operations_get_method.return_value = mock_op # Refresh also returns not done

        tool_input = {"prompt": "long video", "output_filename": "timeout.mp4"}
        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Video generation timed out", result.tool_output)
        # Check sleep was called multiple times due to polling
        self.assertTrue(self.mock_sleep.call_count > 1) # Access the one from setUp

    # TODO: Add tests for API error during generation, API error during polling, no video in response


class TestVideoGenerateFromImageTool(CommonVideoGenToolTests):
    def setUp(self):
        super().setUp()
        # Patch Path.exists and Path.is_file for the input image check
        self.path_exists_patcher = patch('pathlib.Path.exists', return_value=True)
        self.path_is_file_patcher = patch('pathlib.Path.is_file', return_value=True)
        self.mock_path_exists = self.path_exists_patcher.start()
        self.mock_path_is_file = self.path_is_file_patcher.start()

        self.tool = VideoGenerateFromImageTool(workspace_manager=self.mock_workspace_manager)

    def tearDown(self):
        super().tearDown()
        self.path_exists_patcher.stop()
        self.path_is_file_patcher.stop()

    @patch("pathlib.Path.mkdir")
    # Patch the GCS helper functions directly as they are module-level
    @patch('src.ii_agent.tools.advanced_tools.video_gen_tool.upload_to_gcs', return_value=None)
    @patch('src.ii_agent.tools.advanced_tools.video_gen_tool.download_gcs_file', return_value=None)
    @patch('src.ii_agent.tools.advanced_tools.video_gen_tool.delete_gcs_blob', return_value=None)
    def test_run_impl_success(self, mock_delete_gcs, mock_download_gcs, mock_upload_gcs, mock_path_mkdir):
        tool_input = {
            "image_file_path": "input_images/source.png", # Supported format
            "output_filename": "animated_output.mp4",
            "prompt": "Make it zoom out"
        }

        # Mock Veo operation sequence (similar to text tool)
        mock_initial_op = MagicMock(); mock_initial_op.done = False
        self.mock_generate_videos_method.return_value = mock_initial_op
        mock_final_op = MagicMock(); mock_final_op.done = True; mock_final_op.error = None
        mock_video_data = MagicMock(); mock_video_data.uri = "gs://fake-veo-bucket/output_from_image.mp4"
        mock_generated_video = MagicMock(); mock_generated_video.video = mock_video_data
        mock_op_result = MagicMock(); mock_op_result.generated_videos = [mock_generated_video]
        mock_final_op.result = mock_op_result
        self.mock_operations_get_method.return_value = mock_final_op

        result = self.tool.run_impl(tool_input)

        self.assertTrue(result.auxiliary_data["success"], msg=result.tool_output)
        self.assertIn("Successfully generated video from image", result.tool_output)

        expected_local_input_path = Path("/fake/workspace/input_images/source.png")
        expected_temp_gcs_image_uri = "gs://fake-veo-bucket/veo_temp_input_testuuid1234.png"
        mock_upload_gcs.assert_called_once_with(expected_local_input_path, expected_temp_gcs_image_uri)

        self.mock_generate_videos_method.assert_called_once()
        call_kwargs = self.mock_generate_videos_method.call_args.kwargs
        self.assertEqual(call_kwargs["prompt"], "Make it zoom out")
        self.assertEqual(call_kwargs["image"].gcs_uri, expected_temp_gcs_image_uri)
        self.assertEqual(call_kwargs["image"].mime_type, "image/png")

        mock_download_gcs.assert_called_once_with(
            "gs://fake-veo-bucket/output_from_image.mp4",
            Path("/fake/workspace/animated_output.mp4")
        )
        # Check cleanup calls
        self.assertIn(unittest.mock.call(expected_temp_gcs_image_uri), mock_delete_gcs.call_args_list)
        self.assertIn(unittest.mock.call("gs://fake-veo-bucket/output_from_image.mp4"), mock_delete_gcs.call_args_list)


    def test_run_impl_input_image_not_found(self):
        self.mock_path_exists.return_value = False # Input image does not exist
        tool_input = {"image_file_path": "nonexistent.jpg", "output_filename": "video.mp4"}
        result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Input image file not found", result.tool_output)

    def test_run_impl_input_image_unsupported_format(self):
        tool_input = {"image_file_path": "image.gif", "output_filename": "video.mp4"} # .gif not in SUPPORTED_IMAGE_FORMATS_MIMETYPE
        result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Input image format .gif is not supported", result.tool_output)

    # TODO: Add tests for GCS upload/download/delete failures, API errors, timeout for image tool

if __name__ == "__main__":
    unittest.main()
