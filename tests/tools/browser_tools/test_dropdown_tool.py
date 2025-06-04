import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
import json # For formatting options in BrowserGetSelectOptionsTool output
from playwright.async_api import Page # Added import

from src.ii_agent.tools.browser_tools.dropdown import BrowserGetSelectOptionsTool, BrowserSelectDropdownOptionTool
from src.ii_agent.browser.browser import Browser # Removed BrowserPage, BrowserState, InteractiveElement
from src.ii_agent.browser.models import BrowserState, InteractiveElement, Coordinates, Rect # Added import for these, and Coordinates, Rect
from src.ii_agent.tools.base import ToolImplOutput
from src.ii_agent.tools.browser_tools import utils as browser_utils


class CommonDropdownToolTests(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock(spec=Browser)
        self.mock_page = MagicMock(spec=Page) # Changed spec to Page
        self.mock_browser.get_current_page = AsyncMock(return_value=self.mock_page)

        self.mock_state = MagicMock(spec=BrowserState) # This should be fine as BrowserState is now correctly imported
        self.mock_state.interactive_elements = {} # Will be populated by tests
        self.mock_state.screenshot = "dropdown_screenshot_data"
        self.mock_browser.get_state = MagicMock(return_value=self.mock_state) # Sync method
        self.mock_browser.update_state = AsyncMock(return_value=self.mock_state) # Async method

        self.mock_page.evaluate = AsyncMock()

        self.format_screenshot_patcher = patch('src.ii_agent.tools.browser_tools.dropdown.utils.format_screenshot_tool_output') # Patched at lookup
        self.mock_format_screenshot = self.format_screenshot_patcher.start()
        self.mock_formatted_output = ToolImplOutput("formatted_dropdown_llm", "formatted_dropdown_user")
        self.mock_format_screenshot.return_value = self.mock_formatted_output

    def tearDown(self):
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

class TestBrowserGetSelectOptionsTool(CommonDropdownToolTests):
    def setUp(self):
        super().setUp()
        self.tool = BrowserGetSelectOptionsTool(browser=self.mock_browser)

    def test_run_get_options_success(self):
        element_index = 1
        element_agent_id = "select-agent-id-123"
        # Provided all required fields for InteractiveElement
        mock_select_element = InteractiveElement(
            index=element_index,
            tag_name="select",
            text="Option 1", # Default text, or text of selected option
            attributes={},
            viewport=MagicMock(spec=Coordinates),
            page=MagicMock(spec=Coordinates),
            center=MagicMock(spec=Coordinates),
            weight=1.0,
            browser_agent_id=element_agent_id,
            rect=MagicMock(spec=Rect),
            z_index=0,
            # aria_label, role, text_content, html_attributes are not direct model fields but used for setup logic
        )
        self.mock_state.interactive_elements = {element_index: mock_select_element}

        js_return_value = {
            "options": [
                {"text": "Option 1", "value": "val1", "index": 0},
                {"text": "Option 2", "value": "val2", "index": 1},
            ],
            "id": "select_id", "name": "select_name"
        }
        self.mock_page.evaluate.return_value = js_return_value

        result = self._run_tool_async(self.tool, {"index": element_index})

        self.mock_browser.get_current_page.assert_called_once()
        self.mock_browser.get_state.assert_called_once() # Called to get interactive_elements
        self.mock_page.evaluate.assert_called_once()
        js_call_args = self.mock_page.evaluate.call_args[0][1] # Second arg of evaluate call
        self.assertEqual(js_call_args["browserAgentId"], element_agent_id)

        expected_msg_lines = [
            '0: option="Option 1"',
            '1: option="Option 2"',
            "If you decide to use this select element, use the exact option name in select_dropdown_option"
        ]
        # The format_screenshot_tool_output is mocked, so we check what was passed to it
        passed_msg_to_formatter = self.mock_format_screenshot.call_args[0][1]
        for line in expected_msg_lines:
            self.assertIn(line, passed_msg_to_formatter)

        self.mock_browser.update_state.assert_called_once() # Called after getting options
        self.assertEqual(result, self.mock_formatted_output)

    def test_run_get_options_element_not_found(self):
        result = self._run_tool_async(self.tool, {"index": 99}) # Index not in interactive_elements
        self.assertEqual(result.tool_output, "No element found with index 99") # Changed to tool_output
        self.mock_page.evaluate.assert_not_called()

    def test_run_get_options_element_not_select(self):
        element_index = 2
        # Provided all required fields for InteractiveElement
        mock_button_element = InteractiveElement(
            index=element_index,
            tag_name="button",
            text="Click Me", # Example text
            attributes={},
            viewport=MagicMock(spec=Coordinates), # Mocking Coordinates
            page=MagicMock(spec=Coordinates), # Mocking Coordinates
            center=MagicMock(spec=Coordinates), # Mocking Coordinates
            weight=1.0,
            browser_agent_id="btn-id",
            rect=MagicMock(spec=Rect), # Mocking Rect
            z_index=0
            # aria_label, role, text_content, html_attributes are for test setup, not direct model fields
        )
        self.mock_state.interactive_elements = {element_index: mock_button_element}

        result = self._run_tool_async(self.tool, {"index": element_index})
        self.assertEqual(result.tool_output, f"Element {element_index} is not a select element, it's a button") # Changed to tool_output
        self.mock_page.evaluate.assert_not_called()


class TestBrowserSelectDropdownOptionTool(CommonDropdownToolTests):
    def setUp(self):
        super().setUp()
        self.tool = BrowserSelectDropdownOptionTool(browser=self.mock_browser)

    def test_run_select_option_success(self):
        element_index = 3
        element_agent_id = "select-agent-id-456"
        option_to_select = "Choose Me"

        # Provided all required fields for InteractiveElement
        mock_select_element = InteractiveElement(
            index=element_index,
            tag_name="select",
            text=option_to_select, # Default text, or text of selected option
            attributes={},
            viewport=MagicMock(spec=Coordinates),
            page=MagicMock(spec=Coordinates),
            center=MagicMock(spec=Coordinates),
            weight=1.0,
            browser_agent_id=element_agent_id,
            rect=MagicMock(spec=Rect),
            z_index=0
        )
        self.mock_state.interactive_elements = {element_index: mock_select_element}

        js_return_value = {"success": True, "value": "chosen_val", "index": 1}
        self.mock_page.evaluate.return_value = js_return_value

        tool_input = {"index": element_index, "option": option_to_select}
        result = self._run_tool_async(self.tool, tool_input)

        self.mock_page.evaluate.assert_called_once()
        js_call_args = self.mock_page.evaluate.call_args[0][1]
        self.assertEqual(js_call_args["uniqueId"], element_agent_id)
        self.assertEqual(js_call_args["optionText"], option_to_select)

        expected_msg = f"Selected option '{option_to_select}' with value 'chosen_val' at index 1"
        self.mock_format_screenshot.assert_called_once_with(self.mock_state.screenshot, expected_msg)
        self.assertEqual(result, self.mock_formatted_output)
        self.mock_browser.update_state.assert_called_once()


    def test_run_select_option_js_returns_failure_option_not_found(self):
        element_index = 4
        element_agent_id = "select-agent-id-789"
        # Provided all required fields for InteractiveElement
        mock_select_element = InteractiveElement(
            index=element_index,
            tag_name="select",
            text="OptA", # Example initial text
            attributes={},
            viewport=MagicMock(spec=Coordinates),
            page=MagicMock(spec=Coordinates),
            center=MagicMock(spec=Coordinates),
            weight=1.0,
            browser_agent_id=element_agent_id,
            rect=MagicMock(spec=Rect),
            z_index=0
        )
        self.mock_state.interactive_elements = {element_index: mock_select_element}

        js_error_msg = "Option not found: NonExistentOption"
        js_available_options = ["OptA", "OptB"]
        js_return_value = {"success": False, "error": js_error_msg, "availableOptions": js_available_options}
        self.mock_page.evaluate.return_value = js_return_value

        tool_input = {"index": element_index, "option": "NonExistentOption"}
        result = self._run_tool_async(self.tool, tool_input)

        expected_llm_output = f"{js_error_msg}. Available options: {', '.join(js_available_options)}"
        self.assertEqual(result.tool_output, expected_llm_output) # Changed to tool_output
        self.mock_format_screenshot.assert_not_called() # No success screenshot

    def test_run_select_option_element_not_found_in_state(self):
        result = self._run_tool_async(self.tool, {"index": 100, "option": "Any"})
        self.assertEqual(result.tool_output, "No element found with index 100") # Changed to tool_output

    def test_run_select_option_element_not_select_tag(self):
        element_index = 5
        # Provided all required fields for InteractiveElement
        mock_input_element = InteractiveElement( # Changed from mock_button_element to mock_input_element
            index=element_index,
            tag_name="input", # Ensuring it's an input for the test logic
            text="", # Example text
            attributes={},
            viewport=MagicMock(spec=Coordinates),
            page=MagicMock(spec=Coordinates),
            center=MagicMock(spec=Coordinates),
            weight=1.0,
            browser_agent_id="input-id", # Ensuring consistent ID if needed
            rect=MagicMock(spec=Rect),
            z_index=0,
            input_type="text" # Clarifying it's a text input
        )
        self.mock_state.interactive_elements = {element_index: mock_input_element} # Correctly using mock_input_element

        result = self._run_tool_async(self.tool, {"index": element_index, "option": "Any"})
        self.assertEqual(result.tool_output, f"Element {element_index} is not a select element, it's a input") # Changed to tool_output


if __name__ == "__main__":
    unittest.main()
