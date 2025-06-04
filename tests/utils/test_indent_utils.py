import unittest
from src.ii_agent.utils.indent_utils import (
    IndentType,
    detect_line_indent,
    detect_indent_type,
    force_normalize_indent,
    normalize_indent,
    apply_indent_type,
    match_indent_by_first_line,
    match_indent,
)

class TestIndentType(unittest.TestCase):
    def test_creation_and_properties(self):
        it_space = IndentType.space(4)
        self.assertTrue(it_space.is_space)
        self.assertFalse(it_space.is_tab)
        self.assertFalse(it_space.is_mixed)
        self.assertEqual(it_space.size, 4)
        self.assertEqual(repr(it_space), "IndentType(space, size=4)")

        it_tab = IndentType.tab()
        self.assertTrue(it_tab.is_tab)
        self.assertFalse(it_tab.is_space)
        self.assertEqual(it_tab.size, 1) # Default for tab
        self.assertEqual(repr(it_tab), "IndentType(tab)")

        it_mixed_n = IndentType.mixed()
        self.assertTrue(it_mixed_n.is_mixed)
        self.assertIsNone(it_mixed_n.most_used)
        self.assertEqual(repr(it_mixed_n), "IndentType(mixed)")

        it_mixed_s = IndentType.mixed(most_used=IndentType.space(2))
        self.assertTrue(it_mixed_s.is_mixed)
        self.assertTrue(it_mixed_s.most_used.is_space)
        self.assertEqual(repr(it_mixed_s), "IndentType(mixed, most_used=IndentType(space, size=2))")


class TestDetectLineIndent(unittest.TestCase):
    def test_detect_line_indent(self):
        self.assertEqual(detect_line_indent("  text"), (0, 2))
        self.assertEqual(detect_line_indent("\ttext"), (1, 0))
        self.assertEqual(detect_line_indent("\t\t  text"), (2, 2))
        self.assertEqual(detect_line_indent("text"), (0, 0))
        self.assertEqual(detect_line_indent(""), (0, 0))
        self.assertEqual(detect_line_indent("    "), (0, 4)) # All whitespace
        self.assertEqual(detect_line_indent("\t\t"), (2,0))
        self.assertEqual(detect_line_indent("  \ttext"), (0,2)) # Tabs after spaces are not leading tabs


class TestDetectIndentType(unittest.TestCase):
    def test_only_spaces(self):
        code = "def foo():\n  bar()"
        self.assertEqual(detect_indent_type(code), IndentType.space(2))
        code_4 = "def foo():\n    bar()"
        self.assertEqual(detect_indent_type(code_4), IndentType.space(4))

    def test_only_tabs(self):
        code = "def foo():\n\tbar()"
        self.assertEqual(detect_indent_type(code), IndentType.tab())

    def test_mixed_tabs_and_spaces_separate_lines(self):
        code = "def foo():\n\tbar()\n  baz()" # Tab line, then space line
        detected = detect_indent_type(code)
        self.assertTrue(detected.is_mixed)
        # Based on current logic: tab_indents=1, space_indents=1. most_used depends on space_diff_counts.
        # Here, prev_indent_level for baz() would be 1 (from \t), prev_indent_type 'tab'.
        # For baz(), current_indent_type 'space', num_spaces 2. diff = abs(2-1) = 1. This is not >1.
        # So space_diff_counts is empty. most_used falls back to space(4).
        self.assertTrue(detected.most_used.is_space)
        self.assertEqual(detected.most_used.size, 4)


    def test_mixed_indent_in_one_line(self):
        code = "def foo():\n\t  bar()" # Tab then spaces on same line
        detected = detect_indent_type(code)
        self.assertTrue(detected.is_mixed)
        # Here, tab_indents=1, space_indents=0, but mixed_indent_in_one_line is True.
        # most_used logic: tab_indents > space_indents, so most_used is tab.
        self.assertTrue(detected.most_used.is_tab)


    def test_no_indentation(self):
        code = "line1\nline2"
        self.assertIsNone(detect_indent_type(code))
        code_empty = "\n\n"
        self.assertIsNone(detect_indent_type(code_empty))

    def test_none_or_empty_code(self):
        self.assertIsNone(detect_indent_type(None))
        self.assertIsNone(detect_indent_type(""))

    def test_single_indented_line_spaces(self):
        code = "  foo"
        # No diffs calculated, so defaults. This behavior might be arguable.
        # Current logic: space_indents=1, tab_indents=0. space_diff_counts is empty. Returns None.
        self.assertIsNone(detect_indent_type(code))

    def test_single_indented_line_tabs(self):
        code = "\tfoo"
        self.assertEqual(detect_indent_type(code), IndentType.tab())


class TestForceNormalizeIndent(unittest.TestCase):
    def test_tabs_to_4_spaces(self):
        code = "def foo():\n\tbar\n\t\tbaz"
        expected = "def foo():\n    bar\n        baz"
        self.assertEqual(force_normalize_indent(code), expected)

    def test_2_spaces_to_4_spaces(self):
        # force_normalize_indent's logic is based on detect_line_indent,
        # which counts tabs first, then spaces. It doesn't "understand" levels from spaces.
        # It literally converts leading tabs to 4 spaces each, and preserves other leading spaces.
        code = "def foo():\n  bar\n    baz"
        expected = "def foo():\n  bar\n    baz" # No change if no tabs are present.
        self.assertEqual(force_normalize_indent(code), expected)

    def test_mixed_to_4_spaces(self):
        code = "def foo():\n\t  bar" # 1 tab, 2 spaces
        expected = "def foo():\n      bar"  # tab -> 4 spaces, then 2 original spaces
        self.assertEqual(force_normalize_indent(code), expected)

    def test_empty_lines_and_no_indent(self):
        code = "line1\n\n  line2 (indented with spaces)\n\tline3 (tabbed)"
        expected = "line1\n\n  line2 (indented with spaces)\n    line3 (tabbed)"
        self.assertEqual(force_normalize_indent(code), expected)


class TestNormalizeIndent(unittest.TestCase):
    def test_tabs_to_4_spaces(self):
        code = "def f():\n\titem1\n\t\titem2"
        indent_type = IndentType.tab()
        expected = "def f():\n    item1\n        item2"
        self.assertEqual(normalize_indent(code, indent_type), expected)

    def test_2_spaces_to_4_spaces(self):
        code = "def f():\n  item1\n    item2" # item2 is 2 levels of 2-space
        indent_type = IndentType.space(2)
        expected = "def f():\n    item1\n        item2"
        self.assertEqual(normalize_indent(code, indent_type), expected)

    def test_mixed_indent_assertion(self):
        with self.assertRaises(AssertionError):
            normalize_indent("code", IndentType.mixed())

    def test_remainder_spaces_preservation(self):
        code = "def f():\n  item1\n   item1_child" # item1_child has 1 extra space
        indent_type = IndentType.space(2)
        # Expected: item1 at 4 spaces, item1_child at 4 spaces + 1 remainder
        expected = "def f():\n    item1\n     item1_child"
        self.assertEqual(normalize_indent(code, indent_type), expected)

        code_tab = "def f():\n\titem1\n\t item1_child" # item1_child has 1 extra space after tab
        indent_type_tab = IndentType.tab()
        expected_tab = "def f():\n    item1\n     item1_child"
        self.assertEqual(normalize_indent(code_tab, indent_type_tab), expected_tab)


class TestApplyIndentType(unittest.TestCase):
    def test_spaces_to_tabs(self):
        code = "def f():\n    item1\n        item2"
        original_type = IndentType.space(4)
        target_type = IndentType.tab()
        expected = "def f():\n\titem1\n\t\titem2"
        self.assertEqual(apply_indent_type(code, target_type, original_type), expected)

    def test_tabs_to_2_spaces(self):
        code = "def f():\n\titem1\n\t\titem2"
        original_type = IndentType.tab()
        target_type = IndentType.space(2)
        expected = "def f():\n  item1\n    item2"
        self.assertEqual(apply_indent_type(code, target_type, original_type), expected)

    def test_auto_detect_original_and_apply(self):
        code = "def f():\n  item1" # Original is space(2)
        target_type = IndentType.tab()
        # detect_indent_type for "def f():\n  item1" will be IndentType.space(2)
        expected = "def f():\n\titem1"
        self.assertEqual(apply_indent_type(code, target_type), expected)

    def test_apply_to_mixed_or_undetectable_original_returns_original(self):
        code_mixed = "def f():\n\t  item1" # Mixed on one line, or mixed across lines
        target_type = IndentType.tab()
        # detect_indent_type will return IndentType.mixed(...)
        self.assertEqual(apply_indent_type(code_mixed, target_type), code_mixed)

        code_no_clear_indent = "item1\nitem2"
        self.assertEqual(apply_indent_type(code_no_clear_indent, target_type), code_no_clear_indent)


class TestMatchIndentByFirstLine(unittest.TestCase):
    def test_increase_indent(self):
        code = "line1\n  line2"
        match_line = "    target_indent"
        expected = "    line1\n      line2" # line1 matches target, line2 keeps relative 2 spaces
        self.assertEqual(match_indent_by_first_line(code, match_line), expected)

    def test_decrease_indent(self):
        code = "    line1\n      line2"
        match_line = "  target_indent"
        expected = "  line1\n    line2"
        self.assertEqual(match_indent_by_first_line(code, match_line), expected)

    def test_no_change_indent(self):
        code = "  line1"
        match_line = "  target"
        self.assertEqual(match_indent_by_first_line(code, match_line), code)

    def test_target_no_indent(self):
        code = "  line1\n    line2"
        match_line = "target"
        expected = "line1\n  line2"
        self.assertEqual(match_indent_by_first_line(code, match_line), expected)


class TestMatchIndent(unittest.TestCase):
    def test_match_to_tabs(self):
        code_to_match = "def foo():\n\tbar()" # Tab indented
        code_to_change = "class C:\n    pass_stmt" # Space indented
        expected = "class C:\n\tpass_stmt"
        self.assertEqual(match_indent(code_to_change, code_to_match), expected)

    def test_match_to_spaces(self):
        code_to_match = "def foo():\n  bar()" # 2-space indented
        code_to_change = "class C:\n\tpass_stmt" # Tab indented
        expected = "class C:\n  pass_stmt"
        self.assertEqual(match_indent(code_to_change, code_to_match), expected)

    def test_match_to_mixed_uses_most_used(self):
        # most_used in this case (1 tab line, 1 space line) defaults to IndentType.space(4)
        code_to_match = "def foo():\n\titem_tab\n    item_space_4"
        code_to_change = "class C:\n\tpass_stmt" # Tab indented
        expected = "class C:\n    pass_stmt" # Should become 4-space
        self.assertEqual(match_indent(code_to_change, code_to_match), expected)


if __name__ == "__main__":
    unittest.main()
