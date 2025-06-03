import unittest
from unittest.mock import patch, MagicMock, mock_open
import os # For os.makedirs

from src.ii_agent.tools.slide_deck_tool import SlideDeckInitTool, SlideDeckCompleteTool, SLIDE_IFRAME_TEMPLATE
from src.ii_agent.utils.workspace_manager import WorkspaceManager
from src.ii_agent.tools.base import ToolImplOutput

class TestSlideDeckInitTool(unittest.TestCase):
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_workspace_manager.root = "/fake/workspace"
        self.tool = SlideDeckInitTool(workspace_manager=self.mock_workspace_manager)

    @patch('os.makedirs')
    @patch('subprocess.run')
    def test_run_impl_success(self, mock_subprocess_run, mock_makedirs):
        # Simulate successful git clone and npm install
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0, stdout="cloned successfully", stderr=""), # git clone
            MagicMock(returncode=0, stdout="npm installed successfully", stderr=""), # npm install
        ]

        result = self.tool.run_impl({})

        mock_makedirs.assert_called_once_with("/fake/workspace/presentation", exist_ok=True)

        expected_calls = [
            unittest.mock.call(
                f"git clone https://github.com/khoangothe/reveal.js.git /fake/workspace/presentation/reveal.js",
                shell=True, capture_output=True, text=True, cwd="/fake/workspace"
            ),
            unittest.mock.call(
                "npm install",
                shell=True, capture_output=True, text=True, cwd="/fake/workspace/presentation/reveal.js"
            )
        ]
        mock_subprocess_run.assert_has_calls(expected_calls)

        self.assertTrue(result.auxiliary_data["success"])
        self.assertIn("Successfully initialized slide deck", result.output_for_llm)

    @patch('os.makedirs')
    @patch('subprocess.run')
    def test_run_impl_git_clone_fails(self, mock_subprocess_run, mock_makedirs):
        mock_subprocess_run.return_value = MagicMock(returncode=1, stderr="git clone error", stdout="")

        result = self.tool.run_impl({})

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Failed to clone reveal.js repository: git clone error", result.output_for_llm)

    @patch('os.makedirs')
    @patch('subprocess.run')
    def test_run_impl_npm_install_fails(self, mock_subprocess_run, mock_makedirs):
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0, stdout="cloned", stderr=""), # git clone success
            MagicMock(returncode=1, stderr="npm install error", stdout=""), # npm install fails
        ]
        result = self.tool.run_impl({})

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Failed to install dependencies: npm install error", result.output_for_llm)

    @patch('os.makedirs', side_effect=Exception("makedirs failed"))
    def test_run_impl_makedirs_fails(self, mock_makedirs):
        result = self.tool.run_impl({})
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Error initializing slide deck: makedirs failed", result.output_for_llm)


class TestSlideDeckCompleteTool(unittest.TestCase):
    def setUp(self):
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_workspace_manager.root = "/fake/workspace"
        self.tool = SlideDeckCompleteTool(workspace_manager=self.mock_workspace_manager)

    def test_run_impl_success(self):
        slide_paths = ["./slides/intro.html", "slides/content.html"] # Mixed ./ and not
        tool_input = {"slide_paths": slide_paths}

        original_index_content = "<html><head></head><body><!--PLACEHOLDER SLIDES REPLACE THIS--></body></html>"

        # Expected iframe strings after path normalization (./ removed)
        iframe1 = SLIDE_IFRAME_TEMPLATE.format(slide_path="slides/intro.html")
        iframe2 = SLIDE_IFRAME_TEMPLATE.format(slide_path="slides/content.html")
        expected_iframes_str = f"{iframe1}\n{iframe2}"
        expected_final_content = original_index_content.replace("<!--PLACEHOLDER SLIDES REPLACE THIS-->", expected_iframes_str)

        mock_file = mock_open(read_data=original_index_content)
        with patch('builtins.open', mock_file):
            result = self.tool.run_impl(tool_input)

        mock_file.assert_any_call("/fake/workspace/presentation/reveal.js/index.html", "r")
        mock_file().write.assert_called_once_with(expected_final_content)

        self.assertTrue(result.auxiliary_data["success"])
        self.assertIn("Successfully combined slides", result.output_for_llm)
        self.assertEqual(result.auxiliary_data["slide_paths"], slide_paths)


    def test_run_impl_invalid_slide_path_format(self):
        slide_paths = ["./introduction.html"] # Not in slides/ subdirectory
        tool_input = {"slide_paths": slide_paths}

        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("must be in the slides/ subdirectory", result.output_for_llm)

    def test_run_impl_read_index_html_fails(self):
        slide_paths = ["./slides/good.html"]
        tool_input = {"slide_paths": slide_paths}

        with patch('builtins.open', side_effect=FileNotFoundError("Cannot read index.html")):
            result = self.tool.run_impl(tool_input)

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn("Error reading `index.html`: Cannot read index.html", result.output_for_llm)


if __name__ == "__main__":
    unittest.main()
