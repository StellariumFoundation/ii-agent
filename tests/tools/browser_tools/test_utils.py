import unittest
from src.ii_agent.tools.browser_tools.utils import format_screenshot_tool_output
from src.ii_agent.tools.base import ToolImplOutput

class TestBrowserUtils(unittest.TestCase):
    def test_format_screenshot_tool_output(self):
        screenshot_data = "base64_encoded_image_string"
        message_string = "This is a test message."

        result = format_screenshot_tool_output(screenshot_data, message_string)

        self.assertIsInstance(result, ToolImplOutput)

        # Check tool_output structure
        self.assertIsInstance(result.tool_output, list)
        self.assertEqual(len(result.tool_output), 2) # Should contain image and text dicts

        # Check image dictionary
        image_dict = result.tool_output[0]
        self.assertEqual(image_dict.get("type"), "image")
        self.assertIn("source", image_dict)
        image_source = image_dict["source"]
        self.assertEqual(image_source.get("type"), "base64")
        self.assertEqual(image_source.get("media_type"), "image/png")
        self.assertEqual(image_source.get("data"), screenshot_data)

        # Check text dictionary
        text_dict = result.tool_output[1]
        self.assertEqual(text_dict.get("type"), "text")
        self.assertEqual(text_dict.get("text"), message_string)

        # Check tool_result_message
        self.assertEqual(result.tool_result_message, message_string)

if __name__ == "__main__":
    unittest.main()
