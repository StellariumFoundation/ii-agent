import unittest
from unittest.mock import MagicMock, AsyncMock, patch, call
import asyncio
from playwright.async_api import Page, Keyboard # Added import

from src.ii_agent.tools.browser_tools.enter_text import BrowserEnterTextTool
from src.ii_agent.browser.browser import Browser # Removed BrowserPage, Keyboard
from src.ii_agent.tools.base import ToolImplOutput
from src.ii_agent.tools.browser_tools import utils as browser_utils


class TestBrowserEnterTextTool(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock(spec=Browser)
        self.mock_page = MagicMock(spec=Page) # Changed spec to Page
        self.mock_browser.get_current_page = AsyncMock(return_value=self.mock_page)

        self.mock_keyboard = MagicMock(spec=Keyboard) # Spec is now playwright's Keyboard
        self.mock_keyboard.press = AsyncMock()
        self.mock_keyboard.type = AsyncMock()
        self.mock_page.keyboard = self.mock_keyboard

        self.mock_browser_state = MagicMock()
        self.mock_browser_state.screenshot = "enter_text_screenshot"
        self.mock_browser.update_state = AsyncMock(return_value=self.mock_browser_state)

        self.tool = BrowserEnterTextTool(browser=self.mock_browser)

        self.sleep_patcher = patch('asyncio.sleep', new_callable=AsyncMock)
        self.mock_async_sleep = self.sleep_patcher.start()

        self.format_screenshot_patcher = patch('src.ii_agent.tools.browser_tools.enter_text.utils.format_screenshot_tool_output') # Patched at lookup
        self.mock_format_screenshot = self.format_screenshot_patcher.start()
        self.mock_formatted_output = ToolImplOutput("formatted_enter_text_llm", "formatted_enter_text_user")
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

    def test_run_enter_text_without_press_enter(self):
        text_to_enter = "Hello World"
        tool_input = {"text": text_to_enter} # press_enter defaults to False

        result = self._run_tool_async(tool_input)

        self.mock_browser.get_current_page.assert_called_once()

        expected_keyboard_press_calls = [
            call("ControlOrMeta+a"),
            call("Backspace")
        ]
        self.mock_keyboard.press.assert_has_calls(expected_keyboard_press_calls)
        # Ensure "Enter" was not part of the calls to press
        for c in self.mock_keyboard.press.call_args_list:
            self.assertNotEqual(c.args[0], "Enter")

        self.mock_keyboard.type.assert_called_once_with(text_to_enter)

        # Check sleep calls: one after Ctrl+A, one after Backspace
        # Total calls to sleep depend on whether press_enter is true
        self.assertEqual(self.mock_async_sleep.call_count, 2)
        self.mock_async_sleep.assert_any_call(0.1) # Both are 0.1s

        self.mock_browser.update_state.assert_called_once()
        expected_msg = f'Entered "{text_to_enter}" on the keyboard. Make sure to double check that the text was entered to where you intended.'
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, expected_msg)
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_enter_text_with_press_enter(self):
        text_to_enter = "Submit this!"
        tool_input = {"text": text_to_enter, "press_enter": True}

        result = self._run_tool_async(tool_input)

        expected_keyboard_press_calls = [
            call("ControlOrMeta+a"),
            call("Backspace"),
            call("Enter")
        ]
        self.mock_keyboard.press.assert_has_calls(expected_keyboard_press_calls, any_order=False) # Order matters here
        self.mock_keyboard.type.assert_called_once_with(text_to_enter)

        # Check sleep calls: 0.1, 0.1, then 2 after Enter
        self.assertEqual(self.mock_async_sleep.call_count, 3)
        self.mock_async_sleep.assert_has_calls([call(0.1), call(0.1), call(2)], any_order=False)

        self.mock_browser.update_state.assert_called_once()
        expected_msg = f'Entered "{text_to_enter}" on the keyboard. Make sure to double check that the text was entered to where you intended.'
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, expected_msg)
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_enter_empty_text(self):
        tool_input = {"text": ""} # Empty text, press_enter defaults to False
        self._run_tool_async(tool_input)

        self.mock_keyboard.type.assert_called_once_with("") # Should type empty string
        # Ctrl+A, Backspace should still be called
        self.mock_keyboard.press.assert_any_call("ControlOrMeta+a")
        self.mock_keyboard.press.assert_any_call("Backspace")

    def test_run_keyboard_type_raises_exception(self):
        self.mock_keyboard.type.side_effect = Exception("Keyboard type failed")
        tool_input = {"text": "this will fail"}

        with self.assertRaisesRegex(Exception, "Keyboard type failed"):
            self._run_tool_async(tool_input)

        self.mock_browser.update_state.assert_not_called() # Should not be called if error before it
        self.mock_format_screenshot.assert_not_called()

    def test_run_keyboard_press_raises_exception(self):
        self.mock_keyboard.press.side_effect = Exception("Keyboard press failed")
        tool_input = {"text": "this will fail on press"}

        # The first press is Ctrl+A
        with self.assertRaisesRegex(Exception, "Keyboard press failed"):
            self._run_tool_async(tool_input)

        self.mock_keyboard.type.assert_not_called() # Should fail before type
        self.mock_browser.update_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
