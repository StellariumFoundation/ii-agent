import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from src.ii_agent.tools.browser_tools.click import BrowserClickTool
from src.ii_agent.browser.browser import Browser, BrowserPage, Mouse # For type hinting and spec
from src.ii_agent.tools.base import ToolImplOutput
from src.ii_agent.tools.browser_tools import utils as browser_utils # To patch format_screenshot_tool_output

class TestBrowserClickTool(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock(spec=Browser)

        # Mock browser.get_current_page() to return a mock page
        self.mock_page = MagicMock(spec=BrowserPage)
        self.mock_browser.get_current_page = AsyncMock(return_value=self.mock_page)

        # Mock page.mouse.click()
        self.mock_mouse_click = AsyncMock()
        self.mock_page.mouse = MagicMock(spec=Mouse)
        self.mock_page.mouse.click = self.mock_mouse_click

        # Mock browser.context.pages for tab handling
        self.mock_browser.context = MagicMock()
        self.initial_pages_list = [MagicMock()] # Start with one page
        self.mock_browser.context.pages = self.initial_pages_list

        self.mock_browser.switch_to_tab = AsyncMock()

        # Mock browser.update_state() to return a state with a screenshot
        self.mock_browser_state = MagicMock()
        self.mock_browser_state.screenshot = "base64_screenshot_data"
        self.mock_browser.update_state = AsyncMock(return_value=self.mock_browser_state)

        self.mock_browser.handle_pdf_url_navigation = AsyncMock(return_value=self.mock_browser_state) # Returns updated state

        self.tool = BrowserClickTool(browser=self.mock_browser)

        # Patch asyncio.sleep
        self.sleep_patcher = patch('asyncio.sleep', new_callable=AsyncMock)
        self.mock_async_sleep = self.sleep_patcher.start()

        # Patch the formatting utility
        self.format_screenshot_patcher = patch('src.ii_agent.tools.browser_tools.utils.format_screenshot_tool_output')
        self.mock_format_screenshot = self.format_screenshot_patcher.start()
        # Make it return a distinctive value for easy assertion
        self.mock_formatted_output = ToolImplOutput("formatted_output_llm", "formatted_user_msg")
        self.mock_format_screenshot.return_value = self.mock_formatted_output


    def tearDown(self):
        self.sleep_patcher.stop()
        self.format_screenshot_patcher.stop()

    def _run_tool_async(self, tool_input):
        # Helper to run the async _run method
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # We are testing _run directly as run_impl just invokes it
            result = loop.run_until_complete(self.tool._run(tool_input))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return result

    def test_run_click_success_no_new_tab(self):
        tool_input = {"coordinate_x": 100, "coordinate_y": 200}
        result = self._run_tool_async(tool_input)

        self.mock_browser.get_current_page.assert_called_once()
        self.mock_mouse_click.assert_called_once_with(100, 200)
        self.mock_async_sleep.assert_any_call(1) # First sleep after click
        self.mock_browser.switch_to_tab.assert_not_called() # No new tab
        self.mock_browser.update_state.assert_called_once()
        self.mock_browser.handle_pdf_url_navigation.assert_called_once()

        expected_msg = "Clicked at coordinates 100, 200"
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, expected_msg)
        self.assertEqual(result, self.mock_formatted_output)


    def test_run_click_success_new_tab_opens(self):
        tool_input = {"coordinate_x": 50, "coordinate_y": 60}

        # Simulate new tab opening
        def simulate_new_tab(*args, **kwargs):
            self.mock_browser.context.pages.append(MagicMock()) # Add a "new page"
        self.mock_mouse_click.side_effect = simulate_new_tab

        result = self._run_tool_async(tool_input)

        self.mock_mouse_click.assert_called_once_with(50, 60)
        self.mock_browser.switch_to_tab.assert_called_once_with(-1)
        self.mock_async_sleep.assert_any_call(0.1) # Second sleep after tab switch

        expected_msg = "Clicked at coordinates 50, 60 - New tab opened - switching to it"
        self.mock_format_screenshot.assert_called_once_with(self.mock_browser_state.screenshot, expected_msg)
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_missing_coordinates(self):
        result_x_missing = self._run_tool_async({"coordinate_y": 100})
        self.assertEqual(result_x_missing.output_for_llm, "Must provide both coordinate_x and coordinate_y to click on an element")

        result_y_missing = self._run_tool_async({"coordinate_x": 100})
        self.assertEqual(result_y_missing.output_for_llm, "Must provide both coordinate_x and coordinate_y to click on an element")

        self.mock_mouse_click.assert_not_called()

    def test_run_mouse_click_raises_exception(self):
        self.mock_mouse_click.side_effect = Exception("Playwright click failed")
        tool_input = {"coordinate_x": 10, "coordinate_y": 20}

        with self.assertRaisesRegex(Exception, "Playwright click failed"):
            self._run_tool_async(tool_input)

        # Ensure that update_state etc. are not called if click fails
        self.mock_browser.update_state.assert_not_called()
        self.mock_format_screenshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
