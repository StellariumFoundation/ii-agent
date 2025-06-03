import unittest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

from src.ii_agent.tools.list_html_links_tool import ListHtmlLinksTool
from src.ii_agent.utils import WorkspaceManager # Assuming this is the correct import
from src.ii_agent.tools.base import ToolImplOutput


class TestListHtmlLinksTool(unittest.TestCase):
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        # Configure workspace_path to return a Path object based on input
        self.mock_workspace_manager.workspace_path.side_effect = lambda p: Path("/fake/workspace") / p

        self.tool = ListHtmlLinksTool(workspace_manager=self.mock_workspace_manager)

    # Tests for _extract_links_from_file (though it's private, its logic is core)
    # We'll test it indirectly via run_impl by mocking file system interactions

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.read_text")
    def test_run_impl_single_html_file_with_links(self, mock_read_text, mock_is_file, mock_exists):
        mock_exists.return_value = True
        mock_is_file.return_value = True

        html_content = """
        <html><body>
            <a href="page1.html">Page 1</a>
            <a href="page2.html">Page 2</a>
            <a href="http://example.com/abs.html">Absolute Link</a>
            <a href="#section">Anchor Link</a>
            <a href="another/page3.html">Nested Page 3</a>
            <a href="no_ext_route">No Extension Route</a>
            <a href="image.jpg">Image Link</a>
        </body></html>
        """
        mock_read_text.return_value = html_content

        # Mock the Path object for the specific file being processed
        # The tool uses ws_path.suffix, so the path passed to workspace_path needs a suffix
        file_to_scan = Path("index.html")
        self.mock_workspace_manager.workspace_path.return_value = Path("/fake/workspace/index.html")


        result = self.tool.run_impl({"path": str(file_to_scan)})

        self.assertTrue(result.metadata["success"])
        self.assertIn("page1.html", result.metadata["linked_files"])
        self.assertIn("page2.html", result.metadata["linked_files"])
        self.assertIn("page3.html", result.metadata["linked_files"]) # Only filename
        self.assertIn("no_ext_route", result.metadata["linked_files"])
        self.assertNotIn("abs.html", result.metadata["linked_files"])
        self.assertNotIn("image.jpg", result.metadata["linked_files"])
        self.assertIn("Found the following unique local HTML file names", result.output_for_llm)
        mock_read_text.assert_called_once()


    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.read_text")
    def test_run_impl_single_html_file_no_links(self, mock_read_text, mock_is_file, mock_exists):
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_read_text.return_value = "<html><body><p>No links here.</p></body></html>"

        file_to_scan = Path("test.html")
        self.mock_workspace_manager.workspace_path.return_value = Path("/fake/workspace/test.html")

        result = self.tool.run_impl({"path": str(file_to_scan)})
        self.assertTrue(result.metadata["success"])
        self.assertEqual(result.metadata["linked_files"], [])
        self.assertIn("No local HTML links found", result.output_for_llm)

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_file")
    def test_run_impl_path_not_html_file(self, mock_is_file, mock_exists):
        mock_exists.return_value = True
        mock_is_file.return_value = True # It's a file

        # Important: Configure the path object that ws_path itself returns
        non_html_file_path = Path("/fake/workspace/document.txt")
        self.mock_workspace_manager.workspace_path.return_value = non_html_file_path

        result = self.tool.run_impl({"path": "document.txt"}) # Input path string

        self.assertFalse(result.metadata["success"])
        self.assertIn("is not an HTML file", result.output_for_llm)

    @patch("pathlib.Path.exists")
    def test_run_impl_path_not_found(self, mock_exists):
        mock_exists.return_value = False
        self.mock_workspace_manager.workspace_path.return_value = Path("/fake/workspace/nonexistent.html")

        result = self.tool.run_impl({"path": "nonexistent.html"})
        self.assertFalse(result.metadata["success"])
        self.assertIn("Path not found", result.output_for_llm)

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.rglob")
    @patch("pathlib.Path.read_text") # Mock read_text for files found by rglob
    def test_run_impl_directory_scan(self, mock_read_text, mock_rglob, mock_is_dir, mock_is_file, mock_exists):
        mock_exists.return_value = True
        mock_is_file.return_value = False # The main path is a directory
        mock_is_dir.return_value = True

        # Define the structure and content rglob will find
        # Path objects need to be comparable for this to work smoothly in sets.
        # The path passed to workspace_manager.workspace_path is "my_dir"
        # So, ws_path will be /fake/workspace/my_dir

        # Configure workspace_path for the directory itself
        dir_path_obj = Path("/fake/workspace/my_dir")
        self.mock_workspace_manager.workspace_path.return_value = dir_path_obj

        # Mock what rglob finds
        file1_path = dir_path_obj / "file1.html"
        file2_path = dir_path_obj / "sub" / "file2.html"

        # Ensure these paths are seen as files by the loop inside run_impl
        # We need a side_effect for is_file if it's called on these items
        def is_file_side_effect(path_arg):
            if path_arg == file1_path or path_arg == file2_path:
                return True
            return False # Default for the main dir_path_obj

        # We also need exists to be true for these files.
        def exists_side_effect(path_arg):
            if path_arg == dir_path_obj or path_arg == file1_path or path_arg == file2_path:
                return True
            return False

        # Re-patch is_file and exists for this more complex scenario
        # These are patched at the class level (pathlib.Path), so they affect all Path instances
        mock_is_file_repatch = patch("pathlib.Path.is_file", side_effect=is_file_side_effect)
        mock_exists_repatch = patch("pathlib.Path.exists", side_effect=exists_side_effect)

        # We need to start these patches here
        active_mock_is_file = mock_is_file_repatch.start()
        active_mock_exists = mock_exists_repatch.start()


        mock_rglob.return_value = [file1_path, file2_path]

        # Mock read_text for each file
        def read_text_side_effect(errors="ignore"): # Parameter name must match
            # The 'self' for read_text will be the Path instance it's called on
            if self == file1_path:
                return '<a href="link1.html"></a> <a href="../link_outside_sub.html"></a>'
            elif self == file2_path:
                return '<a href="link2.html"></a> <a href="link1.html"></a>' # Duplicate link name
            return ""

        # Patch read_text on the Path class instance method
        mock_read_text_method_patch = patch.object(Path, 'read_text', side_effect=read_text_side_effect)
        active_mock_read_text = mock_read_text_method_patch.start()

        result = self.tool.run_impl({"path": "my_dir"})

        self.assertTrue(result.metadata["success"])
        expected_links = sorted(["link1.html", "link2.html", "link_outside_sub.html"])
        self.assertEqual(sorted(list(result.metadata["linked_files"])), expected_links)
        self.assertIn("Found the following unique local HTML file names", result.output_for_llm)

        # Stop the manually started patches
        mock_is_file_repatch.stop()
        mock_exists_repatch.stop()
        mock_read_text_method_patch.stop()

        # Restore original mocks for other tests if any by stopping them
        # This is tricky because the original setUp mocks are class-level.
        # Better to ensure each test fully manages its specific mocks for Path methods.
        # For now, assume this is the last complex test or that default mocks handle simpler cases.


    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.is_dir")
    def test_run_impl_path_is_not_file_or_dir(self, mock_is_dir, mock_is_file, mock_exists):
        mock_exists.return_value = True
        mock_is_file.return_value = False
        mock_is_dir.return_value = False # It's something else (e.g. symlink, fifo - though unlikely in ws)

        self.mock_workspace_manager.workspace_path.return_value = Path("/fake/workspace/special_thing")

        result = self.tool.run_impl({"path": "special_thing"})
        self.assertFalse(result.metadata["success"])
        self.assertIn("Path is neither a file nor a directory", result.output_for_llm)


if __name__ == "__main__":
    unittest.main()
