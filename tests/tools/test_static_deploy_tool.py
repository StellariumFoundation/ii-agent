import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import os

from src.ii_agent.tools.static_deploy_tool import StaticDeployTool
from src.ii_agent.utils.workspace_manager import WorkspaceManager
from src.ii_agent.tools.base import ToolImplOutput

class TestStaticDeployTool(unittest.TestCase):
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        # Example: /tmp/some_uuid_workspace/workspace_files
        # Let's make root have a name that acts as UUID
        self.workspace_uuid = "test_uuid_123"
        self.mock_workspace_manager.root = Path(f"/tmp/{self.workspace_uuid}")

        # workspace_path(Path(relative_file_path)) should return /tmp/test_uuid_123/relative_file_path
        self.mock_workspace_manager.workspace_path.side_effect = lambda p: self.mock_workspace_manager.root / p

        self.tool = StaticDeployTool(workspace_manager=self.mock_workspace_manager)

    def test_run_impl_success_default_base_url(self):
        file_path_str = "static/index.html"

        # Mock the Path object for the specific file
        mock_file_abs_path = self.mock_workspace_manager.root / file_path_str
        with patch.object(Path, 'exists') as mock_exists, \
             patch.object(Path, 'is_file') as mock_is_file, \
             patch.object(Path, 'relative_to') as mock_relative_to:

            # Configure mocks for the specific path instance that will be created
            # This requires knowing how workspace_path constructs it, or patching Path methods globally for the call
            # For simplicity, we'll assume these methods are called on mock_file_abs_path equivalent.
            # A more robust way would be to ensure workspace_path returns a pre-configured MagicMock(spec=Path).

            # Let's refine workspace_path to return a specific mock for easier method checking
            pre_mocked_file_path = MagicMock(spec=Path)
            pre_mocked_file_path.exists.return_value = True
            pre_mocked_file_path.is_file.return_value = True
            # relative_to should return the path relative to workspace_manager.root
            pre_mocked_file_path.relative_to.return_value = Path(file_path_str)
            # Make workspace_path return this pre-mocked Path object
            self.mock_workspace_manager.workspace_path.return_value = pre_mocked_file_path


            tool_input = {"file_path": file_path_str}

            # Default base_url is file:///tmp (parent of parent of /tmp/test_uuid_123)
            # self.mock_workspace_manager.root.parent.parent.absolute()
            # Let's mock this part for predictable default base URL
            default_base_dir = Path("/srv") # Example, could be anything
            with patch.object(self.mock_workspace_manager.root, 'parent') as mock_parent1:
                mock_parent2 = MagicMock()
                mock_parent2.parent.absolute.return_value = default_base_dir
                mock_parent1.parent = mock_parent2

                # Temporarily remove STATIC_FILE_BASE_URL if set for this test
                with patch.dict(os.environ, {}, clear=True):
                    # Re-initialize tool to pick up changed env
                    tool_under_test = StaticDeployTool(workspace_manager=self.mock_workspace_manager)
                    result = tool_under_test.run_impl(tool_input)

            expected_url = f"file://{default_base_dir}/workspace/{self.workspace_uuid}/{file_path_str}"
            self.assertIsInstance(result, ToolImplOutput)
            self.assertEqual(result.tool_output, expected_url)
            self.assertEqual(result.tool_result_message, f"Static file available at: {expected_url}")
            pre_mocked_file_path.relative_to.assert_called_once_with(self.mock_workspace_manager.root)


    @patch.dict(os.environ, {"STATIC_FILE_BASE_URL": "http://custom.cdn.com"})
    def test_run_impl_success_custom_base_url_from_env(self):
        file_path_str = "images/pic.jpg"
        # Re-initialize tool to pick up new env var
        tool_with_env = StaticDeployTool(workspace_manager=self.mock_workspace_manager)

        mock_file_abs_path = MagicMock(spec=Path)
        mock_file_abs_path.exists.return_value = True
        mock_file_abs_path.is_file.return_value = True
        mock_file_abs_path.relative_to.return_value = Path(file_path_str)
        self.mock_workspace_manager.workspace_path.return_value = mock_file_abs_path

        tool_input = {"file_path": file_path_str}
        result = tool_with_env.run_impl(tool_input)

        expected_url = f"http://custom.cdn.com/workspace/{self.workspace_uuid}/{file_path_str}"
        self.assertEqual(result.tool_output, expected_url)

    def test_run_impl_file_does_not_exist(self):
        file_path_str = "nonexistent.css"

        mock_file_abs_path = MagicMock(spec=Path)
        mock_file_abs_path.exists.return_value = False # File does not exist
        self.mock_workspace_manager.workspace_path.return_value = mock_file_abs_path

        tool_input = {"file_path": file_path_str}
        result = self.tool.run_impl(tool_input)

        self.assertEqual(result.tool_output, f"Path does not exist: {file_path_str}")
        self.assertEqual(result.tool_result_message, f"Path does not exist: {file_path_str}")

    def test_run_impl_path_is_not_a_file(self):
        dir_path_str = "static_dir"

        mock_dir_abs_path = MagicMock(spec=Path)
        mock_dir_abs_path.exists.return_value = True
        mock_dir_abs_path.is_file.return_value = False # It's a directory
        self.mock_workspace_manager.workspace_path.return_value = mock_dir_abs_path

        tool_input = {"file_path": dir_path_str}
        result = self.tool.run_impl(tool_input)

        self.assertEqual(result.tool_output, f"Path is not a file: {dir_path_str}")
        self.assertEqual(result.tool_result_message, f"Path is not a file: {dir_path_str}")

    def test_run_impl_missing_filepath_input(self):
        # This should ideally be caught by schema validation in LLMTool.execute
        with self.assertRaises(KeyError):
            self.tool.run_impl({})


if __name__ == "__main__":
    unittest.main()
