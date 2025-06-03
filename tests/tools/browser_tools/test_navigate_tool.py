import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from src.ii_agent.tools.browser_tools.navigate import BrowserNavigationTool, BrowserRestartTool
from src.ii_agent.browser.browser import Browser, BrowserPage # For type hinting and spec
from src.ii_agent.tools.base import ToolImplOutput
from src.ii_agent.tools.browser_tools import utils as browser_utils

# Mock Playwright's TimeoutError if Playwright is not installed in test env
try:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
except ImportError:
    PlaywrightTimeoutError = type('PlaywrightTimeoutError', (Exception,), {}) # Create a mock exception


class CommonNavigateToolTests(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock(spec=Browser)
        self.mock_page = MagicMock(spec=BrowserPage)
        self.mock_browser.get_current_page = AsyncMock(return_value=self.mock_page)

        self.mock_page.goto = AsyncMock()

        self.mock_browser_state = MagicMock()
        self.mock_browser_state.screenshot = "navigate_screenshot_data"
        self.mock_browser.update_state = AsyncMock(return_value=self.mock_browser_state)
        self.mock_browser.handle_pdf_url_navigation = AsyncMock(return_value=self.mock_browser_state)

        self.sleep_patcher = patch('asyncio.sleep', new_callable=AsyncMock)
        self.mock_async_sleep = self.sleep_patcher.start()

        self.format_screenshot_patcher = patch('src.ii_agent.tools.browser_tools.utils.format_screenshot_tool_output')
        self.mock_format_screenshot = self.format_screenshot_patcher.start()
        self.mock_formatted_output = ToolImplOutput("formatted_nav_llm", "formatted_nav_user")
        self.mock_format_screenshot.return_value = self.mock_formatted_output

    def tearDown(self):
        self.sleep_patcher.stop()
        self.format_screenshot_patcher.stop()

    def _run_tool_async(self, tool, tool_input):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(tool._run(tool_input))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return result


class TestBrowserNavigationTool(CommonNavigateToolTests):
    def setUp(self):
        super().setUp()
        self.tool = BrowserNavigationTool(browser=self.mock_browser)

    def test_run_navigate_success(self):
        url_to_navigate = "http://example.com"
        tool_input = {"url": url_to_navigate}

        result = self._run_tool_async(self.tool, tool_input)

        self.mock_browser.get_current_page.assert_called_once()
        self.mock_page.goto.assert_called_once_with(url_to_navigate, wait_until="domcontentloaded")
        self.mock_async_sleep.assert_called_once_with(1.5)
        self.mock_browser.update_state.assert_called_once()
        self.mock_browser.handle_pdf_url_navigation.assert_called_once()

        expected_msg = f"Navigated to {url_to_navigate}"
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, expected_msg)
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_navigate_timeout_error(self):
        url_to_navigate = "http://timeout.com"
        self.mock_page.goto.side_effect = PlaywrightTimeoutError("Navigation timed out")
        tool_input = {"url": url_to_navigate}

        result = self._run_tool_async(self.tool, tool_input)

        self.assertIsInstance(result, ToolImplOutput)
        expected_msg = f"Timeout error navigating to {url_to_navigate}"
        self.assertEqual(result.output_for_llm, expected_msg)
        self.assertEqual(result.output_for_user, expected_msg) # User message is same as LLM for this error
        self.mock_format_screenshot.assert_not_called() # No screenshot on timeout

    def test_run_navigate_generic_exception(self):
        url_to_navigate = "http://error.com"
        self.mock_page.goto.side_effect = Exception("Some other navigation error")
        tool_input = {"url": url_to_navigate}

        result = self._run_tool_async(self.tool, tool_input)

        self.assertIsInstance(result, ToolImplOutput)
        expected_msg = f"Something went wrong while navigating to {url_to_navigate}; double check the URL and try again."
        self.assertEqual(result.output_for_llm, expected_msg)
        self.mock_format_screenshot.assert_not_called()


class TestBrowserRestartTool(CommonNavigateToolTests):
    def setUp(self):
        super().setUp()
        self.mock_browser.restart = AsyncMock() # Specific to RestartTool
        self.tool = BrowserRestartTool(browser=self.mock_browser)

    def test_run_restart_and_navigate_success(self):
        url_to_navigate = "http://example.com/after_restart"
        tool_input = {"url": url_to_navigate}

        result = self._run_tool_async(self.tool, tool_input)

        self.mock_browser.restart.assert_called_once()
        self.mock_browser.get_current_page.assert_called_once() # Called after restart
        self.mock_page.goto.assert_called_once_with(url_to_navigate, wait_until="domcontentloaded")
        self.mock_async_sleep.assert_called_once_with(1.5)
        self.mock_browser.update_state.assert_called_once()

        expected_msg = f"Navigated to {url_to_navigate}"
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, expected_msg)
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_restart_and_navigate_timeout_error(self):
        url_to_navigate = "http://timeout_after_restart.com"
        self.mock_page.goto.side_effect = PlaywrightTimeoutError("Navigation timed out post-restart")
        tool_input = {"url": url_to_navigate}

        result = self._run_tool_async(self.tool, tool_input)

        self.mock_browser.restart.assert_called_once()
        self.assertIsInstance(result, ToolImplOutput)
        expected_msg = f"Timeout error navigating to {url_to_navigate}"
        self.assertEqual(result.output_for_llm, expected_msg)
        self.mock_format_screenshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
