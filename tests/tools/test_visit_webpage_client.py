import unittest
from unittest.mock import patch, MagicMock
import os
import json

# Import classes and functions to be tested
from src.ii_agent.tools.visit_webpage_client import (
    BaseVisitClient,
    MarkdownifyVisitClient,
    TavilyVisitClient,
    FireCrawlVisitClient,
    JinaVisitClient,
    create_visit_client,
    WebpageVisitException,
    ContentExtractionError,
    NetworkError,
)
# Import from utils for truncate_content, though it's used internally by clients
from src.ii_agent.tools.utils import truncate_content


class TestCreateVisitClient(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True) # Start with no relevant env vars
    def test_create_markdownify_client_by_default(self):
        client = create_visit_client()
        self.assertIsInstance(client, MarkdownifyVisitClient)

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test_tavily_key"}, clear=True)
    def test_create_tavily_client(self):
        client = create_visit_client()
        self.assertIsInstance(client, TavilyVisitClient)

    @patch.dict(os.environ, {"JINA_API_KEY": "test_jina_key"}, clear=True)
    def test_create_jina_client(self):
        # Jina is checked before Tavily in the factory if both are set
        with patch.dict(os.environ, {"TAVILY_API_KEY": "fake_tavily_if_jina_fails"}, clear=False):
             client = create_visit_client()
             self.assertIsInstance(client, JinaVisitClient)

    @patch.dict(os.environ, {"FIRECRAWL_API_KEY": "test_firecrawl_key"}, clear=True)
    def test_create_firecrawl_client(self):
        # Firecrawl is checked first
        with patch.dict(os.environ, {"JINA_API_KEY": "fake_jina", "TAVILY_API_KEY": "fake_tavily"}, clear=False):
            client = create_visit_client()
            self.assertIsInstance(client, FireCrawlVisitClient)

    # Test priority order (FireCrawl > Jina > Tavily > Markdownify)
    @patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc", "JINA_API_KEY": "jina", "TAVILY_API_KEY": "tavily"}, clear=True)
    def test_priority_firecrawl_over_others(self):
        client = create_visit_client()
        self.assertIsInstance(client, FireCrawlVisitClient)

    @patch.dict(os.environ, {"JINA_API_KEY": "jina", "TAVILY_API_KEY": "tavily"}, clear=True)
    def test_priority_jina_over_tavily(self):
        client = create_visit_client()
        self.assertIsInstance(client, JinaVisitClient)


class TestMarkdownifyVisitClient(unittest.TestCase):
    def setUp(self):
        self.client = MarkdownifyVisitClient(max_output_length=100)

    @patch("requests.get")
    @patch("markdownify.markdownify")
    def test_forward_success(self, mock_markdownify, mock_requests_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>Title</h1><p>Content</p></body></html>"
        mock_requests_get.return_value = mock_response

        mock_markdownify.return_value = "# Title\n\nContent"

        url = "http://example.com"
        result = self.client.forward(url)

        mock_requests_get.assert_called_once_with(url, timeout=20)
        mock_response.raise_for_status.assert_called_once()
        mock_markdownify.assert_called_once_with(mock_response.text)
        self.assertEqual(result, "# Title\n\nContent")

    @patch("requests.get")
    def test_forward_network_error_timeout(self, mock_requests_get):
        from requests.exceptions import Timeout
        mock_requests_get.side_effect = Timeout("Request timed out")

        with self.assertRaisesRegex(NetworkError, "The request timed out"):
            self.client.forward("http://example.com")

    @patch("requests.get")
    def test_forward_network_error_request_exception(self, mock_requests_get):
        from requests.exceptions import RequestException
        mock_requests_get.side_effect = RequestException("Some other network error")

        with self.assertRaisesRegex(NetworkError, "Error fetching the webpage: Some other network error"):
            self.client.forward("http://example.com")

    @patch("requests.get")
    @patch("markdownify.markdownify")
    def test_forward_content_extraction_error_empty_markdown(self, mock_markdownify, mock_requests_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body></body></html>" # Empty body
        mock_requests_get.return_value = mock_response
        mock_markdownify.return_value = "" # markdownify returns empty string

        with self.assertRaisesRegex(ContentExtractionError, "No content found in the webpage"):
            self.client.forward("http://example.com")

    @patch("requests.get")
    @patch("markdownify.markdownify")
    def test_forward_truncation(self, mock_markdownify, mock_requests_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Very long content...</p></body></html>"
        mock_requests_get.return_value = mock_response

        long_content = "a" * 120 # Exceeds max_output_length=100
        mock_markdownify.return_value = long_content

        expected_truncated_content = truncate_content(long_content, 100)
        result = self.client.forward("http://example.com")
        self.assertEqual(result, expected_truncated_content)
        self.assertTrue(len(result) < 120) # Ensure it's actually shorter
        self.assertIn("..._This content has been truncated", result)

    def test_import_error_handling(self):
        # Simulate markdownify not being installed
        with patch.dict('sys.modules', {'markdownify': None}):
            with self.assertRaisesRegex(WebpageVisitException, "Required packages 'markdownify' and 'requests' are not installed"):
                # Instantiating a new client to trigger its import check within forward,
                # or directly calling forward if imports are at method level.
                # In this case, imports are inside forward().
                client = MarkdownifyVisitClient()
                client.forward("http://example.com")


class TestFireCrawlVisitClient(unittest.TestCase):
    @patch.dict(os.environ, {"FIRECRAWL_API_KEY": "test_fc_key"}, clear=True)
    def setUp(self):
        self.client = FireCrawlVisitClient(max_output_length=200)

    def test_init_no_api_key(self):
        with patch.dict(os.environ, {}, clear=True): # No API key
            with self.assertRaisesRegex(WebpageVisitException, "FIRECRAWL_API_KEY environment variable not set"):
                FireCrawlVisitClient()

    @patch("requests.request")
    def test_forward_success_firecrawl(self, mock_requests_post):
        mock_api_response = MagicMock()
        mock_api_response.json.return_value = {"data": {"markdown": "FireCrawl Markdown Content"}}
        mock_requests_post.return_value = mock_api_response

        url = "http://example.com"
        result = self.client.forward(url)

        self.assertEqual(result, "FireCrawl Markdown Content")

        expected_payload = {"url": url, "onlyMainContent": False, "formats": ["markdown"]}
        mock_requests_post.assert_called_once_with(
            "POST",
            "https://api.firecrawl.dev/v1/scrape",
            headers=unittest.mock.ANY, # Headers include API key, check if needed
            data=json.dumps(expected_payload)
        )
        actual_headers = mock_requests_post.call_args.kwargs['headers']
        self.assertEqual(actual_headers['Authorization'], "Bearer test_fc_key")


    @patch("requests.request")
    def test_forward_network_error_firecrawl(self, mock_requests_post):
        from requests.exceptions import RequestException
        mock_requests_post.side_effect = RequestException("FireCrawl API error")

        with self.assertRaisesRegex(NetworkError, "Error making request: FireCrawl API error"):
            self.client.forward("http://example.com")

    @patch("requests.request")
    def test_forward_content_extraction_error_firecrawl_no_data(self, mock_requests_post):
        mock_api_response = MagicMock()
        # Simulate API returning success, but 'data' or 'markdown' field is missing/empty
        mock_api_response.json.return_value = {"data": {"markdown": ""}} # Empty markdown
        mock_requests_post.return_value = mock_api_response

        with self.assertRaisesRegex(ContentExtractionError, "No content could be extracted from webpage"):
            self.client.forward("http://example.com")

        mock_api_response.json.return_value = {"data": {}} # Missing markdown key
        mock_requests_post.return_value = mock_api_response
        with self.assertRaisesRegex(ContentExtractionError, "No content could be extracted from webpage"):
            self.client.forward("http://example.com")


# TODO: Add similar test classes for TavilyVisitClient and JinaVisitClient if time permits,
# focusing on their specific request/response mocking and API key handling.

if __name__ == "__main__":
    unittest.main()
