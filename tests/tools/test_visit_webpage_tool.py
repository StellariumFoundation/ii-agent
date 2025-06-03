import unittest
from unittest.mock import patch, MagicMock

# Import the tool and client-related exceptions/classes
from src.ii_agent.tools.visit_webpage_tool import VisitWebpageTool
from src.ii_agent.tools.visit_webpage_client import (
    BaseVisitClient, # To mock the type of visit_client attribute
    WebpageVisitException,
    ContentExtractionError,
    NetworkError,
)
from src.ii_agent.tools.base import ToolImplOutput

class TestVisitWebpageTool(unittest.TestCase):
    def setUp(self):
        # We need to mock the create_visit_client that's called in VisitWebpageTool.__init__
        # or patch the visit_client attribute after instantiation.
        # Patching create_visit_client is cleaner for __init__.

        self.mock_visit_client_instance = MagicMock(spec=BaseVisitClient)
        # Set a name for the mock client for output messages
        self.mock_visit_client_instance.name = "MockedClient"

        self.create_client_patcher = patch(
            "src.ii_agent.tools.visit_webpage_tool.create_visit_client",
            return_value=self.mock_visit_client_instance
        )
        self.mock_create_visit_client = self.create_client_patcher.start()

        self.tool = VisitWebpageTool(max_output_length=1000)

    def tearDown(self):
        self.create_client_patcher.stop()

    def test_run_impl_success(self):
        url = "http://example.com"
        expected_content = "Webpage content here."
        self.mock_visit_client_instance.forward.return_value = expected_content

        tool_input = {"url": url}
        result = self.tool.run_impl(tool_input)

        self.mock_visit_client_instance.forward.assert_called_once_with(url)
        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.output_for_llm, expected_content)
        self.assertEqual(result.output_for_user, f"Webpage {url} successfully visited using MockedClient")
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_arxiv_url_transformation(self):
        original_url = "http://arxiv.org/abs/1234.5678"
        transformed_url = "https://arxiv.org/html/1234.5678"
        expected_content = "Arxiv content."
        self.mock_visit_client_instance.forward.return_value = expected_content

        tool_input = {"url": original_url}
        self.tool.run_impl(tool_input)

        self.mock_visit_client_instance.forward.assert_called_once_with(transformed_url)

    def test_run_impl_content_extraction_error(self):
        url = "http://example.com/empty"
        self.mock_visit_client_instance.forward.side_effect = ContentExtractionError("Could not extract.")

        tool_input = {"url": url}
        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn(f"Failed to extract content from {url}", result.output_for_llm)
        self.assertIn(f"Failed to extract content from {url}", result.output_for_user)

    def test_run_impl_network_error(self):
        url = "http://example.com/timeout"
        self.mock_visit_client_instance.forward.side_effect = NetworkError("Timeout.")

        tool_input = {"url": url}
        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn(f"Failed to access {url}", result.output_for_llm)
        self.assertIn("network error", result.output_for_user)

    def test_run_impl_generic_webpage_visit_exception(self):
        url = "http://example.com/genericerror"
        self.mock_visit_client_instance.forward.side_effect = WebpageVisitException("Generic visit error.")

        tool_input = {"url": url}
        result = self.tool.run_impl(tool_input)

        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn(f"Failed to visit {url}", result.output_for_llm)
        self.assertIn(f"Failed to visit {url}", result.output_for_user)

    def test_run_impl_missing_url_input(self):
        # This should ideally be caught by schema validation in LLMTool.execute
        with self.assertRaises(KeyError):
            self.tool.run_impl({})


if __name__ == "__main__":
    unittest.main()
