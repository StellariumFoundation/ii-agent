import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from src.ii_agent.tools.browser_tools.view import BrowserViewTool
from src.ii_agent.browser.browser import Browser # BrowserState, InteractiveElement removed
from src.ii_agent.browser.models import BrowserState, InteractiveElement, Coordinates, Rect # Added import for models, and Coordinates, Rect
from src.ii_agent.tools.base import ToolImplOutput
from src.ii_agent.tools.browser_tools import utils as browser_utils
import asyncio


class TestBrowserViewTool(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock(spec=Browser)

        self.mock_browser_state = MagicMock(spec=BrowserState)
        self.mock_browser_state.url = "http://example.com/current_page"
        self.mock_browser_state.screenshot_with_highlights = "view_tool_highlighted_screenshot"
        self.mock_browser_state.interactive_elements = {} # Default to no elements

        self.mock_browser.update_state = AsyncMock(return_value=self.mock_browser_state)

        self.tool = BrowserViewTool(browser=self.mock_browser)

        self.format_screenshot_patcher = patch('src.ii_agent.tools.browser_tools.view.utils.format_screenshot_tool_output') # Patched at lookup
        self.mock_format_screenshot = self.format_screenshot_patcher.start()
        self.mock_formatted_output = ToolImplOutput("formatted_view_llm", "formatted_view_user")
        self.mock_format_screenshot.return_value = self.mock_formatted_output

    def tearDown(self):
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

    def test_run_view_with_interactive_elements(self):
        # Setup interactive elements
        mock_element1 = InteractiveElement(
            index=0, tag_name="button", text="Click Me", attributes={},
            viewport=MagicMock(spec=Coordinates), page=MagicMock(spec=Coordinates), center=MagicMock(spec=Coordinates),
            weight=1.0, browser_agent_id="btn1", rect=MagicMock(spec=Rect), z_index=0, input_type=None
        )
        mock_element2 = InteractiveElement(
            index=1, tag_name="input", text="User\nName", attributes={},
            viewport=MagicMock(spec=Coordinates), page=MagicMock(spec=Coordinates), center=MagicMock(spec=Coordinates),
            weight=1.0, browser_agent_id="input1", rect=MagicMock(spec=Rect), z_index=0, input_type="text"
        )
        mock_element3 = InteractiveElement(
            index=2, tag_name="a", text="Link", attributes={"href":"#"},
            viewport=MagicMock(spec=Coordinates), page=MagicMock(spec=Coordinates), center=MagicMock(spec=Coordinates),
            weight=1.0, browser_agent_id="link1", rect=MagicMock(spec=Rect), z_index=0, input_type=None
        )

        self.mock_browser_state.interactive_elements = {
            0: mock_element1,
            1: mock_element2,
            2: mock_element3,
        }

        result = self._run_tool_async()

        self.mock_browser.update_state.assert_called_once()

        # Verify the message passed to the formatter
        passed_msg_to_formatter = self.mock_format_screenshot.call_args[0][1]

        self.assertIn(f"Current URL: {self.mock_browser_state.url}", passed_msg_to_formatter)
        self.assertIn("<highlighted_elements>", passed_msg_to_formatter)
        self.assertIn("[0]<button>Click Me</button>", passed_msg_to_formatter)
        self.assertIn('[1]<input type="text">User Name</input>', passed_msg_to_formatter) # Newline in text replaced by space
        self.assertIn("[2]<a>Link</a>", passed_msg_to_formatter)
        self.assertIn("</highlighted_elements>", passed_msg_to_formatter)

        self.mock_format_screenshot.assert_called_once_with(
            self.mock_browser_state.screenshot_with_highlights,
            unittest.mock.ANY # Already checked the message content
        )
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_view_no_interactive_elements(self):
        self.mock_browser_state.interactive_elements = {} # No elements

        result = self._run_tool_async()

        self.mock_browser.update_state.assert_called_once()
        passed_msg_to_formatter = self.mock_format_screenshot.call_args[0][1]

        self.assertIn(f"Current URL: {self.mock_browser_state.url}", passed_msg_to_formatter)
        # Check for empty highlighted elements tag
        self.assertIn("<highlighted_elements>\n</highlighted_elements>", passed_msg_to_formatter)

        self.assertEqual(result, self.mock_formatted_output)

    def test_run_view_update_state_fails(self):
        self.mock_browser.update_state.side_effect = Exception("Failed to update state")

        with self.assertRaisesRegex(Exception, "Failed to update state"):
            self._run_tool_async()

        self.mock_format_screenshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
