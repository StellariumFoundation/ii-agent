import unittest
from unittest.mock import MagicMock, patch, ANY
import time

from anthropic import APIConnectionError, RateLimitError
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage
from src.ii_agent.llm.anthropic import AnthropicLLMClient, Anthropic_NOT_GIVEN
from src.ii_agent.llm.base import (
    LLMMessages,
    TextPrompt,
    ToolCall,
    UserContentBlock,
    TextResult,
    ToolFormattedResult,
    ToolParam,
    AssistantContentBlock,
)


class TestAnthropicLLMClient(unittest.TestCase):
    def setUp(self):
        self.model_name = "claude-3-opus-20240229"
        # Patch os.getenv for ANTHROPIC_API_KEY during client initialization
        self.env_patcher = patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test_key"})
        self.env_patcher.start()
        self.client = AnthropicLLMClient(model_name=self.model_name, max_retries=2)

    def tearDown(self):
        self.env_patcher.stop()

    def test_client_instantiation(self):
        self.assertIsNotNone(self.client)
        self.assertEqual(self.client.model_name, self.model_name)

    @patch("anthropic.Anthropic")
    def test_generate_simple_text_prompt(self, mock_anthropic_client_constructor):
        mock_anthropic_instance = MagicMock()
        mock_anthropic_client_constructor.return_value = mock_anthropic_instance

        mock_response_content = [TextBlock(type="text", text="Hello, world!")]
        mock_usage = Usage(input_tokens=10, output_tokens=20)
        mock_anthropic_instance.messages.create.return_value = Message(
            id="msg_123",
            content=mock_response_content,
            model=self.model_name,
            role="assistant",
            stop_reason="end_turn",
            type="message",
            usage=mock_usage,
        )

        messages: LLMMessages = [[UserContentBlock(content=TextPrompt(text="Hello"))]]
        max_tokens = 50

        response_content, metadata = self.client.generate(
            messages=messages, max_tokens=max_tokens
        )

        self.assertEqual(len(response_content), 1)
        self.assertIsInstance(response_content[0], TextResult)
        self.assertEqual(response_content[0].text, "Hello, world!")

        self.assertEqual(metadata["input_tokens"], 10)
        self.assertEqual(metadata["output_tokens"], 20)

        mock_anthropic_instance.messages.create.assert_called_once_with(
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            model=self.model_name,
            temperature=0.0,
            system=Anthropic_NOT_GIVEN,
            tool_choice=Anthropic_NOT_GIVEN,
            tools=Anthropic_NOT_GIVEN,
            extra_headers=self.client.prompt_caching_headers,
            extra_body=None,
        )

    @patch("anthropic.Anthropic")
    def test_generate_with_tool_call_and_result(self, mock_anthropic_client_constructor):
        mock_anthropic_instance = MagicMock()
        mock_anthropic_client_constructor.return_value = mock_anthropic_instance

        # First call: Assistant requests to use a tool
        mock_tool_use_block = ToolUseBlock(
            id="tool_abc",
            input={"arg1": "value1"},
            name="test_tool",
            type="tool_use",
        )
        mock_response_content1 = [mock_tool_use_block]
        mock_usage1 = Usage(input_tokens=30, output_tokens=40)

        # Second call: User provides tool result, assistant gives final text answer
        mock_response_content2 = [TextBlock(type="text", text="Tool finished.")]
        mock_usage2 = Usage(input_tokens=50, output_tokens=15)

        mock_anthropic_instance.messages.create.side_effect = [
            Message(
                id="msg_456",
                content=mock_response_content1,
                model=self.model_name,
                role="assistant",
                stop_reason="tool_use",
                type="message",
                usage=mock_usage1,
            ),
            Message(
                id="msg_789",
                content=mock_response_content2,
                model=self.model_name,
                role="assistant",
                stop_reason="end_turn",
                type="message",
                usage=mock_usage2,
            ),
        ]


        messages_turn1: LLMMessages = [
            [UserContentBlock(content=TextPrompt(text="Use a tool to do X"))]
        ]
        max_tokens = 100
        tools = [
            ToolParam(
                name="test_tool",
                description="A test tool",
                input_schema={"type": "object", "properties": {"arg1": {"type": "string"}}},
            )
        ]

        response_content1, metadata1 = self.client.generate(
            messages=messages_turn1, max_tokens=max_tokens, tools=tools
        )

        self.assertEqual(len(response_content1), 1)
        self.assertIsInstance(response_content1[0], ToolCall)
        tool_call_response = cast(ToolCall, response_content1[0])
        self.assertEqual(tool_call_response.tool_call_id, "tool_abc")
        self.assertEqual(tool_call_response.tool_name, "test_tool")
        self.assertEqual(tool_call_response.tool_input, {"arg1": "value1"})

        self.assertEqual(metadata1["input_tokens"], 30)
        self.assertEqual(metadata1["output_tokens"], 40)

        # Now, simulate providing the tool result back to the LLM
        messages_turn2: LLMMessages = [
            [UserContentBlock(content=TextPrompt(text="Use a tool to do X"))],
            [AssistantContentBlock(content=response_content1)], # Original assistant response with ToolCall
            [
                UserContentBlock(
                    content=ToolFormattedResult(
                        tool_call_id="tool_abc", tool_output='{"result": "tool success"}'
                    )
                )
            ],
        ]

        response_content2, metadata2 = self.client.generate(
            messages=messages_turn2, max_tokens=max_tokens, tools=tools
        )

        self.assertEqual(len(response_content2), 1)
        self.assertIsInstance(response_content2[0], TextResult)
        self.assertEqual(response_content2[0].text, "Tool finished.")
        self.assertEqual(metadata2["input_tokens"], 50)
        self.assertEqual(metadata2["output_tokens"], 15)

        self.assertEqual(mock_anthropic_instance.messages.create.call_count, 2)
        call_args_list = mock_anthropic_instance.messages.create.call_args_list

        # Check first call args
        call_args1 = call_args_list[0][1]
        self.assertEqual(call_args1["max_tokens"], max_tokens)
        self.assertEqual(len(call_args1["tools"]), 1)
        self.assertEqual(call_args1["tools"][0]["name"], "test_tool")
        self.assertEqual(call_args1["messages"][-1]["role"], "user")

        # Check second call args
        call_args2 = call_args_list[1][1]
        self.assertEqual(call_args2["max_tokens"], max_tokens)
        self.assertEqual(len(call_args2["tools"]), 1)
        self.assertEqual(call_args2["messages"][-1]["role"], "user")
        self.assertEqual(call_args2["messages"][-1]["content"][-1]["type"], "tool_result")
        self.assertEqual(call_args2["messages"][-1]["content"][-1]["tool_use_id"], "tool_abc")


    @patch("anthropic.Anthropic")
    @patch("time.sleep", return_value=None) # Mock time.sleep to speed up test
    def test_generate_api_error_with_retry(self, mock_sleep, mock_anthropic_client_constructor):
        mock_anthropic_instance = MagicMock()
        mock_anthropic_client_constructor.return_value = mock_anthropic_instance

        # Simulate API error on first call, success on second
        mock_anthropic_instance.messages.create.side_effect = [
            RateLimitError("Rate limited", response=MagicMock(), body=None),
            Message(
                id="msg_retry_123",
                content=[TextBlock(type="text", text="Success after retry")],
                model=self.model_name,
                role="assistant",
                stop_reason="end_turn",
                type="message",
                usage=Usage(input_tokens=5, output_tokens=10),
            ),
        ]

        messages: LLMMessages = [[UserContentBlock(content=TextPrompt(text="Test retry"))]]
        max_tokens = 20

        response_content, metadata = self.client.generate(
            messages=messages, max_tokens=max_tokens
        )

        self.assertEqual(len(response_content), 1)
        self.assertEqual(response_content[0].text, "Success after retry")
        self.assertEqual(metadata["input_tokens"], 5)
        self.assertEqual(metadata["output_tokens"], 10)
        self.assertEqual(mock_anthropic_instance.messages.create.call_count, 2)
        mock_sleep.assert_called_once() # Ensure sleep was called for retry

    @patch("anthropic.Anthropic")
    @patch("time.sleep", return_value=None)
    def test_generate_api_error_max_retries_exceeded(self, mock_sleep, mock_anthropic_client_constructor):
        mock_anthropic_instance = MagicMock()
        mock_anthropic_client_constructor.return_value = mock_anthropic_instance

        # Simulate API error on all calls
        mock_anthropic_instance.messages.create.side_effect = APIConnectionError("Connection error")

        messages: LLMMessages = [[UserContentBlock(content=TextPrompt(text="Test max retry"))]]
        max_tokens = 20

        with self.assertRaises(APIConnectionError):
            self.client.generate(messages=messages, max_tokens=max_tokens)

        self.assertEqual(mock_anthropic_instance.messages.create.call_count, self.client.max_retries)
        self.assertEqual(mock_sleep.call_count, self.client.max_retries -1)


    @patch("anthropic.Anthropic")
    def test_generate_with_system_prompt_and_temperature(self, mock_anthropic_client_constructor):
        mock_anthropic_instance = MagicMock()
        mock_anthropic_client_constructor.return_value = mock_anthropic_instance

        mock_anthropic_instance.messages.create.return_value = Message(
            id="msg_params_123",
            content=[TextBlock(type="text", text="Params test")],
            model=self.model_name,
            role="assistant",
            stop_reason="end_turn",
            type="message",
            usage=Usage(input_tokens=5, output_tokens=5),
        )

        messages: LLMMessages = [[UserContentBlock(content=TextPrompt(text="Hi"))]]
        system_prompt = "You are a helpful assistant."
        temperature = 0.7

        self.client.generate(
            messages=messages, max_tokens=10, system_prompt=system_prompt, temperature=temperature
        )

        mock_anthropic_instance.messages.create.assert_called_once()
        call_args = mock_anthropic_instance.messages.create.call_args[1]
        self.assertEqual(call_args["system"], system_prompt)
        self.assertEqual(call_args["temperature"], temperature)

    @patch("anthropic.Anthropic")
    def test_generate_with_tool_choice(self, mock_anthropic_client_constructor):
        mock_anthropic_instance = MagicMock()
        mock_anthropic_client_constructor.return_value = mock_anthropic_instance

        mock_tool_use_block = ToolUseBlock(id="tool_xyz", input={}, name="specific_tool", type="tool_use")
        mock_anthropic_instance.messages.create.return_value = Message(
            id="msg_tool_choice_123",
            content=[mock_tool_use_block],
            model=self.model_name,
            role="assistant",
            stop_reason="tool_use",
            type="message",
            usage=Usage(input_tokens=15, output_tokens=10),
        )

        messages: LLMMessages = [[UserContentBlock(content=TextPrompt(text="Call specific tool"))]]
        tools = [ToolParam(name="specific_tool", description="desc", input_schema={})]
        tool_choice = {"type": "tool", "name": "specific_tool"}

        self.client.generate(
            messages=messages, max_tokens=30, tools=tools, tool_choice=tool_choice
        )

        mock_anthropic_instance.messages.create.assert_called_once()
        call_args = mock_anthropic_instance.messages.create.call_args[1]
        self.assertEqual(call_args["tool_choice"]["type"], "tool")
        self.assertEqual(call_args["tool_choice"]["name"], "specific_tool")

    @patch("anthropic.Anthropic")
    def test_generate_no_caching(self, mock_anthropic_client_constructor):
        mock_anthropic_instance = MagicMock()
        mock_anthropic_client_constructor.return_value = mock_anthropic_instance
        self.client.use_caching = False # Disable caching for this test

        mock_anthropic_instance.messages.create.return_value = Message(
            id="msg_no_cache_123",
            content=[TextBlock(type="text", text="No cache")],
            model=self.model_name,
            role="assistant",
            stop_reason="end_turn",
            type="message",
            usage=Usage(input_tokens=5, output_tokens=5),
        )
        messages: LLMMessages = [[UserContentBlock(content=TextPrompt(text="Test no cache"))]]
        self.client.generate(messages=messages, max_tokens=10)

        mock_anthropic_instance.messages.create.assert_called_once()
        call_args = mock_anthropic_instance.messages.create.call_args[1]
        self.assertIsNone(call_args["extra_headers"])

        # Reset for other tests
        self.client.use_caching = True


    @patch("anthropic.Anthropic")
    def test_generate_with_thinking_tokens(self, mock_anthropic_client_constructor):
        mock_anthropic_instance = MagicMock()
        mock_anthropic_client_constructor.return_value = mock_anthropic_instance

        mock_anthropic_instance.messages.create.return_value = Message(
            id="msg_thinking_123",
            content=[TextBlock(type="text", text="Thinking test")],
            model=self.model_name,
            role="assistant",
            stop_reason="end_turn",
            type="message",
            usage=Usage(input_tokens=5, output_tokens=5),
        )

        messages: LLMMessages = [[UserContentBlock(content=TextPrompt(text="Think about it"))]]
        thinking_tokens = 1000
        # As per code, max_tokens must be >= 32_000 when thinking_tokens is used
        max_tokens_for_thinking = 32000

        self.client.generate(
            messages=messages, max_tokens=max_tokens_for_thinking, thinking_tokens=thinking_tokens
        )

        mock_anthropic_instance.messages.create.assert_called_once()
        call_args = mock_anthropic_instance.messages.create.call_args[1]
        self.assertIsNotNone(call_args["extra_body"])
        self.assertEqual(call_args["extra_body"]["thinking"]["type"], "enabled")
        self.assertEqual(call_args["extra_body"]["thinking"]["budget_tokens"], thinking_tokens)
        self.assertEqual(call_args["temperature"], 1) # Temperature is forced to 1
        self.assertEqual(call_args["max_tokens"], max_tokens_for_thinking)

    @patch("anthropic.AnthropicVertex") # For vertex client
    def test_vertex_client_instantiation(self, mock_anthropic_vertex_constructor):
        mock_vertex_instance = MagicMock()
        mock_anthropic_vertex_constructor.return_value = mock_vertex_instance

        project_id = "test-project"
        region = "us-central1"

        vertex_client = AnthropicLLMClient(
            model_name=self.model_name,
            project_id=project_id,
            region=region
        )

        self.assertIsNotNone(vertex_client)
        mock_anthropic_vertex_constructor.assert_called_once_with(
            project_id=project_id,
            region=region,
            timeout=ANY,
            max_retries=1
        )
        # Model name should be transformed for Vertex
        self.assertEqual(vertex_client.model_name, self.model_name.replace("@", "-"))


if __name__ == "__main__":
    unittest.main()

# Helper to cast in tests where type is known
from typing import cast
