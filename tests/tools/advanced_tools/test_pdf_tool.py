import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import tool to be tested
from src.ii_agent.tools.advanced_tools.pdf_tool import PdfTextExtractTool
from src.ii_agent.utils import WorkspaceManager
from src.ii_agent.tools.base import ToolImplOutput

# Mock pymupdf if not available or to control behavior
try:
    import pymupdf
except ImportError:
    pymupdf = MagicMock()


class TestPdfTextExtractTool(unittest.TestCase):
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_workspace_manager.workspace_path.side_effect = lambda p: Path("/fake/workspace") / p

        self.tool = PdfTextExtractTool(workspace_manager=self.mock_workspace_manager, max_output_length=100)

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.is_file", return_value=True)
    @patch("pymupdf.open") # Patch where pymupdf.open is used
    def test_run_impl_success_extraction(self, mock_pymupdf_open, mock_is_file, mock_exists):
        file_path_str = "document.pdf"
        tool_input = {"file_path": file_path_str}

        # Configure mock document and pages
        mock_doc = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Text from page 1. "
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = "Text from page 2."

        # Make the mock document iterable for len() and page loading
        mock_doc.__len__.return_value = 2 # Number of pages
        mock_doc.load_page.side_effect = [mock_page1, mock_page2]

        mock_pymupdf_open.return_value = mock_doc

        result = self.tool.run_impl(tool_input)

        full_path = self.mock_workspace_manager.workspace_path(Path(file_path_str))
        mock_pymupdf_open.assert_called_once_with(full_path)
        mock_doc.load_page.assert_any_call(0)
        mock_doc.load_page.assert_any_call(1)
        mock_page1.get_text.assert_called_once_with("text")
        mock_page2.get_text.assert_called_once_with("text")
        mock_doc.close.assert_called_once()

        self.assertIsInstance(result, ToolImplOutput)
        expected_text = "Text from page 1. Text from page 2."
        self.assertEqual(result.tool_output, expected_text)
        self.assertTrue(result.auxiliary_data["success"])
        self.assertEqual(result.auxiliary_data["extracted_chars"], len(expected_text))

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.is_file", return_value=True)
    @patch("pymupdf.open")
    def test_run_impl_text_truncation(self, mock_pymupdf_open, mock_is_file, mock_exists):
        file_path_str = "long_doc.pdf"
        tool_input = {"file_path": file_path_str}

        long_text_part1 = "a" * 60
        long_text_part2 = "b" * 60 # Total 120, max_output_length is 100

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = long_text_part1 + long_text_part2
        mock_doc.__len__.return_value = 1
        mock_doc.load_page.return_value = mock_page
        mock_pymupdf_open.return_value = mock_doc

        result = self.tool.run_impl(tool_input)

        self.assertTrue(result.auxiliary_data["success"])
        self.assertTrue(len(result.tool_output) < 120) # Ensure truncated
        self.assertIn("... (content truncated due to length)", result.tool_output)
        # Exact truncation logic: text[:max_len] + message
        # Max length is 100.
        # Expected: (long_text_part1+long_text_part2)[:100] + "\n... (content truncated due to length)"
        # This is not quite right, the tool truncates as text[:max_output_length] + suffix
        # The test should reflect the tool's actual truncation logic.
        # The tool code is: text[: self.max_output_length] + "\n... (content truncated due to length)"
        # So, it takes the first max_output_length characters.

        original_full_text = long_text_part1 + long_text_part2
        expected_truncated_text = original_full_text[:self.tool.max_output_length] + "\n... (content truncated due to length)"
        self.assertEqual(result.tool_output, expected_truncated_text)


    def test_run_impl_file_not_found(self):
        with patch("pathlib.Path.exists", return_value=False):
            tool_input = {"file_path": "absent.pdf"}
            result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("File not found", result.tool_output)

    def test_run_impl_path_not_a_file(self):
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=False):
            tool_input = {"file_path": "folder.pdf"} # Name suggests PDF but it's a folder
            result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("is not a file", result.tool_output)

    def test_run_impl_not_a_pdf_file(self):
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=True):
            # workspace_path will create /fake/workspace/document.txt
            # Path(document.txt).suffix will be .txt
            tool_input = {"file_path": "document.txt"}
            result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("is not a PDF", result.tool_output)

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.is_file", return_value=True)
    @patch("pymupdf.open", side_effect=Exception("pymupdf error opening file"))
    def test_run_impl_pymupdf_open_error(self, mock_pymupdf_open, mock_is_file, mock_exists):
        tool_input = {"file_path": "corrupted.pdf"}
        result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Error extracting text from PDF", result.tool_output)
        self.assertIn("pymupdf error opening file", result.tool_output)

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.is_file", return_value=True)
    @patch("pymupdf.open")
    def test_run_impl_page_get_text_error(self, mock_pymupdf_open, mock_is_file, mock_exists):
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.side_effect = Exception("pymupdf page error")
        mock_doc.__len__.return_value = 1
        mock_doc.load_page.return_value = mock_page
        mock_pymupdf_open.return_value = mock_doc

        tool_input = {"file_path": "page_error.pdf"}
        result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Error extracting text from PDF", result.tool_output)
        self.assertIn("pymupdf page error", result.tool_output)


if __name__ == "__main__":
    unittest.main()
