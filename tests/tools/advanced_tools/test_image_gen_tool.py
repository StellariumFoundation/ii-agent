import unittest
from unittest.mock import patch, MagicMock
import os
from pathlib import Path

# Import tool to be tested
from src.ii_agent.tools.advanced_tools.image_gen_tool import ImageGenerateTool
from src.ii_agent.utils import WorkspaceManager
from src.ii_agent.tools.base import ToolImplOutput

# Mock Vertex AI parts if not available or to control behavior
try:
    import vertexai
    from vertexai.preview.vision_models import ImageGenerationModel, Image as VertexImage
except ImportError:
    vertexai = MagicMock()
    ImageGenerationModel = MagicMock()
    VertexImage = MagicMock() # To mock the type of image objects returned by API


class TestImageGenerateTool(unittest.TestCase):
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_workspace_manager.workspace_path.side_effect = lambda p: Path("/fake/workspace") / p
        # Mock file_server_port for URL generation
        self.mock_workspace_manager.file_server_port = 8080

        self.env_vars = {
            "GOOGLE_CLOUD_PROJECT": "test-gcp-project",
            "GOOGLE_CLOUD_REGION": "us-central1"
        }

        # Patch vertexai.init and ImageGenerationModel.from_pretrained for most tests
        self.vertex_init_patcher = patch('vertexai.init')
        self.mock_vertex_init = self.vertex_init_patcher.start()

        self.image_model_patcher = patch('vertexai.preview.vision_models.ImageGenerationModel.from_pretrained')
        self.MockImageGenerationModelClass = self.image_model_patcher.start()

        self.mock_imagen_model_instance = MagicMock(spec=ImageGenerationModel)
        self.MockImageGenerationModelClass.return_value = self.mock_imagen_model_instance


    def tearDown(self):
        self.vertex_init_patcher.stop()
        self.image_model_patcher.stop()

    def _create_tool_with_env(self):
        with patch.dict(os.environ, self.env_vars, clear=True):
            tool = ImageGenerateTool(workspace_manager=self.mock_workspace_manager)
        return tool

    def test_init_success(self):
        with patch.dict(os.environ, self.env_vars, clear=True):
            tool = ImageGenerateTool(workspace_manager=self.mock_workspace_manager)
            self.mock_vertex_init.assert_called_once_with(project="test-gcp-project", location="us-central1")
            self.MockImageGenerationModelClass.assert_called_once_with("imagen-3.0-generate-002")
            self.assertIsNotNone(tool.model)

    def test_init_no_gcp_project_env(self):
        with patch.dict(os.environ, {"GOOGLE_CLOUD_REGION": "us-central1"}, clear=True): # GCP_PROJECT missing
            with self.assertRaisesRegex(ValueError, "GOOGLE_CLOUD_PROJECT environment variable not set."):
                ImageGenerateTool(workspace_manager=self.mock_workspace_manager)

    def test_init_vertex_init_fails(self):
        self.mock_vertex_init.side_effect = Exception("Vertex AI init failed")
        with patch.dict(os.environ, self.env_vars, clear=True), \
             patch('builtins.print') as mock_print: # Suppress print
            tool = ImageGenerateTool(workspace_manager=self.mock_workspace_manager)
            self.assertIsNone(tool.model) # Model should be None
            mock_print.assert_called_with("Error initializing Vertex AI or loading Imagen model: Vertex AI init failed")

    @patch("pathlib.Path.mkdir")
    def test_run_impl_success(self, mock_mkdir):
        tool = self._create_tool_with_env()
        tool_input = {
            "prompt": "A cat wearing a hat",
            "output_filename": "cat_hat.png"
        }

        mock_generated_image = MagicMock(spec=VertexImage) # from vertexai.preview.vision_models import Image
        self.mock_imagen_model_instance.generate_images.return_value = [mock_generated_image]

        result = tool.run_impl(tool_input)

        self.assertTrue(result.auxiliary_data["success"])
        self.assertIn("Successfully generated image", result.tool_output)
        self.assertEqual(result.auxiliary_data["output_path"], "cat_hat.png")

        self.mock_imagen_model_instance.generate_images.assert_called_once()
        call_kwargs = self.mock_imagen_model_instance.generate_images.call_args.kwargs
        self.assertEqual(call_kwargs["prompt"], "A cat wearing a hat")
        self.assertEqual(call_kwargs["number_of_images"], 1) # Default
        self.assertTrue(call_kwargs["add_watermark"]) # Default

        expected_save_path = str(self.mock_workspace_manager.workspace_path(Path("cat_hat.png")))
        mock_generated_image.save.assert_called_once_with(location=expected_save_path, include_generation_parameters=False)
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


    def test_run_impl_model_not_initialized(self):
        tool = self._create_tool_with_env()
        tool.model = None # Simulate init failure
        tool_input = {"prompt": "test", "output_filename": "test.png"}
        result = tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Imagen model could not be initialized", result.tool_output)

    def test_run_impl_invalid_output_filename_extension(self):
        tool = self._create_tool_with_env()
        tool_input = {"prompt": "test", "output_filename": "image.jpg"} # Not .png
        result = tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("output_filename must end with .png", result.tool_output)

    @patch("pathlib.Path.mkdir")
    def test_run_impl_seed_and_watermark_logic(self, mock_mkdir):
        tool = self._create_tool_with_env()
        tool_input = {
            "prompt": "A dog",
            "output_filename": "dog.png",
            "seed": 12345,
            "add_watermark": True # This should be overridden
        }
        self.mock_imagen_model_instance.generate_images.return_value = [MagicMock(spec=VertexImage)]

        with patch('builtins.print') as mock_print: # Suppress warning print
            tool.run_impl(tool_input)

        call_kwargs = self.mock_imagen_model_instance.generate_images.call_args.kwargs
        self.assertEqual(call_kwargs["seed"], 12345)
        self.assertFalse(call_kwargs["add_watermark"]) # Seed forces watermark to False
        mock_print.assert_any_call("Warning: 'seed' is provided, 'add_watermark' will be ignored (or set to False).")


    @patch("pathlib.Path.mkdir")
    def test_run_impl_api_returns_no_images(self, mock_mkdir):
        tool = self._create_tool_with_env()
        self.mock_imagen_model_instance.generate_images.return_value = [] # API returns empty list
        tool_input = {"prompt": "rare image", "output_filename": "rare.png"}
        result = tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("No images returned from API", result.tool_output)

    @patch("pathlib.Path.mkdir")
    def test_run_impl_image_save_fails_safety(self, mock_mkdir):
        tool = self._create_tool_with_env()
        mock_generated_image = MagicMock(spec=VertexImage)
        mock_generated_image.save.side_effect = Exception("Safety filter triggered during save")
        self.mock_imagen_model_instance.generate_images.return_value = [mock_generated_image]

        tool_input = {"prompt": "unsafe prompt", "output_filename": "unsafe.png"}
        result = tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Image generation failed due to safety restrictions", result.tool_output)

    @patch("pathlib.Path.mkdir")
    def test_run_impl_general_api_exception(self, mock_mkdir):
        tool = self._create_tool_with_env()
        self.mock_imagen_model_instance.generate_images.side_effect = Exception("Vertex API general error")
        tool_input = {"prompt": "any prompt", "output_filename": "error.png"}
        result = tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Error generating image from text: Vertex API general error", result.tool_output)


if __name__ == "__main__":
    unittest.main()
