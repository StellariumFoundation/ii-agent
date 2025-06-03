import unittest
from unittest.mock import patch, MagicMock
import os
import json

# Import classes and functions to be tested
from src.ii_agent.tools.web_search_client import (
    BaseSearchClient,
    DuckDuckGoSearchClient,
    SerpAPISearchClient,
    JinaSearchClient,
    TavilySearchClient,
    ImageSearchClient, # Added for completeness if testing create_image_search_client
    create_search_client,
    create_image_search_client,
)
from src.ii_agent.tools.utils import truncate_content # Used by clients

# Mock for duckduckgo_search.DDGS if that library is used by a client
# We'll define it here so it can be patched.
try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = MagicMock() # If not installed, use a mock for type hinting / patching

# Mock for TavilyClient
try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = MagicMock()


class TestCreateSearchClient(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True) # No API keys set
    def test_create_duckduckgo_client_by_default(self):
        with patch('src.ii_agent.tools.web_search_client.DDGS', DDGS): # Ensure DDGS is mock if not installed
            client = create_search_client()
            self.assertIsInstance(client, DuckDuckGoSearchClient)

    @patch.dict(os.environ, {"SERPAPI_API_KEY": "test_serp_key"}, clear=True)
    def test_create_serpapi_client(self):
        client = create_search_client()
        self.assertIsInstance(client, SerpAPISearchClient)

    @patch.dict(os.environ, {"JINA_API_KEY": "test_jina_key"}, clear=True)
    def test_create_jina_client_over_tavily_ddg(self):
        # Jina is after SerpAPI, before Tavily
        with patch.dict(os.environ, {"TAVILY_API_KEY": "fake_tavily"}, clear=False):
            client = create_search_client()
            self.assertIsInstance(client, JinaSearchClient)

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test_tavily_key"}, clear=True)
    def test_create_tavily_client_over_ddg(self):
        # Tavily is after SerpAPI and Jina, before DDG
        client = create_search_client()
        self.assertIsInstance(client, TavilySearchClient)

    # Test priority: SerpAPI > Jina > Tavily > DuckDuckGo
    @patch.dict(os.environ, {"SERPAPI_API_KEY": "serp", "JINA_API_KEY": "jina", "TAVILY_API_KEY": "tavily"}, clear=True)
    def test_priority_serpapi_over_all(self):
        client = create_search_client()
        self.assertIsInstance(client, SerpAPISearchClient)

    @patch.dict(os.environ, {"JINA_API_KEY": "jina", "TAVILY_API_KEY": "tavily"}, clear=True)
    def test_priority_jina_over_tavily_no_serp(self):
        client = create_search_client()
        self.assertIsInstance(client, JinaSearchClient)


class TestDuckDuckGoSearchClient(unittest.TestCase):
    @patch('src.ii_agent.tools.web_search_client.DDGS') # Patch where DDGS is imported and used
    def setUp(self, mock_ddgs_constructor):
        self.mock_ddgs_instance = MagicMock()
        mock_ddgs_constructor.return_value = self.mock_ddgs_instance
        self.client = DuckDuckGoSearchClient(max_results=3)

    def test_forward_success(self):
        mock_results = [
            {"title": "Result 1", "href": "http://example.com/1", "body": "Snippet 1"},
            {"title": "Result 2", "href": "http://example.com/2", "body": "Snippet 2"},
        ]
        self.mock_ddgs_instance.text.return_value = mock_results

        query = "test query"
        result_str = self.client.forward(query)

        self.mock_ddgs_instance.text.assert_called_once_with(query, max_results=3)
        self.assertIn("## Search Results", result_str)
        self.assertIn("[Result 1](http://example.com/1)\nSnippet 1", result_str)
        self.assertIn("[Result 2](http://example.com/2)\nSnippet 2", result_str)

    def test_forward_no_results(self):
        self.mock_ddgs_instance.text.return_value = []
        query = "query with no results"

        with self.assertRaisesRegex(Exception, "No results found! Try a less restrictive/shorter query."):
            self.client.forward(query)

    def test_forward_truncation(self):
        # Create a result that, when formatted, will exceed the client's internal max_output_length for truncate_content
        # DuckDuckGoSearchClient uses the default MAX_LENGTH_TRUNCATE_CONTENT from utils
        from src.ii_agent.tools.utils import MAX_LENGTH_TRUNCATE_CONTENT as default_max_len

        long_snippet = "a" * (default_max_len // 2)
        mock_results = [
            {"title": "Long Result", "href": "http://example.com/long", "body": long_snippet},
            {"title": "Another Long", "href": "http://example.com/long2", "body": long_snippet}, # Two make it very long
        ]
        self.mock_ddgs_instance.text.return_value = mock_results

        result_str = self.client.forward("long query")
        self.assertIn("..._This content has been truncated", result_str)
        self.assertTrue(len(result_str) <= default_max_len + 500) # Allow some overhead for formatting

    def test_import_error(self):
        # To test this, we need to make DDGS raise an ImportError when __init__ is called
        # This is tricky because DDGS is imported at the class/module level of web_search_client.py
        # The current DuckDuckGoSearchClient constructor raises the error.
        with patch('src.ii_agent.tools.web_search_client.DDGS', side_effect=ImportError("Mocked import error")):
            with self.assertRaisesRegex(ImportError, "You must install package `duckduckgo-search`"):
                 DuckDuckGoSearchClient()


class TestSerpAPISearchClient(unittest.TestCase):
    @patch.dict(os.environ, {"SERPAPI_API_KEY": "test_serp_key"}, clear=True)
    def setUp(self):
        self.client = SerpAPISearchClient(max_results=2)

    def test_init_no_api_key(self):
        # SerpAPI client doesn't raise in init if key is missing, but prints.
        # The actual error would occur when _search_query_by_serp_api is called without a key.
        # This test is more about the factory function or actual usage.
        # For the client itself, it will proceed, and _search_query_by_serp_api will likely fail or return empty if key is bad/missing.
        with patch.dict(os.environ, {}, clear=True):
            client_no_key = SerpAPISearchClient()
            self.assertEqual(client_no_key.api_key, "") # Key is empty, does not raise here.

    @patch("requests.get")
    def test_forward_success(self, mock_requests_get):
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "organic_results": [
                {"title": "Serp Result 1", "link": "http://serp.com/1", "snippet": "Serp Snippet 1"},
                {"title": "Serp Result 2", "link": "http://serp.com/2", "snippet": "Serp Snippet 2"},
                {"title": "Serp Result 3", "link": "http://serp.com/3", "snippet": "Serp Snippet 3"}, # More than max_results
            ]
        }
        mock_requests_get.return_value = mock_api_response

        query = "serp query"
        result_str = self.client.forward(query)

        expected_output_list = [
            {"title": "Serp Result 1", "url": "http://serp.com/1", "content": "Serp Snippet 1"},
            {"title": "Serp Result 2", "url": "http://serp.com/2", "content": "Serp Snippet 2"},
        ] # Only max_results=2

        self.assertEqual(json.loads(result_str), expected_output_list)
        mock_requests_get.assert_called_once()
        args, kwargs = mock_requests_get.call_args
        self.assertIn("https://serpapi.com/search.json", args[0])
        self.assertIn(f"api_key={self.client.api_key}", args[0])
        self.assertIn(f"q={query}", args[0])


    @patch("requests.get")
    def test_forward_api_error(self, mock_requests_get):
        mock_api_response = MagicMock()
        mock_api_response.status_code = 500 # Simulate server error
        mock_requests_get.return_value = mock_api_response

        # The client's _search_query_by_serp_api catches exceptions and returns empty list
        # Then forward formats this empty list.
        result_str = self.client.forward("query with api error")
        self.assertEqual(json.loads(result_str), [])

    @patch("requests.get")
    def test_forward_empty_results_from_api(self, mock_requests_get):
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {"organic_results": []} # API returns no results
        mock_requests_get.return_value = mock_api_response

        result_str = self.client.forward("empty results query")
        self.assertEqual(json.loads(result_str), [])

# TODO: Add tests for JinaSearchClient and TavilySearchClient, ImageSearchClient
# Similar structure to SerpAPISearchClient: mock requests.get or the specific client library,
# check API key usage, response parsing, and error handling.

if __name__ == "__main__":
    unittest.main()
