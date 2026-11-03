"""Tests for parsing whole expressions."""

from __future__ import annotations

import unittest

from cronport.errors import CronSyntaxError
from cronport.expr import CronExpression, DaySemantics


class ParseTests(unittest.TestCase):
    def test_five_fields(self) -> None:
        expression = CronExpression.parse("0 9 * * 1-5")
        self.assertEqual(expression.minute.values, frozenset({0}))
        self.assertEqual(expression.hour.values, frozenset({9}))
        self.assertEqual(expression.dow.values, frozenset({1, 2, 3, 4, 5}))
        self.assertFalse(expression.has_seconds)

    def test_too_few_fields(self) -> None:
        with self.assertRaises(CronSyntaxError):
            CronExpression.parse("0 9 * *")

    def test_too_many_fields_for_cron(self) -> None:
        with self.assertRaises(CronSyntaxError):
            CronExpression.parse("0 0 9 * * 1")

    def test_six_fields_when_seconds_are_allowed(self) -> None:
        expression = CronExpression.parse("30 0 9 * * 1-5", allow_seconds=True)
        self.assertTrue(expression.has_seconds)
        self.assertEqual(expression.second.values, frozenset({30}))

    def test_seven_fields_with_a_year(self) -> None:
        expression = CronExpression.parse("0 0 9 * * 1-5 2027", allow_seconds=True)
        self.assertIsNotNone(expression.year)
        self.assertEqual(expression.year.values, frozenset({2027}))

    def test_macros_expand(self) -> None:
        self.assertEqual(CronExpression.parse("@daily").canonical(), "0 0 * * *")
        self.assertEqual(CronExpression.parse("@hourly").canonical(), "0 * * * *")
        self.assertEqual(CronExpression.parse("@weekly").canonical(), "0 0 * * 0")
        self.assertEqual(CronExpression.parse("@monthly").canonical(), "0 0 1 * *")
        self.assertEqual(CronExpression.parse("@yearly").canonical(), "0 0 1 1 *")

    def test_unknown_macro(self) -> None:
        with self.assertRaises(CronSyntaxError):
            CronExpression.parse("@sometimes")

    def test_reboot_is_not_a_schedule(self) -> None:
        with self.assertRaises(CronSyntaxError):
            CronExpression.parse("@reboot")

    def test_empty_expression(self) -> None:
        with self.assertRaises(CronSyntaxError):
            CronExpression.parse("   ")

    def test_canonical_form_round_trips(self) -> None:
        for text in [
            "0 9 * * 1-5",
            "*/15 * * * *",
            "0 0 1 jan *",
            "0,15,30,45 9-17 * * 1-5",
        ]:
            once = CronExpression.parse(text)
            twice = CronExpression.parse(once.canonical())
            self.assertEqual(once.signature(), twice.signature(), text)

    def test_canonical_keeps_a_written_out_full_range(self) -> None:
        # "1-31" and "*" behave differently, so the canonical form must not
        # quietly rewrite one into the other.
        expression = CronExpression.parse("0 0 1-31 * *")
        self.assertIn("1-31", expression.canonical())

    def test_quartz_uses_and_semantics(self) -> None:
        expression = CronExpression.parse("0 0 9 ? * 1-5 *", dialect="quartz", allow_seconds=True)
        self.assertIs(expression.day_semantics, DaySemantics.AND)

    def test_cron_uses_or_semantics(self) -> None:
        expression = CronExpression.parse("0 0 9 * 1-5")
        self.assertIs(expression.day_semantics, DaySemantics.OR)

    def test_to_dict_is_serialisable(self) -> None:
        payload = CronExpression.parse("0 9 * * 1-5").to_dict()
        self.assertEqual(payload["canonical"], "0 9 * * 1-5")
        self.assertEqual(payload["day_semantics"], "or")
        self.assertIn("fields", payload)


class MatchTests(unittest.TestCase):
    def test_simple_match(self) -> None:
        from datetime import datetime

        expression = CronExpression.parse("0 9 * * 1-5")
        self.assertTrue(expression.matches(datetime(2026, 11, 4, 9, 0)))
        self.assertFalse(expression.matches(datetime(2026, 11, 4, 9, 1)))
        self.assertFalse(expression.matches(datetime(2026, 11, 7, 9, 0)))

    def test_day_of_month_or_day_of_week(self) -> None:
        from datetime import datetime

        expression = CronExpression.parse("0 0 13 * 5")
        # The 13th of the month ...
        self.assertTrue(expression.matches(datetime(2026, 11, 13, 0, 0)))
        # ... OR any Friday.
        self.assertTrue(expression.matches(datetime(2026, 11, 6, 0, 0)))
        # A Thursday that is not the 13th does not match.
        self.assertFalse(expression.matches(datetime(2026, 11, 5, 0, 0)))

    def test_quartz_and_semantics(self) -> None:
        from datetime import datetime

        expression = CronExpression.parse(
            "0 0 9 13 * 5 *", dialect="quartz", allow_seconds=True
        )
        self.assertTrue(expression.matches(datetime(2026, 11, 13, 9, 0)))
        self.assertFalse(expression.matches(datetime(2026, 11, 6, 9, 0)))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
