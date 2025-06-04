import unittest
from unittest.mock import patch # Added patch
from pathlib import Path # Added Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker as sqlalchemy_sessionmaker # Alias to avoid confusion with db_models.Session
import uuid
from datetime import datetime, timedelta
import os # For managing test DB file if not purely in-memory for some reason

from src.ii_agent.db.manager import DatabaseManager
from src.ii_agent.db.models import Base, Session as DBSession, Event as DBEvent # Alias to avoid confusion
from src.ii_agent.core.event import EventType, RealtimeEvent


class TestDatabaseManager(unittest.TestCase):
    db_path = "test_events.db" # Can use :memory: for purely in-memory

    @classmethod
    def setUpClass(cls):
        # Use a temporary, unique database for each test class run if not using :memory: for every test.
        # For full isolation, :memory: in setUp is better.
        cls.engine = create_engine(f"sqlite:///:memory:") # Use in-memory for tests
        Base.metadata.create_all(cls.engine) # Ensure schema is created once for the class if needed

    def setUp(self):
        # For tests that need a fresh DB each time.
        # If create_all is in DatabaseManager.__init__, this might be redundant
        # unless we want to ensure a clean state for each test method specifically.
        # The current DatabaseManager.__init__ calls create_all.
        # We will create a new DatabaseManager (and thus new in-memory DB) for each test.

        # To ensure each test method has a truly isolated in-memory database,
        # we give DatabaseManager a unique db_path for each test, or ensure :memory: is fresh.
        # The simplest is to patch create_engine used by DatabaseManager.
        self.engine_patcher = patch('sqlalchemy.create_engine')
        self.mock_create_engine = self.engine_patcher.start()

        # This in-memory engine will be used by the DatabaseManager instance
        self.test_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.test_engine) # Create schema on this specific engine
        self.mock_create_engine.return_value = self.test_engine

        self.db_manager = DatabaseManager(db_path=":memory:") # Path arg is now just illustrative due to patch

    def tearDown(self):
        self.engine_patcher.stop()
        # For a file-based test DB, you might os.remove(self.db_path) here
        # For in-memory, it's discarded.

    def test_get_session_context_manager(self):
        with self.db_manager.get_session() as session:
            self.assertIsNotNone(session)
            # Try a simple query to ensure it's a working session
            count = session.query(DBSession).count()
            self.assertEqual(count, 0)

        # Test commit
        session_id = uuid.uuid4()
        with self.db_manager.get_session() as session:
            new_db_session = DBSession(id=session_id, workspace_dir="/test_commit")
            session.add(new_db_session)

        with self.db_manager.get_session() as session:
            retrieved = session.query(DBSession).filter_by(id=str(session_id)).first()
            self.assertIsNotNone(retrieved)

        # Test rollback
        session_id_rollback = uuid.uuid4()
        try:
            with self.db_manager.get_session() as session:
                new_db_session_rb = DBSession(id=session_id_rollback, workspace_dir="/test_rollback")
                session.add(new_db_session_rb)
                raise ValueError("Simulate error for rollback")
        except ValueError:
            pass # Expected error

        with self.db_manager.get_session() as session:
            retrieved_rb = session.query(DBSession).filter_by(id=str(session_id_rollback)).first()
            self.assertIsNone(retrieved_rb)


    def test_create_session(self):
        session_uuid = uuid.uuid4()
        workspace_path = Path("/my/workspace")
        device_id = "device_001"

        created_uuid, created_path = self.db_manager.create_session(session_uuid, workspace_path, device_id)
        self.assertEqual(created_uuid, session_uuid)
        self.assertEqual(created_path, workspace_path)

        with self.db_manager.get_session() as s:
            db_session = s.query(DBSession).filter(DBSession.id == str(session_uuid)).first()
            self.assertIsNotNone(db_session)
            self.assertEqual(db_session.workspace_dir, str(workspace_path))
            self.assertEqual(db_session.device_id, device_id)
            self.assertIsNotNone(db_session.created_at)

    def test_save_event_and_get_session_events(self):
        session_uuid = uuid.uuid4()
        self.db_manager.create_session(session_uuid, Path("/events/ws"))

        event1_content = {"type": "test", "data": "event1"}
        realtime_event1 = RealtimeEvent(type=EventType.USER_MESSAGE, content=event1_content)
        event1_uuid = self.db_manager.save_event(session_uuid, realtime_event1)
        self.assertIsInstance(event1_uuid, uuid.UUID)

        event2_content = {"status": "done"}
        realtime_event2 = RealtimeEvent(type=EventType.AGENT_RESPONSE, content=event2_content)
        self.db_manager.save_event(session_uuid, realtime_event2)

        events = self.db_manager.get_session_events(session_uuid)
        self.assertEqual(len(events), 2)

        # Assuming order by timestamp or insertion
        self.assertEqual(events[0].event_type, EventType.USER_MESSAGE.value)
        self.assertEqual(events[0].event_payload, realtime_event1.model_dump()) # RealtimeEvent is dumped
        self.assertEqual(events[1].event_type, EventType.AGENT_RESPONSE.value)
        self.assertEqual(events[1].event_payload, realtime_event2.model_dump())

    def test_get_session_by_id_workspace_device_id(self):
        session_uuid = uuid.uuid4()
        ws_path_str = "/path/to/ws_for_get"
        device_id_str = "get_device_test"
        self.db_manager.create_session(session_uuid, Path(ws_path_str), device_id_str)

        ret_by_id = self.db_manager.get_session_by_id(session_uuid)
        self.assertIsNotNone(ret_by_id)
        self.assertEqual(ret_by_id.id, str(session_uuid))

        ret_by_ws = self.db_manager.get_session_by_workspace(ws_path_str)
        self.assertIsNotNone(ret_by_ws)
        self.assertEqual(ret_by_ws.id, str(session_uuid))

        ret_by_device = self.db_manager.get_session_by_device_id(device_id_str)
        self.assertIsNotNone(ret_by_device)
        self.assertEqual(ret_by_device.id, str(session_uuid))

        self.assertIsNone(self.db_manager.get_session_by_id(uuid.uuid4())) # Non-existent
        self.assertIsNone(self.db_manager.get_session_by_workspace("/non/existent/ws"))
        self.assertIsNone(self.db_manager.get_session_by_device_id("no_such_device"))


    def test_delete_session_events(self):
        session_uuid = uuid.uuid4()
        self.db_manager.create_session(session_uuid, Path("/delete/events/ws"))
        self.db_manager.save_event(session_uuid, RealtimeEvent(type=EventType.USER_MESSAGE, content={}))

        events_before_delete = self.db_manager.get_session_events(session_uuid)
        self.assertEqual(len(events_before_delete), 1)

        self.db_manager.delete_session_events(session_uuid)
        events_after_delete = self.db_manager.get_session_events(session_uuid)
        self.assertEqual(len(events_after_delete), 0)

    def _add_event_with_timestamp(self, session_id_str, event_type_enum, timestamp, payload=None):
        # Helper to add event with specific timestamp for ordering tests
        if payload is None: payload = {}
        with self.db_manager.get_session() as s:
            # Create DBEvent directly to control timestamp precisely for testing
            # The save_event method uses RealtimeEvent and sets timestamp on DB commit.
            evt = DBEvent(session_id=session_id_str, event_type=event_type_enum.value, event_payload=payload)
            evt.timestamp = timestamp # Manually set timestamp
            s.add(evt)


    def test_delete_events_from_last_to_user_message(self):
        session_uuid = uuid.uuid4()
        session_id_str = str(session_uuid)
        self.db_manager.create_session(session_uuid, Path("/del_complex/ws"))

        # Timestamps for ordering
        t1 = datetime.utcnow() - timedelta(minutes=5)
        t2 = datetime.utcnow() - timedelta(minutes=4) # First USER_MESSAGE
        t3 = datetime.utcnow() - timedelta(minutes=3)
        t4 = datetime.utcnow() - timedelta(minutes=2) # Second (last) USER_MESSAGE
        t5 = datetime.utcnow() - timedelta(minutes=1)
        t6 = datetime.utcnow() # Last event

        self._add_event_with_timestamp(session_id_str, EventType.AGENT_THINKING, t1, {"thought": "1"})
        self._add_event_with_timestamp(session_id_str, EventType.USER_MESSAGE, t2, {"text": "User message 1"})
        self._add_event_with_timestamp(session_id_str, EventType.TOOL_CALL, t3, {"tool": "tool1"})
        self._add_event_with_timestamp(session_id_str, EventType.USER_MESSAGE, t4, {"text": "User message 2"}) # Last user message
        self._add_event_with_timestamp(session_id_str, EventType.AGENT_RESPONSE, t5, {"text": "Response"})
        self._add_event_with_timestamp(session_id_str, EventType.TOOL_RESULT, t6, {"result": "res"})

        all_events_before = self.db_manager.get_session_events(session_uuid)
        self.assertEqual(len(all_events_before), 6)

        self.db_manager.delete_events_from_last_to_user_message(session_uuid)

        events_after = self.db_manager.get_session_events(session_uuid)
        self.assertEqual(len(events_after), 3) # t1, t2, t3 should remain
        event_types_after = [e.event_payload['type'] for e in events_after] # Assuming payload has original RealtimeEvent structure

        # This check is tricky because payload is the model_dump of RealtimeEvent.
        # Let's check timestamps instead for more reliability here.
        timestamps_after = sorted([e.timestamp for e in events_after])
        self.assertEqual(timestamps_after, [t1,t2,t3])


    def test_delete_events_no_user_message(self):
        session_uuid = uuid.uuid4()
        session_id_str = str(session_uuid)
        self.db_manager.create_session(session_uuid, Path("/del_no_user/ws"))

        self._add_event_with_timestamp(session_id_str, EventType.AGENT_THINKING, datetime.utcnow())
        self._add_event_with_timestamp(session_id_str, EventType.TOOL_CALL, datetime.utcnow())

        self.db_manager.delete_events_from_last_to_user_message(session_uuid)
        events_after = self.db_manager.get_session_events(session_uuid)
        self.assertEqual(len(events_after), 0) # All deleted

    def test_delete_events_empty_history(self):
        session_uuid = uuid.uuid4()
        self.db_manager.create_session(session_uuid, Path("/del_empty/ws"))
        # No events added
        self.db_manager.delete_events_from_last_to_user_message(session_uuid)
        events_after = self.db_manager.get_session_events(session_uuid)
        self.assertEqual(len(events_after), 0)


if __name__ == "__main__":
    unittest.main()
