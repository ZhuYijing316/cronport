"""Tests for the terminal rendering helpers."""

from __future__ import annotations

import unittest

from cronport.render import Theme, display_width, pad, truncate


class WidthTests(unittest.TestCase):
    def test_ascii(self) -> None:
        self.assertEqual(display_width("abc"), 3)

    def test_chinese_is_twice_as_wide(self) -> None:
        self.assertEqual(display_width("中文"), 4)

    def test_mixed(self) -> None:
        self.assertEqual(display_width("a中"), 3)

    def test_padding_uses_display_width(self) -> None:
        self.assertEqual(display_width(pad("中", 6)), 6)
        self.assertEqual(display_width(pad("ab", 6)), 6)

    def test_right_alignment(self) -> None:
        self.assertTrue(pad("x", 4, "right").startswith("   "))

    def test_truncate(self) -> None:
        self.assertEqual(truncate("abcdef", 10), "abcdef")
        self.assertLessEqual(display_width(truncate("abcdefghij", 5)), 5)


class ThemeTests(unittest.TestCase):
    def test_colour_can_be_switched_off(self) -> None:
        theme = Theme(color=False)
        self.assertEqual(theme.title("hello"), "hello")
        self.assertNotIn("\033[", theme.title("hello"))

    def test_colour_can_be_switched_on(self) -> None:
        theme = Theme(color=True)
        self.assertIn("\033[", theme.title("hello"))

    def test_ascii_symbols(self) -> None:
        theme = Theme(color=False, ascii_only=True)
        self.assertEqual(theme.symbol("warning"), "!")
        theme = Theme(color=False, ascii_only=False)
        self.assertEqual(theme.symbol("warning"), "⚠")

    def test_table_lines_up(self) -> None:
        theme = Theme(color=False)
        table = theme.table(["name", "value"], [["minute", "0"], ["day-of-week", "1-5"]])
        lines = table.splitlines()
        self.assertTrue(all(display_width(line) == display_width(lines[0]) for line in lines))

    def test_table_lines_up_with_chinese(self) -> None:
        theme = Theme(color=False)
        table = theme.table(
            ["字段", "含义"], [["分钟", "每 15 分钟"], ["星期", "周一至周五"]]
        )
        lines = table.splitlines()
        self.assertTrue(all(display_width(line) == display_width(lines[0]) for line in lines))

    def test_table_with_no_rows(self) -> None:
        theme = Theme(color=False)
        table = theme.table(["name"], [])
        self.assertIn("name", table)

    def test_key_values(self) -> None:
        theme = Theme(color=False)
        block = theme.key_values([("a", "1"), ("bb", "2")])
        self.assertIn("a", block)
        self.assertIn("2", block)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
