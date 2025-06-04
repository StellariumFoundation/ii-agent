import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from playwright.async_api import Page, Keyboard # Added import

from src.ii_agent.tools.browser_tools.press_key import BrowserPressKeyTool
from src.ii_agent.browser.browser import Browser # Removed BrowserPage, Keyboard
from src.ii_agent.tools.base import ToolImplOutput
from src.ii_agent.tools.browser_tools import utils as browser_utils


class TestBrowserPressKeyTool(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock(spec=Browser)
        self.mock_page = MagicMock(spec=Page) # Changed spec to Page
        self.mock_browser.get_current_page = AsyncMock(return_value=self.mock_page)

        self.mock_keyboard = MagicMock(spec=Keyboard) # Spec is now playwright's Keyboard
        self.mock_keyboard.press = AsyncMock()
        self.mock_page.keyboard = self.mock_keyboard

        self.mock_browser_state = MagicMock()
        self.mock_browser_state.screenshot = "press_key_screenshot"
        self.mock_browser.update_state = AsyncMock(return_value=self.mock_browser_state)

        self.tool = BrowserPressKeyTool(browser=self.mock_browser)

        self.sleep_patcher = patch('asyncio.sleep', new_callable=AsyncMock)
        self.mock_async_sleep = self.sleep_patcher.start()

        self.format_screenshot_patcher = patch('src.ii_agent.tools.browser_tools.press_key.utils.format_screenshot_tool_output') # Patched at lookup
        self.mock_format_screenshot = self.format_screenshot_patcher.start()
        self.mock_formatted_output = ToolImplOutput("formatted_press_key_llm", "formatted_press_key_user")
        self.mock_format_screenshot.return_value = self.mock_formatted_output

    def tearDown(self):
        self.sleep_patcher.stop()
        self.format_screenshot_patcher.stop()

    def _run_tool_async(self, tool_input):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.tool._run(tool_input))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return result

    def test_run_press_key_success(self):
        key_to_press = "Enter"
        tool_input = {"key": key_to_press}

        result = self._run_tool_async(tool_input)

        self.mock_browser.get_current_page.assert_called_once()
        self.mock_keyboard.press.assert_called_once_with(key_to_press)
        self.mock_async_sleep.assert_called_once_with(0.5)
        self.mock_browser.update_state.assert_called_once()

        expected_msg = f'Pressed "{key_to_press}" on the keyboard.'
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, expected_msg)
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_press_key_combination_success(self):
        key_combo = "Control+Shift+P"
        tool_input = {"key": key_combo}

        self._run_tool_async(tool_input) # Result not explicitly checked if formatting is same
        self.mock_keyboard.press.assert_called_once_with(key_combo)
        expected_msg = f'Pressed "{key_combo}" on the keyboard.'
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, expected_msg)


    def test_run_keyboard_press_raises_exception(self):
        key_to_press = "InvalidKey"
        error_message = "Invalid key name for press"
        self.mock_keyboard.press.side_effect = Exception(error_message)
        tool_input = {"key": key_to_press}

        result = self._run_tool_async(tool_input)

        self.mock_keyboard.press.assert_called_once_with(key_to_press)
        # Sleep is not called if press fails before it
        self.mock_async_sleep.assert_not_called()
        self.mock_browser.update_state.assert_not_called()
        self.mock_format_screenshot.assert_not_called()

        self.assertEqual(result.__class__.__name__, "ToolImplOutput") # Changed isinstance check
        self.assertEqual(result.tool_output, f"Failed to press key: {error_message}") # Changed to tool_output
        self.assertEqual(result.tool_result_message, "Failed to press key") # Changed to tool_result_message
        self.assertFalse(result.auxiliary_data["success"])
        self.assertEqual(result.auxiliary_data["error"], error_message)


if __name__ == "__main__":
    unittest.main()
