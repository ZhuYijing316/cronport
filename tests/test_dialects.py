"""Tests for the dialect conversions."""

from __future__ import annotations

import unittest

from cronport.dialects import DIALECTS, convert, get_dialect, list_dialects, parse_in
from cronport.errors import UnknownDialectError
from cronport.expr import CronExpression
from cronport.notes import LEVEL_ERROR


class DialectRegistryTests(unittest.TestCase):
    def test_every_expected_dialect_exists(self) -> None:
        self.assertEqual(
            set(DIALECTS),
            {
                "cron",
                "systemd",
                "kubernetes",
                "github-actions",
                "aws-eventbridge",
                "quartz",
                "gcp-scheduler",
            },
        )

    def test_aliases_resolve(self) -> None:
        self.assertEqual(get_dialect("k8s").name, "kubernetes")
        self.assertEqual(get_dialect("gh-actions").name, "github-actions")
        self.assertEqual(get_dialect("aws").name, "aws-eventbridge")

    def test_unknown_dialect(self) -> None:
        with self.assertRaises(UnknownDialectError):
            get_dialect("nonsense")

    def test_list_dialects_returns_all(self) -> None:
        self.assertEqual(len(list_dialects()), len(DIALECTS))


class ConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.weekday = CronExpression.parse("0 9 * * 1-5")

    def test_cron(self) -> None:
        self.assertEqual(convert(self.weekday, "cron").expression, "0 9 * * 1-5")

    def test_systemd(self) -> None:
        self.assertEqual(
            convert(self.weekday, "systemd").expression, "Mon..Fri *-*-* 09:00:00"
        )

    def test_systemd_step(self) -> None:
        expression = CronExpression.parse("*/15 * * * *")
        self.assertEqual(convert(expression, "systemd").expression, "*-*-* *:0/15:00")

    def test_systemd_day_of_month(self) -> None:
        expression = CronExpression.parse("0 0 1 * *")
        self.assertEqual(convert(expression, "systemd").expression, "*-*-01 00:00:00")

    def test_systemd_month(self) -> None:
        expression = CronExpression.parse("0 0 15 1,7 *")
        self.assertEqual(convert(expression, "systemd").expression, "*-01,07-15 00:00:00")

    def test_systemd_needs_two_lines_for_the_or_rule(self) -> None:
        # cron fires on the 13th OR on Friday; systemd ANDs the two fields,
        # so the faithful translation is two OnCalendar= lines.
        expression = CronExpression.parse("0 0 13 * 5")
        result = convert(expression, "systemd")
        self.assertEqual(result.expression.count("\n"), 1)
        self.assertIn("*-*-13 00:00:00", result.expression)
        self.assertIn("Fri *-*-* 00:00:00", result.expression)

    def test_systemd_timezone_is_appended_to_every_line(self) -> None:
        expression = CronExpression.parse("0 0 13 * 5")
        result = convert(expression, "systemd", tz="Asia/Shanghai")
        for line in result.expression.splitlines():
            self.assertTrue(line.endswith("Asia/Shanghai"), line)

    def test_kubernetes(self) -> None:
        result = convert(self.weekday, "kubernetes", tz="Asia/Shanghai")
        self.assertEqual(result.expression, "0 9 * * 1-5")
        self.assertEqual(result.extras["timeZone"], "Asia/Shanghai")

    def test_github_actions_warns_about_utc(self) -> None:
        result = convert(self.weekday, "github-actions")
        self.assertEqual(result.expression, "0 9 * * 1-5")
        self.assertTrue(any("UTC" in note.message for note in result.notes))

    def test_github_actions_drops_seconds(self) -> None:
        expression = CronExpression.parse("0 0 9 * * 1-5", allow_seconds=True)
        result = convert(expression, "github-actions")
        self.assertEqual(result.expression, "0 9 * * 1-5")
        self.assertTrue(any("seconds" in note.message for note in result.notes))

    def test_aws_eventbridge_uses_a_question_mark(self) -> None:
        result = convert(self.weekday, "aws-eventbridge")
        self.assertEqual(result.expression, "cron(0 9 ? * 1-5 *)")

    def test_aws_eventbridge_cannot_express_the_or_rule(self) -> None:
        expression = CronExpression.parse("0 0 13 * 5")
        result = convert(expression, "aws-eventbridge")
        self.assertTrue(result.has_errors)
        self.assertTrue(any(note.level == LEVEL_ERROR for note in result.notes))

    def test_quartz(self) -> None:
        result = convert(self.weekday, "quartz")
        self.assertEqual(result.expression, "0 0 9 ? * 1-5 *")

    def test_quartz_keeps_the_seconds_field(self) -> None:
        expression = CronExpression.parse("30 0 9 * * 1-5", allow_seconds=True)
        result = convert(expression, "quartz")
        self.assertEqual(result.expression, "30 0 9 ? * 1-5 *")

    def test_gcp_scheduler(self) -> None:
        result = convert(self.weekday, "gcp-scheduler", tz="Europe/Berlin")
        self.assertEqual(result.expression, "0 9 * * 1-5")
        self.assertEqual(result.extras["timeZone"], "Europe/Berlin")

    def test_every_dialect_produces_something(self) -> None:
        for dialect in list_dialects():
            result = convert(self.weekday, dialect.name)
            self.assertTrue(result.expression, dialect.name)


class ParseInTests(unittest.TestCase):
    def test_parse_cron(self) -> None:
        expression = parse_in("cron", "0 9 * * 1-5")
        self.assertEqual(expression.canonical(), "0 9 * * 1-5")

    def test_parse_systemd(self) -> None:
        expression = parse_in("systemd", "*-*-* 03:00:00")
        self.assertEqual(expression.canonical(), "0 3 * * *")

    def test_parse_systemd_weekday(self) -> None:
        expression = parse_in("systemd", "Mon..Fri *-*-* 09:00:00")
        self.assertEqual(expression.canonical(), "0 9 * * 1-5")

    def test_parse_systemd_shorthand(self) -> None:
        expression = parse_in("systemd", "daily")
        self.assertEqual(expression.canonical(), "0 0 * * *")

    def test_parse_systemd_step(self) -> None:
        expression = parse_in("systemd", "*:0/15")
        self.assertEqual(expression.minute.values, frozenset({0, 15, 30, 45}))

    def test_parse_systemd_keeps_an_unrestricted_day_unrestricted(self) -> None:
        # If the day of month were written out as 1-31, cron would apply its
        # OR rule to the two day fields and fire far more often.
        expression = parse_in("systemd", "*-*-* 03:00:00")
        self.assertTrue(expression.dom.is_star)
        self.assertTrue(expression.dow.is_star)

    def test_parse_systemd_notes_the_and_rule(self) -> None:
        expression = parse_in("systemd", "Mon..Fri *-*-01 09:00:00")
        self.assertTrue(expression.notes)

    def test_parse_aws(self) -> None:
        expression = parse_in("aws-eventbridge", "cron(0 9 ? * 1-5 *)")
        self.assertEqual(expression.canonical(), "0 9 * * 1-5")

    def test_parse_quartz(self) -> None:
        expression = parse_in("quartz", "0 0 9 ? * 1-5 *")
        self.assertEqual(expression.minute.values, frozenset({0}))


class RoundTripTests(unittest.TestCase):
    def test_cron_to_systemd_and_back_keeps_the_schedule(self) -> None:
        original = CronExpression.parse("0 9 * * 1-5")
        rendered = convert(original, "systemd").expression
        back = parse_in("systemd", rendered)
        self.assertTrue(original.is_equivalent_to(back))

    def test_aws_to_cron_and_back_keeps_the_schedule(self) -> None:
        original = CronExpression.parse("0 9 * * 1-5")
        rendered = convert(original, "aws-eventbridge").expression
        back = parse_in("aws-eventbridge", rendered)
        self.assertTrue(original.is_equivalent_to(back))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
