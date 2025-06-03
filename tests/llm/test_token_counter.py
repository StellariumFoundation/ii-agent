import unittest
from unittest.mock import patch, MagicMock
import base64
import io # Required for BytesIO

# Assuming TokenCounter and relevant message types are in these locations
from src.ii_agent.llm.token_counter import TokenCounter
# We don't need the base LLM types for this version of TokenCounter


class TestTokenCounter(unittest.TestCase):
    def setUp(self):
        self.counter = TokenCounter()

    def test_count_tokens_with_string(self):
        self.assertEqual(self.counter.count_tokens("Hello"), 5 // 3)
        self.assertEqual(self.counter.count_tokens("Hello World"), 11 // 3)
        self.assertEqual(self.counter.count_tokens(""), 0 // 3)

    def test_count_tokens_with_list_of_text_dicts(self):
        messages = [
            {"type": "text", "text": "Hello"}, # 5 chars -> 1 token
            {"type": "text", "text": "World"}, # 5 chars -> 1 token
        ]
        # Expected: (5//3) + (5//3) = 1 + 1 = 2
        self.assertEqual(self.counter.count_tokens(messages), 2)

    def test_count_tokens_with_list_of_non_text_image_dicts(self):
        messages = [
            {"key": "value", "number": 123}, # json: '{"key": "value", "number": 123}' = 30 chars -> 10 tokens
            {"another": "item"}             # json: '{"another": "item"}' = 19 chars -> 6 tokens
        ]
        # Expected: (30//3) + (19//3) = 10 + 6 = 16
        self.assertEqual(self.counter.count_tokens(messages), 16)

    @patch("base64.b64decode")
    @patch("PIL.Image.open")
    def test_count_tokens_with_list_of_image_dicts(self, mock_image_open, mock_b64decode):
        # Mock image data and dimensions
        mock_image_data = b"fake_image_data"
        mock_b64decode.return_value = mock_image_data

        mock_img_instance = MagicMock()
        mock_img_instance.size = (300, 200) # width, height

        # PIL.Image.open is used as a context manager in the code
        mock_image_open.return_value.__enter__.return_value = mock_img_instance

        messages = [
            {"type": "image", "source": {"data": "some_base64_string"}},
        ]
        # Expected tokens for image: (300 * 200) / 750 = 60000 / 750 = 80
        self.assertEqual(self.counter.count_tokens(messages), 80)
        mock_b64decode.assert_called_once_with("some_base64_string")
        mock_image_open.assert_called_once_with(io.BytesIO(mock_image_data))

    @patch("base64.b64decode")
    @patch("PIL.Image.open")
    def test_count_tokens_with_mixed_content_list(self, mock_image_open, mock_b64decode):
        mock_image_data = b"fake_image_data_2"
        mock_b64decode.return_value = mock_image_data
        mock_img_instance = MagicMock()
        mock_img_instance.size = (150, 150) # (150*150)/750 = 22500/750 = 30 tokens
        mock_image_open.return_value.__enter__.return_value = mock_img_instance

        messages = [
            {"type": "text", "text": "Description"}, # 11 chars -> 3 tokens
            {"type": "image", "source": {"data": "another_b64_string"}}, # 30 tokens
            {"other_data": "misc info"}, # json: '{"other_data": "misc info"}' = 28 chars -> 9 tokens
        ]
        # Expected: 3 (text) + 30 (image) + 9 (other) = 42
        self.assertEqual(self.counter.count_tokens(messages), 42)

    @patch("base64.b64decode", side_effect=Exception("decoding failed"))
    def test_count_tokens_with_image_decoding_failure(self, mock_b64decode):
        messages = [
            {"type": "image", "source": {"data": "bad_b64_string"}},
        ]
        # Expecting fallback token count for image (1500)
        with patch('builtins.print') as mock_print: # Suppress print warning during test
            self.assertEqual(self.counter.count_tokens(messages), 1500)
        mock_print.assert_called_once() # Check that the warning was printed

    def test_count_tokens_with_empty_list(self):
        self.assertEqual(self.counter.count_tokens([]), 0)

    def test_count_tokens_with_unsupported_type(self):
        with self.assertRaises(ValueError) as context:
            self.counter.count_tokens(12345)
        self.assertIn("Unsupported type for token counting", str(context.exception))

    @patch("base64.b64decode")
    @patch("PIL.Image.open")
    def test_count_tokens_image_calculation_precision(self, mock_image_open, mock_b64decode):
        # Test case where width * height is not perfectly divisible by 750
        mock_b64decode.return_value = b"img_data"
        mock_img_instance = MagicMock()
        mock_img_instance.size = (100, 100) # (100*100)/750 = 10000/750 = 13.33... -> 13 tokens (due to int())
        mock_image_open.return_value.__enter__.return_value = mock_img_instance
        messages = [{"type": "image", "source": {"data": "b64"}}]
        self.assertEqual(self.counter.count_tokens(messages), 13)

if __name__ == "__main__":
    unittest.main()
