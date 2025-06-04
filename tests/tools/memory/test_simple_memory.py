import unittest
from unittest.mock import MagicMock

from src.ii_agent.tools.memory.simple_memory import SimpleMemoryTool
from src.ii_agent.tools.base import ToolImplOutput

class TestSimpleMemoryTool(unittest.TestCase):
    def setUp(self):
        self.tool = SimpleMemoryTool()

    def test_initial_state(self):
        self.assertEqual(self.tool.full_memory, "")
        self.assertEqual(str(self.tool), "")

    # --- Test 'read' action ---
    def test_run_impl_read_empty_memory(self):
        tool_input = {"action": "read"}
        result = self.tool.run_impl(tool_input)
        self.assertIsInstance(result, ToolImplOutput)
        self.assertEqual(result.tool_output, "")
        self.assertEqual(result.tool_result_message, "Memory read successfully")
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_read_with_content(self):
        self.tool.full_memory = "Stored information."
        tool_input = {"action": "read"}
        result = self.tool.run_impl(tool_input)
        self.assertEqual(result.tool_output, "Stored information.")
        self.assertEqual(str(self.tool), "Stored information.") # Test __str__

    # --- Test 'write' action ---
    def test_run_impl_write_to_empty_memory(self):
        tool_input = {"action": "write", "content": "New memory content."}
        result = self.tool.run_impl(tool_input)
        self.assertEqual(self.tool.full_memory, "New memory content.")
        self.assertEqual(result.tool_output, "Memory updated successfully.")
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_write_overwriting_memory(self):
        self.tool.full_memory = "Old content."
        tool_input = {"action": "write", "content": "Fresh content."}
        result = self.tool.run_impl(tool_input)
        self.assertEqual(self.tool.full_memory, "Fresh content.")
        self.assertIn("Warning: Overwriting existing content.", result.tool_output)
        self.assertIn("Previous content was:\nOld content.", result.tool_output)
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_write_empty_content(self): # Effectively clears memory
        self.tool.full_memory = "To be cleared."
        tool_input = {"action": "write", "content": ""}
        result = self.tool.run_impl(tool_input)
        self.assertEqual(self.tool.full_memory, "")
        self.assertIn("Warning: Overwriting existing content.", result.tool_output) # Still warns
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_write_missing_content_param(self):
        # content defaults to "" if missing in tool_input.get("content", "")
        self.tool.full_memory = "Some data"
        tool_input = {"action": "write"} # Content missing
        result = self.tool.run_impl(tool_input)
        self.assertEqual(self.tool.full_memory, "") # Overwritten with empty string
        self.assertIn("Warning: Overwriting existing content.", result.tool_output)
        self.assertTrue(result.auxiliary_data["success"])


    # --- Test 'edit' action ---
    def test_run_impl_edit_success_unique_match(self):
        self.tool.full_memory = "The quick brown fox."
        tool_input = {"action": "edit", "old_string": "brown", "new_string": "red"}
        result = self.tool.run_impl(tool_input)
        self.assertEqual(self.tool.full_memory, "The quick red fox.")
        self.assertEqual(result.tool_output, "Edited memory: 1 occurrence replaced.")
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_edit_old_string_not_found(self):
        self.tool.full_memory = "Hello world."
        tool_input = {"action": "edit", "old_string": "galaxy", "new_string": "universe"}
        result = self.tool.run_impl(tool_input)
        self.assertEqual(self.tool.full_memory, "Hello world.") # No change
        self.assertEqual(result.tool_output, "Error: 'galaxy' not found in memory.")
        self.assertTrue(result.auxiliary_data["success"]) # The operation itself "completed" by returning info

    def test_run_impl_edit_multiple_occurrences(self):
        self.tool.full_memory = "apple apple pie."
        tool_input = {"action": "edit", "old_string": "apple", "new_string": "orange"}
        result = self.tool.run_impl(tool_input)
        self.assertEqual(self.tool.full_memory, "apple apple pie.") # No change
        self.assertIn("Warning: Found 2 occurrences of 'apple'.", result.tool_output)
        self.assertTrue(result.auxiliary_data["success"])

    def test_run_impl_edit_empty_old_string(self):
        # Behavior of string.count("") is len(string) + 1
        # Behavior of string.replace("", "x") inserts "x" between each char and at ends.
        # The tool's logic might lead to unexpected results or errors if old_string is empty.
        self.tool.full_memory = "abc"
        # old_string defaults to "" if missing in tool_input.get("old_string", "")
        tool_input = {"action": "edit", "new_string": "-"}
        result = self.tool.run_impl(tool_input)
        # Current code: count("") is 4. This will trigger "multiple occurrences" warning.
        self.assertIn("Warning: Found 4 occurrences of ''.", result.tool_output)
        self.assertEqual(self.tool.full_memory, "abc") # No change due to multiple occurrences rule

    def test_run_impl_edit_missing_new_string(self):
        self.tool.full_memory = "Remove this word."
        # new_string defaults to "" if missing
        tool_input = {"action": "edit", "old_string": " word"}
        result = self.tool.run_impl(tool_input)
        self.assertEqual(self.tool.full_memory, "Remove this.")
        self.assertEqual(result.tool_output, "Edited memory: 1 occurrence replaced.")


    # --- Test invalid action ---
    def test_run_impl_invalid_action(self):
        tool_input = {"action": "unknown_action"}
        result = self.tool.run_impl(tool_input)
        self.assertFalse(result.auxiliary_data["success"])
        self.assertEqual(result.tool_output, "Error: Unknown action 'unknown_action'. Valid actions are read, write, edit.")

if __name__ == "__main__":
    unittest.main()
