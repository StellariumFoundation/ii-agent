import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import uuid
import logging

from src.ii_agent.agents.anthropic_fc import AnthropicFC, AGENT_INTERRUPT_MESSAGE, TOOL_RESULT_INTERRUPT_MESSAGE, AGENT_INTERRUPT_FAKE_MODEL_RSP, TOOL_CALL_INTERRUPT_FAKE_MODEL_RSP
from src.ii_agent.llm.base import LLMClient, TextResult, ToolCall, ToolCallParameters, AssistantContentBlock
from src.ii_agent.tools.tool_manager import AgentToolManager
from src.ii_agent.tools.base import LLMTool, ToolImplOutput
from src.ii_agent.llm.context_manager.base import ContextManager
from src.ii_agent.llm.message_history import MessageHistory
from src.ii_agent.utils import WorkspaceManager
from src.ii_agent.db.manager import DatabaseManager
from src.ii_agent.core.event import RealtimeEvent, EventType

# A simple mock tool for testing
class SimpleMockTool(LLMTool):
    name = "simple_tool"
    description = "A simple mock tool."
    input_schema = {"type": "object", "properties": {"arg": {"type": "string"}}}

    def run_impl(self, tool_input: dict, message_history: MessageHistory | None = None) -> ToolImplOutput:
        return ToolImplOutput(f"Result for {tool_input.get('arg')}", "User msg for simple_tool")


class TestAnthropicFCAgent(unittest.TestCase):
    def setUp(self):
        self.mock_llm_client = MagicMock(spec=LLMClient)
        self.mock_workspace_manager = MagicMock(spec=WorkspaceManager)
        self.mock_message_queue = MagicMock(spec=asyncio.Queue)
        self.mock_logger = MagicMock(spec=logging.Logger)
        self.mock_context_manager = MagicMock(spec=ContextManager)
        self.mock_db_manager = MagicMock(spec=DatabaseManager)
        self.mock_websocket = MagicMock() # spec=WebSocket if available, else MagicMock
        self.mock_websocket.send_json = AsyncMock()


        self.test_session_id = uuid.uuid4()
        self.system_prompt = "You are a helpful agent."
        self.tool_list = [SimpleMockTool()]

        # Patch DatabaseManager constructor
        self.db_manager_patcher = patch('src.ii_agent.agents.anthropic_fc.DatabaseManager', return_value=self.mock_db_manager)
        self.MockDatabaseManager = self.db_manager_patcher.start()

        # Patch AgentToolManager constructor and its methods
        self.agent_tool_manager_patcher = patch('src.ii_agent.agents.anthropic_fc.AgentToolManager')
        self.MockAgentToolManagerClass = self.agent_tool_manager_patcher.start()
        self.mock_tool_manager_instance = MagicMock(spec=AgentToolManager)
        self.MockAgentToolManagerClass.return_value = self.mock_tool_manager_instance
        # Set up mock tool manager methods needed
        self.mock_tool_manager_instance.get_tools.return_value = self.tool_list # For _validate_tool_parameters
        self.mock_tool_manager_instance.should_stop.return_value = False # Default


        self.agent = AnthropicFC(
            system_prompt=self.system_prompt,
            client=self.mock_llm_client,
            tools=self.tool_list,
            workspace_manager=self.mock_workspace_manager,
            message_queue=self.mock_message_queue,
            logger_for_agent_logs=self.mock_logger,
            context_manager=self.mock_context_manager,
            websocket=self.mock_websocket,
            session_id=self.test_session_id,
            interactive_mode=True
        )
        # AgentToolManager is created inside AnthropicFC.__init__
        # So, we re-assign self.mock_tool_manager_instance to the one created by the agent
        # if we need to check calls on the *actual* instance used by the agent.
        # Or, ensure the patched constructor returns *our* mock_tool_manager_instance.
        # The current setup with `return_value=self.mock_tool_manager_instance` for the class patch does this.


    def tearDown(self):
        self.db_manager_patcher.stop()
        self.agent_tool_manager_patcher.stop()

    def test_init(self):
        self.assertEqual(self.agent.system_prompt, self.system_prompt)
        self.assertIs(self.agent.client, self.mock_llm_client)
        self.MockAgentToolManagerClass.assert_called_once_with(
            tools=self.tool_list,
            logger_for_agent_logs=self.mock_logger,
            interactive_mode=True
        )
        self.assertIs(self.agent.tool_manager, self.mock_tool_manager_instance)
        self.assertIsInstance(self.agent.history, MessageHistory)

    @patch('src.ii_agent.agents.anthropic_fc.encode_image', return_value="base64_encoded_data")
    def test_run_agent_llm_text_response_no_tools(self, mock_encode_image):
        instruction = "Hello agent"
        # Mock LLM client to return a direct text response
        llm_response_text = "Hello user, how can I help?"
        self.mock_llm_client.generate.return_value = ([TextResult(text=llm_response_text)], {})

        # Use run_agent which calls run_impl internally
        # run_agent returns the output_for_llm part of ToolImplOutput
        result_str = self.agent.run_agent(instruction=instruction, files=None)

        self.mock_llm_client.generate.assert_called_once()
        self.mock_tool_manager_instance.run_tool.assert_not_called()
        self.assertEqual(result_str, llm_response_text)

        # Check history
        self.assertEqual(self.agent.history.get_messages()[-1].content[0].text, llm_response_text)
        # Check message queue for agent response
        self.mock_message_queue.put_nowait.assert_any_call(
            RealtimeEvent(type=EventType.AGENT_RESPONSE, content={"text": "Task completed"})
        )
        # Check user prompt in history
        self.assertEqual(self.agent.history.get_messages()[0].content[0].text, instruction)

    @patch('src.ii_agent.agents.anthropic_fc.encode_image')
    def test_run_agent_single_tool_call_success_then_text(self, mock_encode_image):
        instruction = "Use simple_tool with arg 'test'"

        tool_call_id = "tool_call_1"
        mock_llm_tool_call = ToolCall(tool_name="simple_tool", tool_input={"arg": "test"}, tool_call_id=tool_call_id)

        tool_result_text = "Result for test"
        self.mock_tool_manager_instance.run_tool.return_value = tool_result_text # run_tool returns string

        final_llm_response_text = "The tool ran and said: Result for test"

        self.mock_llm_client.generate.side_effect = [
            ([mock_llm_tool_call], {}), # First call: LLM asks to use tool
            ([TextResult(text=final_llm_response_text)], {}) # Second call: LLM gives final answer
        ]

        result_str = self.agent.run_agent(instruction=instruction)

        self.assertEqual(self.mock_llm_client.generate.call_count, 2)
        self.mock_tool_manager_instance.run_tool.assert_called_once()
        actual_tool_call_params = self.mock_tool_manager_instance.run_tool.call_args[0][0]
        self.assertEqual(actual_tool_call_params.tool_name, "simple_tool")
        self.assertEqual(actual_tool_call_params.tool_input, {"arg": "test"})

        self.assertEqual(result_str, final_llm_response_text)

        # Check message queue for tool call, tool result, and final agent response
        put_calls = self.mock_message_queue.put_nowait.call_args_list
        self.assertIn(call(RealtimeEvent(type=EventType.TOOL_CALL, content={'tool_call_id': tool_call_id, 'tool_name': 'simple_tool', 'tool_input': {'arg': 'test'}})), put_calls)
        self.assertIn(call(RealtimeEvent(type=EventType.TOOL_RESULT, content={'tool_call_id': tool_call_id, 'tool_name': 'simple_tool', 'result': tool_result_text})), put_calls)
        self.assertIn(call(RealtimeEvent(type=EventType.AGENT_RESPONSE, content={'text': 'Task completed'})), put_calls)

        # Check history
        history_msgs = self.agent.history.get_messages()
        self.assertIsInstance(history_msgs[-3].content[0], ToolCall) # LLM's tool call
        self.assertIsInstance(history_msgs[-2].content[0], ToolFormattedResult) # Result of tool call
        self.assertEqual(history_msgs[-2].content[0].tool_output, tool_result_text)
        self.assertIsInstance(history_msgs[-1].content[0], TextResult) # Final LLM response
        self.assertEqual(history_msgs[-1].content[0].text, final_llm_response_text)


    def test_run_agent_max_turns_exceeded(self):
        self.agent.max_turns = 1 # Set low for test
        instruction = "Loop forever"

        # Simulate LLM always calling a tool
        mock_llm_tool_call = ToolCall(tool_name="simple_tool", tool_input={"arg": "loop"}, tool_call_id="loop_call")
        self.mock_llm_client.generate.return_value = ([mock_llm_tool_call], {})
        self.mock_tool_manager_instance.run_tool.return_value = "Loop result"

        result_str = self.agent.run_agent(instruction=instruction)

        self.assertEqual(self.mock_llm_client.generate.call_count, 1) # Hits max_turns
        self.mock_tool_manager_instance.run_tool.assert_called_once()
        self.assertEqual(result_str, "Agent did not complete after max turns")
        self.mock_message_queue.put_nowait.assert_any_call(
            RealtimeEvent(type=EventType.AGENT_RESPONSE, content={'text': 'Agent did not complete after max turns'})
        )

    def test_cancel_agent_during_llm_call(self):
        instruction = "Long task"
        # Simulate agent being cancelled when LLM client is called
        def generate_side_effect(*args, **kwargs):
            self.agent.cancel() # Cancel the agent
            return ([TextResult(text="Should be interrupted.")], {})
        self.mock_llm_client.generate.side_effect = generate_side_effect

        result_str = self.agent.run_agent(instruction=instruction)

        self.assertTrue(self.agent.interrupted)
        self.assertEqual(result_str, AGENT_INTERRUPT_MESSAGE)
        # Check that a fake assistant turn for interruption was added
        last_history_msg_content = self.agent.history.get_messages()[-1].content[0].text
        self.assertEqual(last_history_msg_content, AGENT_INTERRUPT_FAKE_MODEL_RSP)


    def test_cancel_agent_during_tool_call(self):
        instruction = "Task with tool that gets interrupted"
        mock_llm_tool_call = ToolCall(tool_name="simple_tool", tool_input={"arg": "interrupt_me"}, tool_call_id="interrupt_call")
        self.mock_llm_client.generate.return_value = ([mock_llm_tool_call], {})

        def run_tool_side_effect(*args, **kwargs):
            self.agent.cancel() # Cancel during tool execution
            return "Tool almost finished"
        self.mock_tool_manager_instance.run_tool.side_effect = run_tool_side_effect

        result_str = self.agent.run_agent(instruction=instruction)

        self.assertTrue(self.agent.interrupted)
        self.assertEqual(result_str, TOOL_RESULT_INTERRUPT_MESSAGE)
        # Check history: tool result should be the interrupt message,
        # and a fake assistant turn for tool call interruption
        history_msgs = self.agent.history.get_messages()
        self.assertEqual(history_msgs[-2].content[0].tool_output, TOOL_RESULT_INTERRUPT_MESSAGE)
        self.assertEqual(history_msgs[-1].content[0].text, TOOL_CALL_INTERRUPT_FAKE_MODEL_RSP)


    def test_clear_method(self):
        self.agent.history.add_user_prompt("previous instruction")
        self.agent.interrupted = True

        self.agent.clear()

        self.assertEqual(len(self.agent.history.get_messages()), 0)
        self.assertFalse(self.agent.interrupted)

    # TODO: Test _process_messages, file attachments, tool validation errors

if __name__ == "__main__":
    unittest.main()
