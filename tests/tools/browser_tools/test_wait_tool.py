import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from src.ii_agent.tools.browser_tools.wait import BrowserWaitTool
from src.ii_agent.browser.browser import Browser, BrowserState # For type hinting and spec
from src.ii_agent.tools.base import ToolImplOutput
from src.ii_agent.tools.browser_tools import utils as browser_utils


class TestBrowserWaitTool(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock(spec=Browser)

        self.mock_browser_state = MagicMock(spec=BrowserState)
        self.mock_browser_state.screenshot = "wait_tool_screenshot_data"
        self.mock_browser.update_state = AsyncMock(return_value=self.mock_browser_state)
        self.mock_browser.handle_pdf_url_navigation = AsyncMock(return_value=self.mock_browser_state) # Returns updated state

        self.tool = BrowserWaitTool(browser=self.mock_browser)

        self.sleep_patcher = patch('asyncio.sleep', new_callable=AsyncMock)
        self.mock_async_sleep = self.sleep_patcher.start()

        self.format_screenshot_patcher = patch('src.ii_agent.tools.browser_tools.utils.format_screenshot_tool_output')
        self.mock_format_screenshot = self.format_screenshot_patcher.start()
        self.mock_formatted_output = ToolImplOutput("formatted_wait_llm", "formatted_wait_user")
        self.mock_format_screenshot.return_value = self.mock_formatted_output

    def tearDown(self):
        self.sleep_patcher.stop()
        self.format_screenshot_patcher.stop()

    def _run_tool_async(self, tool_input=None): # tool_input is {} for this tool
        if tool_input is None:
            tool_input = {}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.tool._run(tool_input))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return result

    def test_run_wait_tool_success(self):
        result = self._run_tool_async()

        self.mock_async_sleep.assert_called_once_with(1) # Fixed 1 second sleep
        self.mock_browser.update_state.assert_called_once()
        self.mock_browser.handle_pdf_url_navigation.assert_called_once()

        expected_msg = "Waited for page"
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, expected_msg)
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_wait_tool_update_state_fails(self):
        # If update_state fails after sleep, the exception should propagate
        self.mock_browser.update_state.side_effect = Exception("Failed to update state after wait")

        with self.assertRaisesRegex(Exception, "Failed to update state after wait"):
            self._run_tool_async()

        self.mock_async_sleep.assert_called_once_with(1)
        self.mock_format_screenshot.assert_not_called() # Should not be reached


if __name__ == "__main__":
    unittest.main()
