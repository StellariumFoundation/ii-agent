import unittest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import uuid
from datetime import datetime

from src.ii_agent.db.models import Base, Session as DBSession, Event as DBEvent, init_db

class TestDBModels(unittest.TestCase):

    def test_session_model_instantiation(self):
        session_id_uuid = uuid.uuid4()
        workspace_dir = "/test/workspace"
        device_id = "test_device_123"

        session = DBSession(id=session_id_uuid, workspace_dir=workspace_dir, device_id=device_id)

        self.assertIsInstance(session.id, str) # Should be converted to string
        self.assertEqual(session.id, str(session_id_uuid))
        self.assertEqual(session.workspace_dir, workspace_dir)
        self.assertEqual(session.device_id, device_id)
        self.assertIsInstance(session.created_at, datetime) # Default value
        self.assertIsNotNone(session.created_at)
        self.assertEqual(session.events, []) # Relationship initializes as empty list before DB commit

    def test_session_model_instantiation_optional_device_id(self):
        session_id_uuid = uuid.uuid4()
        workspace_dir = "/another/ws"

        session = DBSession(id=session_id_uuid, workspace_dir=workspace_dir) # device_id is None
        self.assertIsNone(session.device_id)


    def test_event_model_instantiation(self):
        session_id_uuid = uuid.uuid4()
        event_type = "test_event"
        event_payload = {"key": "value", "number": 123}

        event = DBEvent(session_id=session_id_uuid, event_type=event_type, event_payload=event_payload)

        self.assertIsInstance(event.id, str) # Default UUID string
        self.assertTrue(uuid.UUID(event.id)) # Check it's a valid UUID string
        self.assertIsInstance(event.session_id, str) # Should be converted to string
        self.assertEqual(event.session_id, str(session_id_uuid))
        self.assertEqual(event.event_type, event_type)
        self.assertEqual(event.event_payload, event_payload)
        self.assertIsInstance(event.timestamp, datetime) # Default value
        self.assertIsNotNone(event.timestamp)

        # session relationship will be None until committed and queried from a session
        self.assertIsNone(event.session)

    def test_init_db_creates_tables(self):
        # Use an in-memory SQLite database for this test
        engine = create_engine("sqlite:///:memory:")

        # Check tables before init_db
        inspector_before = inspect(engine)
        table_names_before = inspector_before.get_table_names()
        self.assertNotIn("session", table_names_before)
        self.assertNotIn("event", table_names_before)

        # Call init_db
        init_db(engine)

        # Check tables after init_db
        inspector_after = inspect(engine)
        table_names_after = inspector_after.get_table_names()
        self.assertIn("session", table_names_after)
        self.assertIn("event", table_names_after)

        # Optionally, check some column details for one table
        session_columns = {col['name'] for col in inspector_after.get_columns("session")}
        self.assertIn("id", session_columns)
        self.assertIn("workspace_dir", session_columns)
        self.assertIn("created_at", session_columns)
        self.assertIn("device_id", session_columns)


if __name__ == "__main__":
    unittest.main()
