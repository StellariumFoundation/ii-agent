import unittest
from unittest.mock import patch, MagicMock

from src.ii_agent.tools.web_search_tool import WebSearchTool
from src.ii_agent.tools.web_search_client import BaseSearchClient # To mock the type
from src.ii_agent.tools.base import ToolImplOutput

class TestWebSearchTool(unittest.TestCase):
    def setUp(self):
        self.mock_search_client_instance = MagicMock(spec=BaseSearchClient)
        self.mock_search_client_instance.name = "MockedSearchClient" # For output messages

        # Patch create_search_client in the module where WebSearchTool uses it
        self.create_client_patcher = patch(
            "src.ii_agent.tools.web_search_tool.create_search_client",
            return_value=self.mock_search_client_instance
        )
        self.mock_create_search_client = self.create_client_patcher.start()

        self.tool = WebSearchTool(max_results=5)

    def tearDown(self):
        self.create_client_patcher.stop()

    def test_run_impl_success(self):
        query = "test search query"
        expected_search_results_str = '[{"title": "Result 1", "url": "url1", "content": "snippet1"}]'
        self.mock_search_client_instance.forward.return_value = expected_search_results_str

        tool_input = {"query": query}
        result = self.tool.run_impl(tool_input)

        self.mock_search_client_instance.forward.assert_called_once_with(query)
        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.output_for_llm, expected_search_results_str)
        self.assertEqual(result.output_for_user, f"Search Results with query: {query} successfully retrieved using MockedSearchClient")
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_client_raises_exception(self):
        query = "query that causes error"
        error_message = "Client API error"
        self.mock_search_client_instance.forward.side_effect = Exception(error_message)

        tool_input = {"query": query}
        result = self.tool.run_impl(tool_input)

        self.mock_search_client_instance.forward.assert_called_once_with(query)
        self.assertIsInstance(result, ToolImplOutput)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertIn(f"Error searching the web with MockedSearchClient: {error_message}", result.output_for_llm)
        self.assertEqual(result.output_for_user, f"Failed to search the web with query: {query}")

    def test_run_impl_missing_query_input(self):
        # This should ideally be caught by schema validation in LLMTool.execute
        with self.assertRaises(KeyError):
            self.tool.run_impl({})

    def test_tool_initialization_passes_max_results_to_client_factory(self):
        # Stop the global patch for this specific init test
        self.create_client_patcher.stop()

        # Start a new patch specifically to check the arguments create_search_client was called with
        with patch("src.ii_agent.tools.web_search_tool.create_search_client") as mock_factory:
            WebSearchTool(max_results=7)
            mock_factory.assert_called_once_with(max_results=7)

        # Restart the global patcher if other tests in this class need it (though tearDown handles it)
        # self.mock_create_search_client = self.create_client_patcher.start() # Not strictly needed if this is the last test or setUp reruns

if __name__ == "__main__":
    unittest.main()
