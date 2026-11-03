"""Tests for the plain language explanations."""

from __future__ import annotations

import unittest

from cronport.explain import explain
from cronport.expr import CronExpression


def summary(expression: str, language: str = "en") -> str:
    result = explain(CronExpression.parse(expression))
    return result.summary_en if language == "en" else result.summary_zh


class EnglishTests(unittest.TestCase):
    def test_weekday_morning(self) -> None:
        self.assertEqual(summary("0 9 * * 1-5"), "At 09:00 on Monday to Friday")

    def test_every_quarter_of_an_hour(self) -> None:
        self.assertEqual(summary("*/15 * * * *"), "Every 15 minutes, every day")

    def test_midnight(self) -> None:
        self.assertEqual(summary("0 0 * * *"), "At 00:00, every day")

    def test_the_or_rule_is_spelled_out(self) -> None:
        self.assertEqual(
            summary("0 0 13 * 5"), "At 00:00 on the 13th of the month or on Friday"
        )

    def test_first_of_the_month(self) -> None:
        self.assertEqual(summary("0 0 1 * *"), "At 00:00 on the 1st of the month")

    def test_a_month_is_mentioned(self) -> None:
        self.assertEqual(
            summary("0 0 30 2 *"), "At 00:00 on the 30th of the month in February"
        )

    def test_every_minute(self) -> None:
        self.assertEqual(summary("* * * * *"), "Every minute, every day")

    def test_the_pattern_is_recognised(self) -> None:
        result = explain(CronExpression.parse("0 9 * * 1-5"))
        self.assertEqual(result.pattern_en, "weekdays at 09:00")


class ChineseTests(unittest.TestCase):
    def test_weekday_morning(self) -> None:
        self.assertEqual(summary("0 9 * * 1-5", "zh"), "周一至周五 09:00")

    def test_every_quarter_of_an_hour(self) -> None:
        self.assertEqual(summary("*/15 * * * *", "zh"), "每天每 15 分钟")

    def test_the_or_rule_is_spelled_out(self) -> None:
        self.assertEqual(summary("0 0 13 * 5", "zh"), "每月 13 号，或每周五 00:00")

    def test_first_of_the_month(self) -> None:
        self.assertEqual(summary("0 0 1 * *", "zh"), "每月 1 号 00:00")

    def test_the_pattern_is_recognised(self) -> None:
        result = explain(CronExpression.parse("0 9 * * 1-5"))
        self.assertEqual(result.pattern_zh, "工作日 09:00")


class FieldTests(unittest.TestCase):
    def test_every_field_is_explained(self) -> None:
        result = explain(CronExpression.parse("0 9 * * 1-5"))
        self.assertEqual(len(result.fields), 5)
        self.assertEqual(result.fields[0].name, "minute")
        self.assertEqual(result.fields[4].name, "day-of-week")

    def test_both_languages_are_present(self) -> None:
        for item in explain(CronExpression.parse("0 9 * * 1-5")).fields:
            self.assertTrue(item.meaning_en)
            self.assertTrue(item.meaning_zh)

    def test_seconds_are_included_when_present(self) -> None:
        result = explain(CronExpression.parse("30 0 9 * * 1-5", allow_seconds=True))
        self.assertEqual(result.fields[0].name, "second")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
