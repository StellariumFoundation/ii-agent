import unittest
from unittest.mock import MagicMock, patch, call
from pathlib import Path
import asyncio # For queue if needed

from src.ii_agent.tools.str_replace_tool_relative import StrReplaceEditorTool, ToolError, ExtendedToolImplOutput
from src.ii_agent.utils import WorkspaceManager
# from ii_agent.core.event import RealtimeEvent, EventType # If testing queue

# Helper to run async methods if needed, though most tool logic seems sync
def async_test(f):
    def wrapper(*args, **kwargs):
        return asyncio.get_event_loop().run_until_complete(f(*args, **kwargs))
    return wrapper

class TestStrReplaceEditorTool(unittest.TestCase):
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_workspace_manager.root = Path("/fake/workspace")
        self.mock_workspace_manager.workspace_path.side_effect = lambda p: Path("/fake/workspace") / Path(p)
        self.mock_workspace_manager.relative_path.side_effect = lambda p: Path(p).relative_to(Path("/fake/workspace"))

        self.mock_message_queue = MagicMock(spec=asyncio.Queue)

        # Default tool instance
        self.tool = StrReplaceEditorTool(
            workspace_manager=self.mock_workspace_manager,
            message_queue=self.mock_message_queue
        )
        # Tool instance for testing ignore_indentation
        self.tool_ignore_indent = StrReplaceEditorTool(
            workspace_manager=self.mock_workspace_manager,
            ignore_indentation_for_str_replace=True,
            message_queue=self.mock_message_queue
        )
        # Tool instance for testing expand_tabs
        self.tool_expand_tabs = StrReplaceEditorTool(
            workspace_manager=self.mock_workspace_manager,
            expand_tabs=True,
            message_queue=self.mock_message_queue
        )

    # --- Helper to mock file system ---
    def _setup_mock_file(self, path_obj: Path, content: str = "", exists: bool = True, is_file: bool = True, is_dir: bool = False):
        path_obj.exists.return_value = exists
        path_obj.is_file.return_value = is_file
        path_obj.is_dir.return_value = is_dir
        if exists and is_file:
            path_obj.read_text.return_value = content
            # path_obj.write_text = MagicMock() # Will be set per test if needed to check content

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    def test_str_replace_verbatim_success(self, mock_exists, mock_is_file, mock_is_dir, mock_read_text, mock_write_text):
        file_path_str = "test_file.txt"
        file_path_obj = self.mock_workspace_manager.workspace_path(file_path_str)

        original_content = "Hello world\nThis is a test\nHello again world"
        self._setup_mock_file(file_path_obj, original_content)
        # For methods on Path instances that are dynamically created (like in loops or returned by other mocks)
        # we need to ensure they also have these mocks if they are called.
        # Here, workspace_path returns a new Path object, so we mock its methods directly after creation.
        # This is simpler if workspace_path always returns the *same* mock Path object for the same input string.
        # Our current side_effect for workspace_path creates new Path objects.
        # So, we need to ensure that the specific Path instance `_ws_path` inside `run_impl` gets these mocks.
        # The easiest way is to patch `Path` globally for these methods for the duration of the test,
        # or ensure that `workspace_path` returns a pre-configured mock Path object.

        # Let's re-mock workspace_path to return a specific mock for this test
        specific_mock_path = MagicMock(spec=Path)
        specific_mock_path.name = file_path_str # for relative_path
        specific_mock_path.parent = self.mock_workspace_manager.root
        specific_mock_path.resolve.return_value = self.mock_workspace_manager.root / file_path_str # for is_path_in_directory
        self.mock_workspace_manager.workspace_path.return_value = specific_mock_path
        self._setup_mock_file(specific_mock_path, original_content)


        tool_input = {
            "command": "str_replace",
            "path": file_path_str,
            "old_str": "This is a test",
            "new_str": "This was a test"
        }
        result = self.tool.run_impl(tool_input)

        self.assertTrue(result.success)
        self.assertIn(f"The file {file_path_str} has been edited.", result.tool_output)
        expected_new_content = "Hello world\nThis was a test\nHello again world"
        specific_mock_path.write_text.assert_called_once_with(expected_new_content)
        self.assertEqual(len(self.tool._file_history[specific_mock_path]), 1)
        self.assertEqual(self.tool._file_history[specific_mock_path][0], original_content)
        self.mock_message_queue.put_nowait.assert_called() # Check if event was sent

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    def test_str_replace_verbatim_old_str_not_found(self, mock_exists, mock_is_file, mock_is_dir, mock_read_text):
        file_path_str = "test_file.txt"
        specific_mock_path = MagicMock(spec=Path); specific_mock_path.name = file_path_str; specific_mock_path.parent = self.mock_workspace_manager.root
        specific_mock_path.resolve.return_value = self.mock_workspace_manager.root / file_path_str
        self.mock_workspace_manager.workspace_path.return_value = specific_mock_path
        self._setup_mock_file(specific_mock_path, "Hello world\nAnother line")

        tool_input = {"command": "str_replace", "path": file_path_str, "old_str": "NonExistent", "new_str": "Replacement"}
        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.success)
        self.assertIn("did not appear verbatim", result.tool_output)

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    def test_str_replace_verbatim_multiple_occurrences(self, mock_exists, mock_is_file, mock_is_dir, mock_read_text):
        file_path_str = "test_file.txt"
        specific_mock_path = MagicMock(spec=Path); specific_mock_path.name = file_path_str; specific_mock_path.parent = self.mock_workspace_manager.root
        specific_mock_path.resolve.return_value = self.mock_workspace_manager.root / file_path_str
        self.mock_workspace_manager.workspace_path.return_value = specific_mock_path
        self._setup_mock_file(specific_mock_path, "Repeat\nSome text\nRepeat")

        tool_input = {"command": "str_replace", "path": file_path_str, "old_str": "Repeat", "new_str": "Replaced"}
        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.success)
        self.assertIn("Multiple occurrences", result.tool_output)

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    def test_str_replace_ignore_indent_success(self, mock_exists, mock_is_file, mock_is_dir, mock_read_text, mock_write_text):
        file_path_str = "test_indent.txt"
        specific_mock_path = MagicMock(spec=Path); specific_mock_path.name = file_path_str; specific_mock_path.parent = self.mock_workspace_manager.root
        specific_mock_path.resolve.return_value = self.mock_workspace_manager.root / file_path_str
        self.mock_workspace_manager.workspace_path.return_value = specific_mock_path
        original_content = "  Indented line\n    More indented"
        self._setup_mock_file(specific_mock_path, original_content)

        tool_input = {
            "command": "str_replace",
            "path": file_path_str,
            "old_str": "Indented line\nMore indented", # No leading spaces in old_str for ignore_indent
            "new_str": "New line\n  New indented"
        }
        result = self.tool_ignore_indent.run_impl(tool_input) # Use the ignore_indent tool

        self.assertTrue(result.success, msg=result.tool_output)
        # new_str should be re-indented according to the first line of the match ("  Indented line")
        expected_new_content = "  New line\n    New indented"
        specific_mock_path.write_text.assert_called_once_with(expected_new_content)
        self.assertEqual(len(self.tool_ignore_indent._file_history[specific_mock_path]), 1)

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    def test_undo_edit_success(self, mock_exists, mock_is_file, mock_is_dir, mock_read_text, mock_write_text):
        file_path_str = "test_undo.txt"
        specific_mock_path = MagicMock(spec=Path); specific_mock_path.name = file_path_str; specific_mock_path.parent = self.mock_workspace_manager.root
        specific_mock_path.resolve.return_value = self.mock_workspace_manager.root / file_path_str
        self.mock_workspace_manager.workspace_path.return_value = specific_mock_path

        original_content = "Content line 1\nContent line 2"
        edited_content = "Edited line 1\nContent line 2"
        self._setup_mock_file(specific_mock_path, original_content) # Initial state

        # Perform an edit first
        self.tool._file_history[specific_mock_path].append(original_content) # Manually simulate history
        specific_mock_path.write_text(edited_content) # Simulate file is now edited
        # Reset read_text to return the "edited" content for the undo operation
        specific_mock_path.read_text.return_value = edited_content


        tool_input_undo = {"command": "undo_edit", "path": file_path_str}
        result_undo = self.tool.run_impl(tool_input_undo)

        self.assertTrue(result_undo.success, msg=result.tool_output)
        specific_mock_path.write_text.assert_called_with(original_content) # Should write back original
        self.assertEqual(len(self.tool._file_history[specific_mock_path]), 0) # History item popped
        self.assertIn(f"Last edit to {file_path_str} undone successfully.", result_undo.tool_output)

    def test_undo_edit_no_history(self):
        file_path_str = "test_no_undo.txt"
        specific_mock_path = MagicMock(spec=Path); specific_mock_path.name = file_path_str; specific_mock_path.parent = self.mock_workspace_manager.root
        specific_mock_path.resolve.return_value = self.mock_workspace_manager.root / file_path_str
        self.mock_workspace_manager.workspace_path.return_value = specific_mock_path
        self._setup_mock_file(specific_mock_path, "Some content", exists=True) # File exists

        tool_input_undo = {"command": "undo_edit", "path": file_path_str}
        result_undo = self.tool.run_impl(tool_input_undo)

        self.assertFalse(result_undo.success)
        self.assertIn(f"No edit history found for {file_path_str}", result_undo.tool_output)

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    def test_str_replace_expand_tabs(self, mock_exists, mock_is_file, mock_is_dir, mock_read_text, mock_write_text):
        file_path_str = "tab_test.txt"
        specific_mock_path = MagicMock(spec=Path); specific_mock_path.name = file_path_str; specific_mock_path.parent = self.mock_workspace_manager.root
        specific_mock_path.resolve.return_value = self.mock_workspace_manager.root / file_path_str
        self.mock_workspace_manager.workspace_path.return_value = specific_mock_path

        original_content_with_tabs = "Line\twith\ttabs"
        # Assuming default tab expansion to 8 spaces, but python .expandtabs() is default 8
        expanded_original_content = "Line    with    tabs"

        self._setup_mock_file(specific_mock_path, original_content_with_tabs)

        tool_input = {
            "command": "str_replace",
            "path": file_path_str,
            "old_str": "with\ttabs", # old_str also gets expanded
            "new_str": "no\ttabs"   # new_str also gets expanded
        }
        result = self.tool_expand_tabs.run_impl(tool_input) # Use tool with expand_tabs=True

        self.assertTrue(result.success, msg=result.tool_output)

        expected_old_str_expanded = "with    tabs"
        expected_new_str_expanded = "no      tabs" # Note: if new_str had different tab stops, it would be different

        # The content passed to write_text should have tabs expanded if original had them,
        # and the replacement section also expanded.
        # The actual replacement happens on the *expanded* content.
        final_expected_content = "Line    no      tabs"
        specific_mock_path.write_text.assert_called_once_with(final_expected_content)


    # TODO: Add tests for 'create', 'view', 'insert' commands and path validation logic.
    # Test for path outside workspace root.

if __name__ == "__main__":
    unittest.main()
