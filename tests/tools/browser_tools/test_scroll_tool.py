import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from src.ii_agent.tools.browser_tools.scroll import BrowserScrollDownTool, BrowserScrollUpTool
from src.ii_agent.browser.browser import Browser, BrowserPage, Keyboard, Mouse, Viewport, BrowserState # For type hinting and spec
from src.ii_agent.tools.base import ToolImplOutput
from src.ii_agent.tools.browser_tools import utils as browser_utils # To patch format_screenshot_tool_output

class CommonScrollToolTests(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock(spec=Browser)
        self.mock_page = MagicMock(spec=BrowserPage)
        self.mock_browser.get_current_page = AsyncMock(return_value=self.mock_page)

        self.mock_keyboard = MagicMock(spec=Keyboard)
        self.mock_keyboard.press = AsyncMock()
        self.mock_page.keyboard = self.mock_keyboard

        self.mock_mouse = MagicMock(spec=Mouse)
        self.mock_mouse.move = AsyncMock()
        self.mock_mouse.wheel = AsyncMock()
        self.mock_page.mouse = self.mock_mouse

        # Mock page.url attribute, used by is_pdf_url
        self.mock_page.url = "http://example.com/somepage"

        self.mock_browser_state = MagicMock(spec=BrowserState)
        self.mock_browser_state.screenshot = "scroll_screenshot_data"
        self.mock_browser_state.viewport = Viewport(width=800, height=600) # Example viewport
        self.mock_browser.get_state = MagicMock(return_value=self.mock_browser_state) # Sync method
        self.mock_browser.update_state = AsyncMock(return_value=self.mock_browser_state) # Async method

        self.sleep_patcher = patch('asyncio.sleep', new_callable=AsyncMock)
        self.mock_async_sleep = self.sleep_patcher.start()

        self.format_screenshot_patcher = patch('src.ii_agent.tools.browser_tools.utils.format_screenshot_tool_output')
        self.mock_format_screenshot = self.format_screenshot_patcher.start()
        self.mock_formatted_output = ToolImplOutput("formatted_scroll_llm", "formatted_scroll_user")
        self.mock_format_screenshot.return_value = self.mock_formatted_output

        # Patch is_pdf_url used by the scroll tools
        self.is_pdf_url_patcher = patch('src.ii_agent.tools.browser_tools.scroll.is_pdf_url')
        self.mock_is_pdf_url = self.is_pdf_url_patcher.start()


    def tearDown(self):
        self.sleep_patcher.stop()
        self.format_screenshot_patcher.stop()
        self.is_pdf_url_patcher.stop()

    def _run_tool_async(self, tool, tool_input=None): # tool_input is {} for these tools
        if tool_input is None:
            tool_input = {}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(tool._run(tool_input))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return result


class TestBrowserScrollDownTool(CommonScrollToolTests):
    def setUp(self):
        super().setUp()
        self.tool = BrowserScrollDownTool(browser=self.mock_browser)

    def test_run_scroll_down_not_pdf(self):
        self.mock_is_pdf_url.return_value = False # Simulate not a PDF page

        result = self._run_tool_async(self.tool)

        self.mock_is_pdf_url.assert_called_once_with(self.mock_page.url)
        self.mock_page.keyboard.press.assert_not_called()
        self.mock_mouse.move.assert_called_once_with(400, 300) # center of 800x600
        self.mock_mouse.wheel.assert_called_once_with(0, 600 * 0.8) # delta_y is positive
        self.assertEqual(self.mock_async_sleep.call_count, 2) # 0.1 after move, 0.1 after wheel
        self.mock_browser.update_state.assert_called_once()
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, "Scrolled page down")
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_scroll_down_is_pdf(self):
        self.mock_is_pdf_url.return_value = True # Simulate a PDF page

        result = self._run_tool_async(self.tool)

        self.mock_is_pdf_url.assert_called_once_with(self.mock_page.url)
        self.mock_page.keyboard.press.assert_called_once_with("PageDown")
        self.mock_mouse.move.assert_not_called()
        self.mock_mouse.wheel.assert_not_called()
        self.mock_async_sleep.assert_called_once_with(0.1) # Only one sleep for PDF path
        self.mock_browser.update_state.assert_called_once()
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, "Scrolled page down")


class TestBrowserScrollUpTool(CommonScrollToolTests):
    def setUp(self):
        super().setUp()
        self.tool = BrowserScrollUpTool(browser=self.mock_browser)

    def test_run_scroll_up_not_pdf(self):
        self.mock_is_pdf_url.return_value = False

        result = self._run_tool_async(self.tool)

        self.mock_is_pdf_url.assert_called_once_with(self.mock_page.url)
        self.mock_mouse.move.assert_called_once_with(400, 300)
        self.mock_mouse.wheel.assert_called_once_with(0, -600 * 0.8) # delta_y is negative
        self.assertEqual(self.mock_async_sleep.call_count, 2)
        self.mock_browser.update_state.assert_called_once()
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, "Scrolled page up")

    def test_run_scroll_up_is_pdf(self):
        self.mock_is_pdf_url.return_value = True

        result = self._run_tool_async(self.tool)

        self.mock_is_pdf_url.assert_called_once_with(self.mock_page.url)
        self.mock_page.keyboard.press.assert_called_once_with("PageUp")
        self.mock_mouse.move.assert_not_called()
        self.mock_mouse.wheel.assert_not_called()
        self.mock_async_sleep.assert_called_once_with(0.1)
        self.mock_browser.update_state.assert_called_once()
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, "Scrolled page up")


if __name__ == "__main__":
    unittest.main()
