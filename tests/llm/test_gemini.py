import unittest
from unittest.mock import MagicMock, patch, ANY
import os
import time

# Import Actual Gemini Types for constructing mock responses
from google import genai # Updated for new SDK
from google.genai import types as genai_types # Updated for new SDK
from google.genai import errors # For new SDK error types
# from google.generativeai import client as genai_client # This was incorrect


from src.ii_agent.llm.gemini import GeminiDirectClient, generate_tool_call_id
# Standardize imports to match src/ii_agent/llm/gemini.py for shared base types
from ii_agent.llm.base import (
    LLMMessages,
    TextPrompt,
    ToolCall,
    UserContentBlock,
    TextResult,
    ToolFormattedResult,
    ToolParam,
    AssistantContentBlock,
    ImageBlock,
)


class TestGeminiLLMClient(unittest.TestCase):
    def setUp(self):
        self.model_name = "gemini-1.5-pro-latest"
        self.project_id = "test-project"
        self.region = "us-central1"

        self.env_patcher = patch.dict(os.environ, {"GEMINI_API_KEY": "test_gemini_key"})
        self.env_patcher.start()

        # Patch the new client structure: genai.Client()
        self.genai_client_patcher = patch("google.genai.Client")
        self.MockGenaiClientConstructor = self.genai_client_patcher.start()

        self.mock_gemini_client_actual_instance = MagicMock(spec=genai.Client)
        self.MockGenaiClientConstructor.return_value = self.mock_gemini_client_actual_instance

        # Mock the 'models' attribute and its 'generate_content' method
        self.mock_models_object = MagicMock()
        self.mock_gemini_client_actual_instance.models = self.mock_models_object

        self.mock_generate_content = MagicMock()
        self.mock_models_object.generate_content = self.mock_generate_content


    def tearDown(self):
        self.env_patcher.stop()
        self.genai_client_patcher.stop() # Stops patch("google.genai.Client")

    def test_client_instantiation_direct(self):
        client = GeminiDirectClient(model_name=self.model_name)
        self.assertIsNotNone(client)
        self.assertEqual(client.model_name, self.model_name)
        # GeminiDirectClient itself creates genai.Client
        # The patch is on google.genai.Client, so self.MockGenaiClientConstructor is that mock
        self.MockGenaiClientConstructor.assert_called_once_with(api_key="test_gemini_key")
        self.assertIs(client.client, self.mock_gemini_client_actual_instance)

    def test_client_instantiation_vertex_ai(self):
        # No more genai.configure. The client itself handles Vertex AI mode.
        client = GeminiDirectClient(
            model_name=self.model_name,
            project_id=self.project_id,
            region=self.region,
        )
        self.assertIsNotNone(client)
        self.assertEqual(client.model_name, self.model_name)
        self.MockGenaiClientConstructor.assert_called_once_with(
            vertexai=True, project=self.project_id, location=self.region
        )
        self.assertIs(client.client, self.mock_gemini_client_actual_instance)

    def _prepare_mock_response(self, text_content=None, function_calls_data=None, input_tokens=10, output_tokens=20):
        mock_response = MagicMock(spec=genai_types.GenerateContentResponse) # Keep this spec if it exists
        mock_response.text = text_content

        mock_parts_list = []
        if text_content:
            text_part = MagicMock()
            text_part.text = text_content
            mock_parts_list.append(text_part)

        if function_calls_data:
            for fc_data in function_calls_data:
                function_call_part = MagicMock()
                function_call_part.function_call.name = fc_data["name"]
                function_call_part.function_call.args = fc_data["args"]
                # function_call_part.function_call.id = fc_data.get("id") # ID might not be directly on function_call part
                mock_parts_list.append(function_call_part)

        # The structure of GenerateContentResponse is usually a list of candidates,
        # and each candidate has 'content' which has 'parts'.
        # Parts can be text or function calls.

        mock_candidate = MagicMock()
        mock_candidate.content.parts = mock_parts_list

        # If function_calls_data is provided, the response structure might differ slightly
        # or these are extracted from parts by the client code.
        # For now, ensuring parts are populated.
        # The original code also set mock_response.function_calls directly.
        # Let's ensure `parts` are there, as that's common in Gemini API.
        # If the client code expects `response.text` and `response.function_calls` directly,
        # the adapter in `GeminiDirectClient` must be creating these.

        # The existing mock sets response.text and response.function_calls.
        # Let's stick to that for now, assuming the client code processes this.
        mock_fc_list = []
        if function_calls_data:
             for fc_data in function_calls_data:
                mock_fc_obj = MagicMock(spec=genai_types.FunctionCall)
                mock_fc_obj.name = fc_data["name"]
                mock_fc_obj.args = fc_data["args"]
                mock_fc_obj.id = fc_data.get("id") # Explicitly set id, can be None
                mock_fc_list.append(mock_fc_obj)
        mock_response.function_calls = mock_fc_list


        # mock_response.usage_metadata = genai_types.UsageMetadata( # This was causing issues
        #     prompt_token_count=input_tokens,
        #     candidates_token_count=output_tokens,
        # )
        # Instead, mock it as an attribute with sub-attributes
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = input_tokens
        mock_response.usage_metadata.candidates_token_count = output_tokens

        self.mock_generate_content.return_value = mock_response
        return mock_response

    def test_generate_simple_text_prompt(self):
        client = GeminiDirectClient(model_name=self.model_name)
        self._prepare_mock_response(text_content="Hello, world!")

        messages = [[TextPrompt(text="Hello")]] # Directly use TextPrompt
        max_tokens = 50

        response_content, metadata = client.generate(
            messages=messages, max_tokens=max_tokens
        )

        self.assertEqual(len(response_content), 1)
        self.assertIsInstance(response_content[0], TextResult)
        self.assertEqual(response_content[0].text, "Hello, world!")

        self.assertEqual(metadata["input_tokens"], 10)
        self.assertEqual(metadata["output_tokens"], 20)

        self.mock_generate_content.assert_called_once()
        call_args = self.mock_generate_content.call_args

        self.assertEqual(call_args.kwargs["model"], self.model_name)
        self.assertEqual(call_args.kwargs["contents"][0].parts[0].text, "Hello")
        self.assertEqual(call_args.kwargs["contents"][0].role, "user")

        # Access nested config attributes correctly
        self.assertEqual(call_args.kwargs["config"].max_output_tokens, max_tokens)
        self.assertEqual(call_args.kwargs["config"].temperature, 0.0)
        self.assertEqual(call_args.kwargs["config"].system_instruction, None) # system_prompt is None by default in this call
        self.assertEqual(call_args.kwargs["config"].tool_config.function_calling_config.mode, "ANY")

    def test_generate_with_system_prompt_and_temperature(self):
        client = GeminiDirectClient(model_name=self.model_name)
        self._prepare_mock_response(text_content="Systematic hello.")

        system_prompt_text = "You are a helpful bot."
        temp = 0.7
        messages = [[TextPrompt(text="Hi")]] # Directly use TextPrompt

        client.generate(messages=messages, max_tokens=20, system_prompt=system_prompt_text, temperature=temp)

        self.mock_generate_content.assert_called_once()
        call_args = self.mock_generate_content.call_args
        self.assertEqual(call_args.kwargs["config"].system_instruction, system_prompt_text)
        self.assertEqual(call_args.kwargs["config"].temperature, temp)

    @patch("src.ii_agent.llm.gemini.generate_tool_call_id", return_value="fixed_call_id_123")
    def test_generate_with_function_calling(self, mock_generate_id):
        client = GeminiDirectClient(model_name=self.model_name)
        tool_name = "get_weather"
        tool_args = {"location": "London"}
        self._prepare_mock_response(function_calls_data=[{"name": tool_name, "args": tool_args}]) # No ID from API

        messages = [[TextPrompt(text="What's the weather in London?")]] # Directly use TextPrompt
        tools = [ToolParam(name=tool_name, description="Gets weather", input_schema={"type": "object", "properties": {"location": {"type": "string"}}})]

        response_content, _ = client.generate(messages=messages, max_tokens=50, tools=tools)

        self.assertEqual(len(response_content), 1)
        self.assertIsInstance(response_content[0], ToolCall)
        tool_call = response_content[0]
        self.assertEqual(tool_call.tool_name, tool_name)
        self.assertEqual(tool_call.tool_input, tool_args)
        self.assertEqual(tool_call.tool_call_id, "fixed_call_id_123") # ID generated by client

        self.mock_generate_content.assert_called_once()
        call_args = self.mock_generate_content.call_args
        self.assertIsNotNone(call_args.kwargs["config"].tools) # tools is part of GenerationConfig
        self.assertEqual(len(call_args.kwargs["config"].tools[0].function_declarations), 1)
        self.assertEqual(call_args.kwargs["config"].tools[0].function_declarations[0].name, tool_name)
        self.assertEqual(call_args.kwargs["config"].tool_config.function_calling_config.mode, "ANY") # tool_config is part of GenerationConfig

    def test_generate_with_tool_choice_auto(self):
        client = GeminiDirectClient(model_name=self.model_name)
        self._prepare_mock_response(text_content="Okay.") # Gemini might return text with AUTO

        messages = [[TextPrompt(text="Hi")]] # Directly use TextPrompt
        tools = [ToolParam(name="any_tool", description="desc", input_schema={})]

        client.generate(messages=messages, max_tokens=10, tools=tools, tool_choice={"type": "auto"})

        self.mock_generate_content.assert_called_once()
        call_args = self.mock_generate_content.call_args
        self.assertEqual(call_args.kwargs["config"].tool_config.function_calling_config.mode, "AUTO")


    def test_generate_with_tool_formatted_result(self):
        client = GeminiDirectClient(model_name=self.model_name)
        self._prepare_mock_response(text_content="The weather is sunny.")

        tool_name = "get_weather"
        messages = [
            [TextPrompt(text="What's the weather in London?")], # Directly use TextPrompt
            [ToolCall(tool_call_id="call_123", tool_name=tool_name, tool_input={"location": "London"})], # Directly use ToolCall (was already correct as AssistantContentBlock)
            [ToolFormattedResult(tool_call_id="call_123", tool_name=tool_name, tool_output="Sunny")] # Directly use ToolFormattedResult
        ]
        tools = [ToolParam(name=tool_name, description="Gets weather", input_schema={})]

        client.generate(messages=messages, max_tokens=50, tools=tools)

        self.mock_generate_content.assert_called_once()
        call_args = self.mock_generate_content.call_args

        # Last message should be the tool result
        last_message_parts = call_args.kwargs["contents"][-1].parts
        self.assertEqual(len(last_message_parts), 1)
        self.assertEqual(last_message_parts[0].function_response.name, tool_name)
        self.assertEqual(last_message_parts[0].function_response.response["result"], "Sunny")

    def test_generate_with_tool_formatted_result_as_list_of_parts(self):
        client = GeminiDirectClient(model_name=self.model_name)
        self._prepare_mock_response(text_content="Here is the image and text.")

        tool_name = "get_image_and_text"
        tool_output_list = [
            {"type": "text", "text": "This is a generated caption."},
            {"type": "image", "source": {"media_type": "image/png", "data": b"fakeimagedata"}}
        ]
        messages = [
            [TextPrompt(text="Generate an image and caption")], # Directly use TextPrompt
            [ToolCall(tool_call_id="call_img_txt", tool_name=tool_name, tool_input={})], # Directly use ToolCall
            [ToolFormattedResult(tool_call_id="call_img_txt", tool_name=tool_name, tool_output=tool_output_list)] # Directly use ToolFormattedResult
        ]
        tools = [ToolParam(name=tool_name, description="Gets image and text", input_schema={})]

        client.generate(messages=messages, max_tokens=50, tools=tools)

        self.mock_generate_content.assert_called_once()
        call_args = self.mock_generate_content.call_args

        last_message_parts = call_args.kwargs["contents"][-1].parts
        self.assertEqual(len(last_message_parts), 1) # Should be a single FunctionResponse Part
        self.assertIsNotNone(last_message_parts[0].function_response, "Part should be a function_response") # Added this line from my previous correct reasoning
        self.assertEqual(last_message_parts[0].function_response.name, tool_name)

        # The actual list is now nested under 'result' in the response
        actual_tool_output_list_from_response = last_message_parts[0].function_response.response['result']
        self.assertEqual(len(actual_tool_output_list_from_response), 2)
        self.assertEqual(actual_tool_output_list_from_response[0]['text'], "This is a generated caption.")
        # For the image part, check its structure within the list
        self.assertEqual(actual_tool_output_list_from_response[1]['type'], "image")
        self.assertEqual(actual_tool_output_list_from_response[1]['source']['media_type'], "image/png")
        self.assertEqual(actual_tool_output_list_from_response[1]['source']['data'], b"fakeimagedata")


    @patch("time.sleep", return_value=None) # Mock time.sleep
    def test_generate_api_error_with_retry(self, mock_sleep):
        client = GeminiDirectClient(model_name=self.model_name, max_retries=2)

        # Simulate API error on first call, success on second
        # Using ResourceExhausted as an example of a retryable error (code 429)
        # Assuming ResourceExhausted is in genai_types or genai.errors (which we can't find)
        # For now, let's use a generic Exception and refine if tests fail here.
        # If genai_types.ResourceExhausted is not valid, this will need to change.
        # errors.APIError(message, response_json) - provide minimal response_json
        mock_error_429 = errors.APIError("Rate limited - simulated", response_json={})
        mock_error_429.code = 429 # Simulate ResourceExhausted
        self.mock_generate_content.side_effect = [
            mock_error_429,
            self._prepare_mock_response(text_content="Success after retry")
        ]

        messages = [[TextPrompt(text="Test retry")]]
        client.generate(messages=messages, max_tokens=20)

        self.assertEqual(self.mock_generate_content.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("time.sleep", return_value=None)
    def test_generate_api_error_max_retries_exceeded(self, mock_sleep):
        client = GeminiDirectClient(model_name=self.model_name, max_retries=2)
        # Simulate API error on all calls (DeadlineExceeded is code 503)
        mock_error_503 = errors.APIError("Timeout - simulated", response_json={})
        mock_error_503.code = 503 # Simulate DeadlineExceeded
        self.mock_generate_content.side_effect = mock_error_503

        messages = [[TextPrompt(text="Test max retry")]]
        with self.assertRaises(errors.APIError) as cm:
            client.generate(messages=messages, max_tokens=20)
        self.assertEqual(cm.exception.code, 503)

        self.assertEqual(self.mock_generate_content.call_count, client.max_retries)
        self.assertEqual(mock_sleep.call_count, client.max_retries - 1)

    def test_generate_non_retryable_api_error(self):
        client = GeminiDirectClient(model_name=self.model_name, max_retries=2)
        # InternalServerError is not explicitly listed for retry, so it should fail fast
        mock_error_500 = errors.APIError("Internal error - simulated", response_json={})
        mock_error_500.code = 500 # Simulate InternalServerError
        self.mock_generate_content.side_effect = mock_error_500

        messages = [[TextPrompt(text="Test non-retry error")]]
        with self.assertRaises(errors.APIError) as cm:
            client.generate(messages=messages, max_tokens=20)
        self.assertEqual(cm.exception.code, 500)
        self.assertEqual(self.mock_generate_content.call_count, 1)


    def test_generate_with_image_block(self):
        client = GeminiDirectClient(model_name=self.model_name)
        self._prepare_mock_response(text_content="Image received.")

        image_data = b"fake_image_bytes"
        messages = [
            [ # Outer list for turns
                TextPrompt(text="What is this image?"), # Directly use TextPrompt
                ImageBlock(type="image", source={"media_type": "image/png", "data": image_data})
            ]
        ]

        client.generate(messages=messages, max_tokens=30)

        self.mock_generate_content.assert_called_once()
        call_args = self.mock_generate_content.call_args

        user_parts = call_args.kwargs["contents"][0].parts
        self.assertEqual(len(user_parts), 2)
        self.assertEqual(user_parts[0].text, "What is this image?")
        self.assertEqual(user_parts[1].inline_data.mime_type, "image/png")
        self.assertEqual(user_parts[1].inline_data.data, image_data)


if __name__ == "__main__":
    unittest.main()
