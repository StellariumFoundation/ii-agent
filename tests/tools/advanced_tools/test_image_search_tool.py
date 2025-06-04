import unittest
from unittest.mock import patch, MagicMock
import json # For creating mock search result strings

from src.ii_agent.tools.advanced_tools.image_search_tool import ImageSearchTool
# ImageSearchClient is what create_image_search_client is expected to return or None
from src.ii_agent.tools.web_search_client import ImageSearchClient
from src.ii_agent.tools.base import ToolImplOutput


class TestImageSearchTool(unittest.TestCase):
    def setUp(self):
        self.mock_image_search_client_instance = MagicMock(spec=ImageSearchClient)
        self.mock_image_search_client_instance.name = "MockedImageSearchClient"

        # Patch create_image_search_client in the module where ImageSearchTool uses it
        self.create_client_patcher = patch(
            "src.ii_agent.tools.advanced_tools.image_search_tool.create_image_search_client",
            return_value=self.mock_image_search_client_instance
        )
        self.mock_create_image_search_client = self.create_client_patcher.start()

        self.tool = ImageSearchTool(max_results=3)

    def tearDown(self):
        self.create_client_patcher.stop()

    def test_init_client_creation(self):
        self.mock_create_image_search_client.assert_called_once_with(max_results=3)
        self.assertIs(self.tool.image_search_client, self.mock_image_search_client_instance)

    def test_is_available_client_exists(self):
        self.assertTrue(self.tool.is_available())

    def test_is_available_client_is_none(self):
        # Stop the current patch, then re-patch create_image_search_client to return None
        self.create_client_patcher.stop()

        create_client_returns_none_patcher = patch(
            "src.ii_agent.tools.advanced_tools.image_search_tool.create_image_search_client",
            return_value=None # Simulate no client available
        )
        mock_create_returns_none = create_client_returns_none_patcher.start()

        tool_unavailable = ImageSearchTool(max_results=3) # Re-initialize
        self.assertFalse(tool_unavailable.is_available())

        create_client_returns_none_patcher.stop()
        # Restart original patcher for other tests if setUp doesn't run for each method in some test runners (though it should)
        self.mock_create_image_search_client = self.create_client_patcher.start()


    def test_run_impl_success(self):
        query = "cats in hats"
        mock_results_data = [
            {"title": "Cat Hat 1", "image_url": "http://example.com/cat1.jpg", "width": 800, "height": 600},
            {"title": "Cat Hat 2", "image_url": "http://example.com/cat2.jpg", "width": 1024, "height": 768},
        ]
        # ImageSearchClient.forward is expected to return a JSON string
        expected_client_output_str = json.dumps(mock_results_data, indent=4)
        self.mock_image_search_client_instance.forward.return_value = expected_client_output_str

        tool_input = {"query": query}
        result = self.tool.run_impl(tool_input)

        self.mock_image_search_client_instance.forward.assert_called_once_with(query)
        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.tool_output, expected_client_output_str)
        self.assertIn(f"Image Search Results with query: {query} successfully retrieved", result.tool_result_message)
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_client_raises_exception(self):
        query = "error query"
        error_message = "Image search API error"
        self.mock_image_search_client_instance.forward.side_effect = Exception(error_message)

        tool_input = {"query": query}
        result = self.tool.run_impl(tool_input)

        self.mock_image_search_client_instance.forward.assert_called_once_with(query)
        self.assertIsInstance(result, ToolImplOutput)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn(f"Error searching the web with MockedImageSearchClient: {error_message}", result.tool_output)

    def test_run_impl_client_is_none_should_fail_gracefully_or_be_prevented(self):
        # Simulate that the client was None during tool init
        self.tool.image_search_client = None # Manually set to None after normal setup

        tool_input = {"query": "query for no client"}
        # Current code would raise AttributeError: 'NoneType' object has no attribute 'forward'
        # A more robust tool might check `if not self.is_available():` in run_impl
        with self.assertRaises(AttributeError):
            self.tool.run_impl(tool_input)

        # If we wanted to test a hypothetical robust version:
        # self.tool.is_available = MagicMock(return_value=False) # Or ensure client is None
        # result = self.tool.run_impl(tool_input)
        # self.assertFalse(result.auxiliary_data["success"])
        # self.assertIn("Image search client is not available", result.tool_output)


if __name__ == "__main__":
    unittest.main()
