import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

# Import the base class and utility to be tested
from src.ii_agent.tools.browser_tools.base import BrowserTool, get_event_loop
from src.ii_agent.browser.browser import Browser # For type hinting Browser
from src.ii_agent.tools.base import ToolImplOutput # For expected return type

# A concrete implementation for testing purposes, or we can mock _run directly
class ConcreteBrowserTool(BrowserTool):
    name = "concrete_browser_tool" # LLMTool requires a name
    description = "concrete"
    input_schema = {}

    def __init__(self, browser: Browser):
        super().__init__(browser)
        # Mock the async _run method for this test instance
        self._run = AsyncMock(return_value=ToolImplOutput("async run output", "async user output"))

class TestBrowserToolBase(unittest.TestCase):
    def setUp(self):
        self.mock_browser_instance = MagicMock(spec=Browser)

    def test_init(self):
        tool = BrowserTool(browser=self.mock_browser_instance)
        self.assertIs(tool.browser, self.mock_browser_instance)

    def test_run_impl_calls_async_run(self):
        # Use the ConcreteBrowserTool which has _run mocked
        concrete_tool = ConcreteBrowserTool(browser=self.mock_browser_instance)

        tool_input_dict = {"param": "value"}
        mock_message_history = MagicMock() # Not used by _run in this mock

        # Ensure an event loop is available for run_until_complete
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = concrete_tool.run_impl(tool_input_dict, message_history=mock_message_history)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        # Check that the async _run method was called
        concrete_tool._run.assert_called_once_with(tool_input_dict, mock_message_history)

        # Check that the result from _run is returned by run_impl
        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.tool_output, "async run output") # Changed output_for_llm to tool_output

    def test_run_impl_when_run_is_not_implemented_in_subclass(self):
        # Test the abstract nature of _run
        # Create a direct instance of BrowserTool (if not prevented by abstract checks)
        # or a subclass that doesn't implement _run
        class AbstractSubclass(BrowserTool):
            name = "abstract_sub"
            description = "sub"
            input_schema = {}
            # No _run method

        tool = AbstractSubclass(browser=self.mock_browser_instance)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with self.assertRaises(NotImplementedError):
                tool.run_impl({}, None)
        finally:
            loop.close()
            asyncio.set_event_loop(None)


    # Tests for get_event_loop (similar to those in DeepResearchTool tests)
    def test_get_event_loop_creates_new_if_none(self):
        asyncio.set_event_loop(None) # Ensure no loop is set
        loop = get_event_loop()
        self.assertIsNotNone(loop)
        # A new loop might not be running yet, but it shouldn't be closed.
        self.assertFalse(loop.is_closed())
        # Clean up
        asyncio.set_event_loop(loop) # Set it to be able to close it
        loop.close()
        asyncio.set_event_loop(None) # Clear it again

    def test_get_event_loop_returns_existing(self):
        existing_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(existing_loop)

        returned_loop = get_event_loop()
        self.assertIs(returned_loop, existing_loop)

        existing_loop.close()
        asyncio.set_event_loop(None)


if __name__ == "__main__":
    unittest.main()
