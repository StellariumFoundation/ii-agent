import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.ii_agent.tools.text_inspector_tool import TextInspectorTool
from src.ii_agent.utils import WorkspaceManager
from src.ii_agent.tools.base import ToolImplOutput
from src.ii_agent.tools.markdown_converter import DocumentConverterResult, MarkdownConverter # For mocking convert's return type

class TestTextInspectorTool(unittest.TestCase):
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_workspace_manager.workspace_path.side_effect = lambda p: Path("/fake/workspace") / p

        self.tool = TextInspectorTool(workspace_manager=self.mock_workspace_manager, text_limit=1000)

        # Mock the MarkdownConverter instance within the tool
        self.mock_md_converter_instance = MagicMock(spec=MarkdownConverter)
        self.tool.md_converter = self.mock_md_converter_instance


    def test_forward_successful_extraction(self):
        file_path = "document.docx"
        expected_text_content = "This is the content of the docx."
        mock_doc_result = DocumentConverterResult(text_content=expected_text_content)
        self.mock_md_converter_instance.convert.return_value = mock_doc_result

        result_text = self.tool.forward(file_path)

        self.assertEqual(result_text, expected_text_content)
        abs_path_str = str(Path("/fake/workspace") / file_path)
        self.mock_md_converter_instance.convert.assert_called_once_with(abs_path_str)

    def test_forward_zip_file(self):
        file_path = "archive.zip"
        expected_zip_listing = "File1.txt\nFile2.jpg"
        mock_doc_result = DocumentConverterResult(text_content=expected_zip_listing)
        self.mock_md_converter_instance.convert.return_value = mock_doc_result

        result_text = self.tool.forward(file_path)
        self.assertEqual(result_text, expected_zip_listing)

    def test_forward_image_file_raises_exception(self):
        with self.assertRaisesRegex(Exception, "Cannot use this tool with images: use display_image instead!"):
            self.tool.forward("image.png")

        with self.assertRaisesRegex(Exception, "Cannot use this tool with images: use display_image instead!"):
            self.tool.forward("photo.jpg")

        self.mock_md_converter_instance.convert.assert_not_called() # convert should not be called for images by forward

    def test_run_impl_success(self):
        file_path = "report.pdf"
        extracted_content = "PDF content here."

        # Mock the forward method directly for this test of run_impl's logic
        with patch.object(self.tool, 'forward', return_value=extracted_content) as mock_forward_method:
            tool_input = {"file_path": file_path}
            result = self.tool.run_impl(tool_input)

            mock_forward_method.assert_called_once_with(file_path)
            self.assertIsInstance(result, ToolImplOutput)
            self.assertEqual(result.tool_output, extracted_content)
            self.assertEqual(result.tool_result_message, f"Successfully inspected file {file_path}")
            self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_forward_raises_exception(self):
        file_path = "error_file.docx"
        error_message = "Failed to convert document."

        with patch.object(self.tool, 'forward', side_effect=Exception(error_message)) as mock_forward_method:
            tool_input = {"file_path": file_path}
            result = self.tool.run_impl(tool_input)

            mock_forward_method.assert_called_once_with(file_path)
            self.assertIsInstance(result, ToolImplOutput)
            self.assertEqual(result.tool_output, f"Error inspecting file: {error_message}")
            self.assertEqual(result.tool_result_message, f"Failed to inspect file {file_path}")
            self.assertFalse(result.auxiliary_data["success"])

    def test_run_impl_missing_filepath_input(self):
        # This case should ideally be caught by schema validation in LLMTool.execute
        # before run_impl is called. If called directly, it would raise a KeyError.
        with self.assertRaises(KeyError):
            self.tool.run_impl({})


if __name__ == "__main__":
    unittest.main()
