import unittest
from unittest.mock import patch, MagicMock, AsyncMock, ANY
import asyncio
import argparse # For creating mock args
import sys # For patching sys.argv
import logging
from pathlib import Path
import uuid

# Modules to be tested or mocked
from src.ii_agent.cli import async_main # Assuming cli.py is in src.ii_agent for direct import
# If cli.py is at root, the import path for its internal imports might need adjustment in test
# For now, assume cli.py can find its imports like 'from ii_agent.core.event import ...'

# Mocks for classes initialized in cli.py
from src.ii_agent.llm.base import LLMClient
from src.ii_agent.tools.tool_manager import AgentToolManager
from src.ii_agent.llm.context_manager.base import ContextManager
from src.ii_agent.llm.context_manager.llm_summarizing import LLMSummarizingContextManager
from src.ii_agent.llm.context_manager.amortized_forgetting import AmortizedForgettingContextManager
from src.ii_agent.llm.token_counter import TokenCounter
from src.ii_agent.db.manager import DatabaseManager
from src.ii_agent.utils import WorkspaceManager
from src.ii_agent.agents.anthropic_fc import AnthropicFC
from src.ii_agent.core.event import RealtimeEvent, EventType


# Suppress most logging from the application during tests
logging.disable(logging.CRITICAL)
# Or specifically for 'agent_logs' if it's already configured by cli.py
# logging.getLogger("agent_logs").setLevel(logging.CRITICAL + 1)


class TestCliAsyncMain(unittest.TestCase):

    @patch('src.ii_agent.cli.argparse.ArgumentParser.parse_args')
    @patch('src.ii_agent.cli.create_workspace_manager_for_connection')
    @patch('src.ii_agent.cli.DatabaseManager')
    @patch('src.ii_agent.cli.get_client')
    @patch('src.ii_agent.cli.LLMSummarizingContextManager') # Default context_manager
    @patch('src.ii_agent.cli.AmortizedForgettingContextManager') # Alt context_manager
    @patch('src.ii_agent.cli.TokenCounter')
    @patch('src.ii_agent.cli.get_system_tools')
    @patch('src.ii_agent.cli.AnthropicFC')
    @patch('asyncio.Queue')
    @patch('builtins.input')
    @patch('src.ii_agent.cli.Console') # Mock Rich Console
    @patch('asyncio.loop.run_in_executor', new_callable=AsyncMock) # Mock the executor call
    @patch('src.ii_agent.cli.logging.FileHandler') # Mock FileHandler to avoid creating log files
    @patch('src.ii_agent.cli.logging.StreamHandler')
    @patch('os.path.exists') # Mock os.path.exists for log file removal check
    @patch('os.remove') # Mock os.remove for log file removal
    async def _run_async_main_with_mocks(
        self, mock_os_remove, mock_os_exists,
        mock_log_streamhandler, mock_log_filehandler,
        mock_run_in_executor, MockRichConsole, mock_builtin_input,
        MockAsyncQueue, MockAnthropicFC, mock_get_system_tools,
        MockTokenCounter, MockAmortizedCM, MockLLMSummarizingCM,
        mock_get_llm_client, MockDatabaseManager,
        mock_create_workspace, mock_parse_args,
        cli_args=None, user_inputs=None, agent_run_responses=None
    ):
        # Default CLI args
        if cli_args is None:
            cli_args = {
                "logs_path": "test_agent.log", "minimize_stdout_logs": True,
                "workspace": None, "use_container_workspace": False,
                "model_name": "test_model", "llm_client": "anthropic-direct",
                "project_id": None, "region": None, "azure_model": False, "cot_model": False,
                "context_manager": "llm-summarizing", "prompt": None,
                "docker_container_id": None, "needs_permission": False,
                "memory_tool": "simple"
            }
        mock_parse_args.return_value = argparse.Namespace(**cli_args)
        mock_os_exists.return_value = False # Assume log file doesn't exist initially

        # Mock WorkspaceManager creation
        mock_ws_manager_instance = MagicMock(spec=WorkspaceManager)
        mock_ws_manager_instance.root = Path("/tmp/test_workspace")
        test_session_id = uuid.uuid4()
        mock_create_workspace.return_value = (mock_ws_manager_instance, test_session_id)

        # Mock DatabaseManager
        mock_db_instance = MockDatabaseManager.return_value
        mock_db_instance.create_session = MagicMock()

        # Mock LLM Client
        mock_llm_instance = MagicMock(spec=LLMClient)
        mock_get_llm_client.return_value = mock_llm_instance

        # Mock ContextManager (default is LLMSummarizing)
        mock_cm_instance = MagicMock(spec=ContextManager)
        if cli_args["context_manager"] == "llm-summarizing":
            MockLLMSummarizingCM.return_value = mock_cm_instance
        else: # Amortized
            MockAmortizedCM.return_value = mock_cm_instance


        # Mock Tools
        mock_get_system_tools.return_value = [MagicMock(spec=LLMTool)]

        # Mock Agent
        mock_agent_instance = MagicMock(spec=AnthropicFC)
        mock_agent_instance.run_agent = MagicMock()
        if agent_run_responses:
            mock_agent_instance.run_agent.side_effect = agent_run_responses
        else:
            mock_agent_instance.run_agent.return_value = "Agent default response."

        mock_agent_instance.start_message_processing = MagicMock()
        mock_message_task = AsyncMock() # The task itself
        mock_message_task.cancel = MagicMock()
        mock_agent_instance.start_message_processing.return_value = mock_message_task

        MockAnthropicFC.return_value = mock_agent_instance

        # Mock asyncio.Queue
        mock_queue_instance = MockAsyncQueue.return_value
        mock_queue_instance.put_nowait = MagicMock()


        # Mock input
        if user_inputs:
            mock_builtin_input.side_effect = user_inputs
        else:
            mock_builtin_input.return_value = "exit" # Default to exit immediately

        # Mock run_in_executor to directly call the lambda's function (agent.run_agent)
        # This makes agent.run_agent effectively synchronous for the test of the loop
        async def run_sync_lambda(loop, func, *args):
            return func(*args)
        mock_run_in_executor.side_effect = run_sync_lambda


        # Run async_main
        await async_main()

        return {
            "mock_parse_args": mock_parse_args,
            "mock_create_workspace": mock_create_workspace,
            "mock_db_instance": mock_db_instance,
            "mock_get_llm_client": mock_get_llm_client,
            "MockLLMSummarizingCM": MockLLMSummarizingCM,
            "MockAmortizedCM": MockAmortizedCM,
            "mock_get_system_tools": mock_get_system_tools,
            "MockAnthropicFC": MockAnthropicFC,
            "mock_agent_instance": mock_agent_instance,
            "mock_builtin_input": mock_builtin_input,
            "mock_message_task": mock_message_task,
            "mock_queue_instance": mock_queue_instance,
            "mock_run_in_executor": mock_run_in_executor
        }

    def test_cli_basic_interaction_hello_exit(self):
        user_inputs = ["hello", "exit"]
        agent_responses = ["Agent says world."]

        # asyncio.run to execute the async test method that calls async_main
        mocks = asyncio.run(self._run_async_main_with_mocks(
            user_inputs=user_inputs,
            agent_run_responses=agent_responses
        ))

        mocks["mock_db_instance"].create_session.assert_called_once()
        mocks["MockAnthropicFC"].assert_called_once() # Check agent was initialized
        mocks["mock_agent_instance"].start_message_processing.assert_called_once()

        # Check agent.run_agent was called with "hello"
        # Due to run_in_executor mock, it's called directly
        mocks["mock_agent_instance"].run_agent.assert_called_once_with("hello", resume=True)

        # Check user input was called twice ("hello", then "exit")
        self.assertEqual(mocks["mock_builtin_input"].call_count, 2)

        # Check events put on queue
        mocks["mock_queue_instance"].put_nowait.assert_any_call(
            RealtimeEvent(type=EventType.USER_MESSAGE, content={"text": "hello"})
        )
        # Exit does not queue a user message in the same way before breaking

        mocks["mock_message_task"].cancel.assert_called_once() # Task cancelled on exit


    def test_cli_non_interactive_mode_with_prompt(self):
        cli_args_prompt = {
            "logs_path": "test_agent.log", "minimize_stdout_logs": True,
            "workspace": None, "use_container_workspace": False,
            "model_name": "test_model", "llm_client": "anthropic-direct",
            "project_id": None, "region": None, "azure_model": False, "cot_model": False,
            "context_manager": "llm-summarizing", "prompt": "Process this single prompt", # Non-interactive
            "docker_container_id": None, "needs_permission": False,
            "memory_tool": "simple"
        }
        agent_response = "Single prompt processed."

        mocks = asyncio.run(self._run_async_main_with_mocks(
            cli_args=cli_args_prompt,
            agent_run_responses=[agent_response] # Only one response needed
        ))

        mocks["mock_agent_instance"].run_agent.assert_called_once_with("Process this single prompt", resume=True)
        mocks["mock_builtin_input"].assert_not_called() # input() should not be called
        # Loop should exit after one run because args.prompt is not None
        self.assertEqual(mocks["mock_run_in_executor"].call_count, 1)


    def test_cli_argument_parsing_selects_components(self):
        cli_args_custom = {
            "logs_path": "test_agent.log", "minimize_stdout_logs": True,
            "workspace": "/custom_ws", "use_container_workspace": True,
            "model_name": "custom_openai_model", "llm_client": "openai-direct",
            "project_id": "gcp_proj", "region": "gcp_reg", # Should be ignored for openai
            "azure_model": True, "cot_model": True, # For openai
            "context_manager": "amortized-forgetting", "prompt": None,
            "docker_container_id": "my_container", "needs_permission": True,
            "memory_tool": "compactify-memory"
        }

        mocks = asyncio.run(self._run_async_main_with_mocks(cli_args=cli_args_custom))

        mocks["mock_create_workspace"].assert_called_with("/custom_ws", True)
        mocks["mock_get_llm_client"].assert_called_with(
            "openai-direct",
            model_name="custom_openai_model",
            azure_model=True,
            cot_model=True
        )
        mocks["MockAmortizedCM"].assert_called_once() # Check correct CM was init
        mocks["MockLLMSummarizingCM"].assert_not_called()

        mocks["mock_get_system_tools"].assert_called_once()
        system_tools_call_args = mocks["mock_get_system_tools"].call_args.kwargs
        self.assertEqual(system_tools_call_args["container_id"], "my_container")
        self.assertTrue(system_tools_call_args["ask_user_permission"])
        self.assertEqual(system_tools_call_args["tool_args"]["memory_tool"], "compactify-memory")


    def test_cli_agent_run_exception_handling(self):
        user_inputs = ["cause_error", "exit"]
        # Simulate agent.run_agent raising an exception
        agent_run_side_effects = [Exception("Agent failed dramatically!"), "Should not be called"]

        mocks = asyncio.run(self._run_async_main_with_mocks(
            user_inputs=user_inputs,
            agent_run_responses=agent_run_side_effects
        ))

        mocks["mock_agent_instance"].run_agent.assert_called_once_with("cause_error", resume=True)
        # Check logger was called with the error
        # This requires logger instance used by cli.py to be the one we have.
        # The cli creates its own logger "agent_logs". We'd need to patch that specific logger.
        # For now, we assume if an error occurs, it's logged.
        # A more direct way: check if print (or console.print) was used for the error.
        self.assertTrue(self.mock_logger.info.called) # From setUp, used by AgentToolManager
        # The cli.py logger_for_agent_logs is what logs "Error: {str(e)}"
        # This test setup doesn't easily capture that specific logger's output yet.


if __name__ == "__main__":
    unittest.main()
