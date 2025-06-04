import unittest
from pydantic import ValidationError

from src.ii_agent.core.event import EventType, RealtimeEvent

class TestEventTypeEnum(unittest.TestCase):
    def test_event_type_members_exist(self):
        # Check a few key members
        self.assertIsNotNone(EventType.TOOL_CALL)
        self.assertIsNotNone(EventType.AGENT_RESPONSE)
        self.assertIsNotNone(EventType.USER_MESSAGE)
        self.assertIsNotNone(EventType.ERROR)
        self.assertIsNotNone(EventType.SYSTEM)

    def test_event_type_member_values(self):
        self.assertEqual(EventType.TOOL_CALL, "tool_call")
        self.assertEqual(EventType.AGENT_RESPONSE, "agent_response")
        self.assertEqual(EventType.PROCESSING, "processing")
        self.assertEqual(EventType.FILE_EDIT, "file_edit")

    def test_event_type_is_string_comparable(self):
        self.assertTrue(EventType.TOOL_CALL == "tool_call")
        self.assertFalse(EventType.TOOL_CALL == "tool_call_typo")

        # Check that all enum values are strings
        for event_type in EventType:
            self.assertIsInstance(event_type.value, str)

class TestRealtimeEventModel(unittest.TestCase):
    def test_successful_instantiation(self):
        event_type = EventType.AGENT_RESPONSE
        content_data = {"text": "Hello user!", "status": "complete"}

        event = RealtimeEvent(type=event_type, content=content_data)

        self.assertEqual(event.type, event_type)
        self.assertEqual(event.content, content_data)

    def test_instantiation_with_all_event_types(self):
        sample_content = {"data": "some_value"}
        for event_type_member in EventType:
            with self.subTest(event_type=event_type_member):
                event = RealtimeEvent(type=event_type_member, content=sample_content)
                self.assertEqual(event.type, event_type_member)
                self.assertEqual(event.content, sample_content)

    def test_validation_error_missing_type(self):
        with self.assertRaises(ValidationError) as context:
            RealtimeEvent(content={"data": "test"})
        # Check that 'type' is mentioned in the error details
        self.assertIn("'type'", str(context.exception).lower())
        self.assertIn("missing", str(context.exception).lower())


    def test_validation_error_missing_content(self):
        with self.assertRaises(ValidationError) as context:
            RealtimeEvent(type=EventType.SYSTEM)
        self.assertIn("'content'", str(context.exception).lower())
        self.assertIn("missing", str(context.exception).lower())


    def test_validation_error_invalid_type_value(self):
        with self.assertRaises(ValidationError) as context:
            RealtimeEvent(type="not_a_real_event_type", content={"data": "test"})
        # Pydantic error message for enums can be detailed
        self.assertIn("Input tag 'not_a_real_event_type' found using 'str_constrained'", str(context.exception))

    def test_validation_error_content_not_a_dict(self):
        with self.assertRaises(ValidationError) as context:
            RealtimeEvent(type=EventType.TOOL_RESULT, content="just a string")
        self.assertIn("Input should be a valid dictionary", str(context.exception))

    def test_model_dump_serialization(self):
        event_type = EventType.TOOL_CALL
        content_data = {"tool_name": "calculator", "tool_input": {"x": 1, "y": 2}}
        event = RealtimeEvent(type=event_type, content=content_data)

        dumped_event = event.model_dump()

        expected_dump = {
            "type": "tool_call", # Enum member should be dumped as its string value
            "content": content_data
        }
        self.assertEqual(dumped_event, expected_dump)

    def test_model_validate_deserialization(self):
        raw_data = {
            "type": "tool_result", # String value for EventType
            "content": {"result": "3", "status": "success"}
        }

        event = RealtimeEvent.model_validate(raw_data)

        self.assertEqual(event.type, EventType.TOOL_RESULT) # Should be converted to Enum member
        self.assertEqual(event.content, {"result": "3", "status": "success"})

    def test_model_validate_deserialization_invalid_type_string(self):
        raw_data = {
            "type": "invalid_event_name_for_sure",
            "content": {"data": "test"}
        }
        with self.assertRaises(ValidationError):
            RealtimeEvent.model_validate(raw_data)


if __name__ == "__main__":
    unittest.main()
