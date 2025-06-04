import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from src.ii_agent.tools.browser_tools.tab import BrowserSwitchTabTool, BrowserOpenNewTabTool
from src.ii_agent.browser.browser import Browser # For type hinting and spec
from src.ii_agent.tools.base import ToolImplOutput
from src.ii_agent.tools.browser_tools import utils as browser_utils


class CommonTabToolTests(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock(spec=Browser)

        self.mock_browser_state = MagicMock()
        self.mock_browser_state.screenshot = "tab_tool_screenshot_data"
        self.mock_browser.update_state = AsyncMock(return_value=self.mock_browser_state)

        self.sleep_patcher = patch('asyncio.sleep', new_callable=AsyncMock)
        self.mock_async_sleep = self.sleep_patcher.start()

        self.format_screenshot_patcher = patch('src.ii_agent.tools.browser_tools.tab.utils.format_screenshot_tool_output') # Patched at lookup
        self.mock_format_screenshot = self.format_screenshot_patcher.start()
        self.mock_formatted_output = ToolImplOutput("formatted_tab_llm", "formatted_tab_user")
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


class TestBrowserSwitchTabTool(CommonTabToolTests):
    def setUp(self):
        super().setUp()
        self.mock_browser.switch_to_tab = AsyncMock()
        self.tool = BrowserSwitchTabTool(browser=self.mock_browser)

    def test_run_switch_tab_success(self):
        tab_index = 2
        tool_input = {"index": tab_index}

        result = self._run_tool_async(self.tool, tool_input)

        self.mock_browser.switch_to_tab.assert_called_once_with(tab_index)
        self.mock_async_sleep.assert_called_once_with(0.5)
        self.mock_browser.update_state.assert_called_once()

        expected_msg = f"Switched to tab {tab_index}"
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, expected_msg)
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_switch_tab_browser_raises_exception(self):
        self.mock_browser.switch_to_tab.side_effect = Exception("Failed to switch tab")
        tool_input = {"index": 1}

        with self.assertRaisesRegex(Exception, "Failed to switch tab"):
            self._run_tool_async(self.tool, tool_input)

        self.mock_browser.update_state.assert_not_called()


class TestBrowserOpenNewTabTool(CommonTabToolTests):
    def setUp(self):
        super().setUp()
        self.mock_browser.create_new_tab = AsyncMock()
        self.tool = BrowserOpenNewTabTool(browser=self.mock_browser)

    def test_run_open_new_tab_success(self):
        # No input for this tool
        tool_input = {}
        result = self._run_tool_async(self.tool, tool_input)

        self.mock_browser.create_new_tab.assert_called_once()
        self.mock_async_sleep.assert_called_once_with(0.5)
        self.mock_browser.update_state.assert_called_once()

        expected_msg = "Opened a new tab"
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, expected_msg)
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_open_new_tab_browser_raises_exception(self):
        self.mock_browser.create_new_tab.side_effect = Exception("Failed to open new tab")
        tool_input = {}

        with self.assertRaisesRegex(Exception, "Failed to open new tab"):
            self._run_tool_async(self.tool, tool_input)

        self.mock_browser.update_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
