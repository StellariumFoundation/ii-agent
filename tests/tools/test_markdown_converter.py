import unittest
from unittest.mock import MagicMock, patch
import tempfile
import os

# The main class to test is MarkdownConverter
from src.ii_agent.tools.markdown_converter import MarkdownConverter, DocumentConverterResult

# We are testing the conversion of HTML to Markdown,
# so we'll primarily be exercising the HtmlConverter logic within MarkdownConverter.

class TestMarkdownConverterHtmlToMd(unittest.TestCase):
    def setUp(self):
        self.converter = MarkdownConverter()

    def _write_to_temp_file(self, content, extension=".html"):
        # Helper to write content to a temporary file and return its path
        fd, path = tempfile.mkstemp(suffix=extension)
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(content)
        return path

    def test_convert_html_headings(self):
        html_content = "<h1>Title 1</h1><h2>Title 2</h2><h3>Title 3</h3>"
        path = self._write_to_temp_file(html_content)
        result = self.converter.convert_local(path)
        os.unlink(path)

        self.assertIsInstance(result, DocumentConverterResult)
        # _CustomMarkdownify adds a newline before headings if not convert_as_inline
        # and the convert_hn ensures a newline start.
        expected_md = "\n# Title 1\n\n## Title 2\n\n### Title 3"
        self.assertEqual(result.text_content.strip(), expected_md.strip())


    def test_convert_html_lists(self):
        html_content = "<ul><li>Item 1</li><li>Item 2</li></ul><ol><li>First</li><li>Second</li></ol>"
        path = self._write_to_temp_file(html_content)
        result = self.converter.convert_local(path)
        os.unlink(path)

        expected_lines = [
            "* Item 1", # Markdownify can produce different list markers/spacing
            "* Item 2",
            "1. First",
            "2. Second"
        ]
        # Normalize whitespace and check for presence of items
        result_lines = {line.strip() for line in result.text_content.splitlines() if line.strip()}
        for expected_line in expected_lines:
            self.assertTrue(any(expected_line in res_line for res_line in result_lines), f"Expected '{expected_line}' not found in output")


    def test_convert_html_emphasis(self):
        html_content = "<p><strong>Bold text</strong> and <em>italic text</em> and <b>b tag</b> and <i>i tag</i>.</p>"
        path = self._write_to_temp_file(html_content)
        result = self.converter.convert_local(path)
        os.unlink(path)

        # markdownify typically converts <strong> to ** and <em> to *
        # <b> and <i> are also often converted similarly by default.
        expected_snippets = ["**Bold text**", "*italic text*", "**b tag**", "*i tag*"]
        for snippet in expected_snippets:
            self.assertIn(snippet, result.text_content)

    def test_convert_html_links(self):
        html_content = '<a href="http://example.com" title="Example Domain">Example</a>'
        path = self._write_to_temp_file(html_content)
        result = self.converter.convert_local(path)
        os.unlink(path)

        expected_md = '[Example](http_example.com "Example Domain")' # markdownify might escape http://
        # More robust check:
        self.assertIn("[Example](http", result.text_content)
        self.assertIn("example.com", result.text_content)
        self.assertIn('"Example Domain")', result.text_content)


    def test_convert_html_images_no_url_prefix_handling_in_this_lib(self):
        # The _CustomMarkdownify truncates data URIs and keeps other src as is.
        # There's no url_prefix logic in the provided code for image paths.
        html_content = '<img src="image.jpg" alt="Alt text" title="Image Title">'
        path = self._write_to_temp_file(html_content)
        result = self.converter.convert_local(path)
        os.unlink(path)

        expected_md = '![Alt text](image.jpg "Image Title")'
        self.assertIn(expected_md, result.text_content)

    def test_convert_html_code_blocks(self):
        html_content = "<pre><code>def hello():\n  print('world')</code></pre>"
        path = self._write_to_temp_file(html_content)
        result = self.converter.convert_local(path)
        os.unlink(path)

        # Markdownify usually converts <pre><code> to indented code blocks or fenced code blocks
        # Expecting fenced:
        expected_md_fenced = "```\ndef hello():\n  print('world')\n```"
        # Or indented (less common now):
        # expected_md_indented_lines = ["    def hello():", "      print('world')"]

        # Normalize newlines and check
        normalized_result = result.text_content.replace('\r\n', '\n').strip()
        self.assertTrue(normalized_result.startswith("```") and normalized_result.endswith("```"))
        self.assertIn("def hello():\n  print('world')", normalized_result)


    def test_convert_empty_html_input(self):
        html_content = ""
        path = self._write_to_temp_file(html_content)
        result = self.converter.convert_local(path)
        os.unlink(path)

        self.assertEqual(result.text_content.strip(), "")

    def test_convert_html_with_scripts_and_styles(self):
        html_content = """
        <style>body { color: red; }</style>
        <script>alert('hello');</script>
        <p>Visible text.</p>
        """
        path = self._write_to_temp_file(html_content)
        result = self.converter.convert_local(path)
        os.unlink(path)

        self.assertEqual(result.text_content.strip(), "Visible text.") # Scripts and styles should be removed
        self.assertNotIn("color: red", result.text_content)
        self.assertNotIn("alert('hello')", result.text_content)

    def test_convert_non_html_file_handled_by_plaintext_or_error(self):
        # If we pass a .txt file, PlainTextConverter should handle it.
        # If we pass a .txt file but force file_extension=".html", HtmlConverter might try
        # and produce empty or minimal output if it's not valid HTML.

        # Case 1: .txt file, PlainTextConverter should pick it up.
        text_content = "This is plain text."
        path_txt = self._write_to_temp_file(text_content, extension=".txt")
        result_txt = self.converter.convert_local(path_txt)
        os.unlink(path_txt)
        self.assertEqual(result_txt.text_content.strip(), text_content)

        # Case 2: .other_ext file, PlainTextConverter might still pick it up if content_type is text/*
        # Forcing it via file_extension kwarg would be a more specific test for HtmlConverter
        # but convert_local infers extension.
        # If we give it a non-html file with .html extension:
        malformed_html_content = "This is not really<html> <p>html."
        path_malformed = self._write_to_temp_file(malformed_html_content, extension=".html")
        result_malformed = self.converter.convert_local(path_malformed)
        os.unlink(path_malformed)
        # BeautifulSoup is robust, it will try to parse it.
        # _CustomMarkdownify will then convert what it can.
        self.assertIn("This is not reallyhtml.", result_malformed.text_content.replace("\n", " "))


if __name__ == "__main__":
    unittest.main()
