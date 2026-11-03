"""Tests for parsing individual cron fields.

The tests are written with :mod:`unittest` so that the whole suite runs with
nothing but the standard library::

    python -m unittest discover -s tests

``pytest`` collects them just as happily, and is configured in
``pyproject.toml`` for contributors who prefer it.
"""

from __future__ import annotations

import unittest

from cronport.errors import CronSyntaxError
from cronport.fields import (
    DOW_ALIASES,
    MONTH_ALIASES,
    compress,
    format_field,
    parse_field,
)


class ParseFieldTests(unittest.TestCase):
    def test_star_expands_to_the_whole_range(self) -> None:
        spec = parse_field("*", "minute", 0, 59)
        self.assertEqual(spec.values, frozenset(range(60)))
        self.assertTrue(spec.is_star)
        self.assertTrue(spec.covers_entire_range)

    def test_single_value(self) -> None:
        spec = parse_field("7", "minute", 0, 59)
        self.assertEqual(spec.values, frozenset({7}))

    def test_range(self) -> None:
        spec = parse_field("1-5", "day-of-week", 0, 6)
        self.assertEqual(spec.values, frozenset({1, 2, 3, 4, 5}))

    def test_list(self) -> None:
        spec = parse_field("0,15,30,45", "minute", 0, 59)
        self.assertEqual(spec.values, frozenset({0, 15, 30, 45}))

    def test_step_over_the_whole_range(self) -> None:
        spec = parse_field("*/15", "minute", 0, 59)
        self.assertEqual(spec.values, frozenset({0, 15, 30, 45}))

    def test_step_over_a_range(self) -> None:
        spec = parse_field("0-30/5", "minute", 0, 59)
        self.assertEqual(spec.values, frozenset({0, 5, 10, 15, 20, 25, 30}))

    def test_step_from_a_value_to_the_end(self) -> None:
        spec = parse_field("5/15", "minute", 0, 59)
        self.assertEqual(spec.values, frozenset({5, 20, 35, 50}))

    def test_month_names(self) -> None:
        spec = parse_field("jan,mar,dec", "month", 1, 12, aliases=MONTH_ALIASES)
        self.assertEqual(spec.values, frozenset({1, 3, 12}))

    def test_weekday_names(self) -> None:
        spec = parse_field("mon-fri", "day-of-week", 0, 6, aliases=DOW_ALIASES)
        self.assertEqual(spec.values, frozenset({1, 2, 3, 4, 5}))

    def test_names_are_case_insensitive(self) -> None:
        spec = parse_field("JAN", "month", 1, 12, aliases=MONTH_ALIASES)
        self.assertEqual(spec.values, frozenset({1}))

    def test_question_mark_is_only_allowed_when_requested(self) -> None:
        with self.assertRaises(CronSyntaxError):
            parse_field("?", "day-of-month", 1, 31)
        spec = parse_field("?", "day-of-month", 1, 31, allow_question=True)
        self.assertTrue(spec.is_question)
        self.assertTrue(spec.unconstrained)

    def test_value_above_the_range_is_rejected(self) -> None:
        with self.assertRaises(CronSyntaxError) as caught:
            parse_field("25", "hour", 0, 23)
        self.assertIn("out of range", str(caught.exception))

    def test_zero_step_is_rejected(self) -> None:
        with self.assertRaises(CronSyntaxError):
            parse_field("*/0", "minute", 0, 59)

    def test_reversed_range_is_rejected(self) -> None:
        with self.assertRaises(CronSyntaxError):
            parse_field("5-1", "minute", 0, 59)

    def test_unknown_name_is_rejected(self) -> None:
        with self.assertRaises(CronSyntaxError):
            parse_field("xyz", "day-of-week", 0, 6, aliases=DOW_ALIASES)

    def test_long_name_is_rejected(self) -> None:
        with self.assertRaises(CronSyntaxError):
            parse_field("monday", "day-of-week", 0, 6, aliases=DOW_ALIASES)

    def test_empty_field_is_rejected(self) -> None:
        with self.assertRaises(CronSyntaxError):
            parse_field("", "minute", 0, 59)

    def test_empty_term_is_rejected(self) -> None:
        with self.assertRaises(CronSyntaxError):
            parse_field("1,,2", "minute", 0, 59)


class CompressTests(unittest.TestCase):
    def test_single_value(self) -> None:
        self.assertEqual(compress([5]), "5")

    def test_contiguous_range(self) -> None:
        self.assertEqual(compress([1, 2, 3, 4, 5]), "1-5")

    def test_mixed(self) -> None:
        self.assertEqual(compress([1, 2, 3, 7, 9, 10]), "1-3,7,9-10")

    def test_empty(self) -> None:
        self.assertEqual(compress([]), "")


class FormatFieldTests(unittest.TestCase):
    def test_a_literal_star_stays_a_star(self) -> None:
        spec = parse_field("*", "minute", 0, 59)
        self.assertEqual(format_field(spec), "*")

    def test_a_full_range_written_out_stays_written_out(self) -> None:
        # "1-31" and "*" are not interchangeable in cron: the difference is
        # what decides between the OR and the AND rule for the two day fields.
        spec = parse_field("1-31", "day-of-month", 1, 31)
        self.assertEqual(format_field(spec), "1-31")

    def test_question_mark(self) -> None:
        spec = parse_field("?", "day-of-month", 1, 31, allow_question=True)
        self.assertEqual(format_field(spec), "?")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
