import asyncio
import uuid
import logging
from typing import Any, Dict, Optional

from ii_agent.core.event import EventType, RealtimeEvent
from ii_agent.llm.message_history import MessageHistory # For type hint if needed
from ii_agent.tools.base import LLMTool, ToolImplOutput
from ii_agent.agents.anthropic_fc import AnthropicFC # To access message_queue

# A shared dictionary to store asyncio.Event objects for each command_id
# This allows run_impl to wait for a result from the WebSocket server.
# IMPORTANT: This is a simple in-memory solution. For multi-worker or more robust
# setups, an external store (like Redis) or a more sophisticated IPC mechanism
# would be needed.
pending_neutralino_commands: Dict[str, asyncio.Event] = {}
neutralino_command_results: Dict[str, Any] = {}

logger = logging.getLogger(__name__)

class NeutralinoBridgeTool(LLMTool):
    name = "desktop_interaction"
    description = (
        "Interacts with the user's desktop via the Neutralinojs app. "
        "Can be used to show native notifications or file dialogs. "
        "Specify the 'action' (e.g., 'show_notification', 'show_save_dialog', 'show_open_dialog') "
        "and necessary 'action_params'."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "The desktop action to perform.",
                "enum": ["show_notification", "show_save_dialog", "show_open_dialog"],
            },
            "action_params": {
                "type": "object",
                "description": "Parameters for the specified action.",
                "properties": {
                    "title": {"type": "string", "description": "Title for dialogs or notifications."},
                    "content": {"type": "string", "description": "Content for notifications."},
                    "defaultPath": {"type": "string", "description": "Default path for file dialogs."},
                    # Add other params as Neutralinojs API needs them for these actions
                },
                "required": [], # Make specific params required based on action later if needed
            },
        },
        "required": ["action", "action_params"],
    }

    # This tool needs access to the agent's message_queue to send NEUTRALINO_COMMAND
    # And potentially the agent itself or a reference to the ws_server's command handling mechanism
    # For now, let's assume the agent instance is passed or accessible.
    # A cleaner way might be a dedicated dispatcher, but this is simpler for now.
    agent_reference: Optional[AnthropicFC] = None

    def __init__(self, agent_ref: Optional[AnthropicFC] = None): # agent_ref is for direct injection, but we'll set agent_reference later
        super().__init__()
        self.agent_reference = agent_ref # This will likely be None initially if using the revised approach
        if not self.agent_reference:
            # This warning is fine at initial instantiation time with the revised approach
            logger.debug("NeutralinoBridgeTool initialized without agent reference. It will be set later by the agent.")

    async def run_impl_async(self, tool_input: dict[str, Any], message_history: Optional[MessageHistory] = None) -> ToolImplOutput:
        action = tool_input.get("action")
        action_params = tool_input.get("action_params", {})

        if not self.agent_reference or not hasattr(self.agent_reference, 'message_queue'):
            error_msg = "NeutralinoBridgeTool cannot send command: agent reference or message_queue not set."
            logger.error(error_msg)
            return ToolImplOutput(tool_output=error_msg, tool_result_message=error_msg, error=True)

        command_id = str(uuid.uuid4())

        payload_to_frontend = {
            "command_id": command_id,
            "action": action,
            "details": action_params
        }

        # Create an event for this command_id that we can wait on
        event = asyncio.Event()
        pending_neutralino_commands[command_id] = event
        neutralino_command_results.pop(command_id, None) # Clear any stale result

        logger.info(f"Sending NEUTRALINO_COMMAND {command_id} for action {action}")
        # The message_queue is an asyncio.Queue, use put_nowait from sync context if called from one,
        # or put if agent_reference itself is async and can await.
        # Since agent's message processing loop is async, this should be fine.
        self.agent_reference.message_queue.put_nowait(
            RealtimeEvent(type=EventType.NEUTRALINO_COMMAND, content=payload_to_frontend)
        )

        try:
            # Wait for the result to be set by the WebSocket handler (with a timeout)
            await asyncio.wait_for(event.wait(), timeout=30.0) # 30 second timeout
            result = neutralino_command_results.pop(command_id, None)
            # Ensure event is removed from pending commands even if result is None (e.g. if set without result)
            pending_neutralino_commands.pop(command_id, None)


            if result:
                logger.info(f"Received NEUTRALINO_RESULT for {command_id}: {result}")
                # Check status from frontend if it's part of the result payload
                status = result.get('status', 'unknown')
                output_payload = result.get("payload", "No payload in result")
                if status == 'error':
                    return ToolImplOutput(
                        tool_output=output_payload,
                        tool_result_message=f"Desktop action '{action}' failed with: {output_payload}",
                        error=True
                    )
                return ToolImplOutput(
                    tool_output=output_payload,
                    tool_result_message=f"Desktop action '{action}' completed with status: {status}"
                )
            else:
                # This case might be hit if event.set() was called but result was not put in neutralino_command_results
                logger.warning(f"NEUTRALINO_COMMAND {command_id} (action: {action}) completed but result was not found.")
                return ToolImplOutput(
                    tool_output=f"Desktop action '{action}' completed without a result payload.",
                    tool_result_message="Desktop action completed without result.",
                    error=True
                )
        except asyncio.TimeoutError:
            pending_neutralino_commands.pop(command_id, None) # Clean up
            neutralino_command_results.pop(command_id, None) # Clean up
            logger.warning(f"NEUTRALINO_COMMAND {command_id} (action: {action}) timed out.")
            return ToolImplOutput(
                tool_output=f"Desktop action '{action}' timed out.",
                tool_result_message="Desktop action timed out.",
                error=True
            )
        except Exception as e:
            pending_neutralino_commands.pop(command_id, None) # Clean up
            neutralino_command_results.pop(command_id, None) # Clean up
            logger.error(f"Error during NEUTRALINO_COMMAND {command_id} (action: {action}): {e}", exc_info=True)
            return ToolImplOutput(
                tool_output=f"Error during desktop action '{action}': {str(e)}",
                tool_result_message=f"Error: {str(e)}",
                error=True
            )

    def run_impl(self, tool_input: dict[str, Any], message_history: Optional[MessageHistory] = None) -> ToolImplOutput:
        try:
            loop = asyncio.get_event_loop()
            # Check if the loop is available and we are in a thread that can submit tasks to it
            if loop.is_running():
                # This is typical if run_impl is called from a thread managed by anyio.to_thread.run_sync
                future = asyncio.run_coroutine_threadsafe(self.run_impl_async(tool_input, message_history), loop)
                return future.result()  # This blocks the current thread
            else:
                # Fallback if no loop is running in the current context (less common for this app)
                return loop.run_until_complete(self.run_impl_async(tool_input, message_history))
        except RuntimeError: # No event loop in this thread
            # This might happen if the thread is not managed by an asyncio-aware system
            # Creating a new loop here can be problematic if other parts of the system expect a single loop
            logger.warning("NeutralinoBridgeTool.run_impl: No event loop found, creating a new one. This might be an issue.")
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(self.run_impl_async(tool_input, message_history))
            finally:
                new_loop.close()
                # It's important to restore the original event loop context if it was changed,
                # but Python's default policy might not have one to restore.
                # asyncio.set_event_loop(None) # Or restore previous loop if known
                pass # Or handle this more gracefully depending on threading model.
