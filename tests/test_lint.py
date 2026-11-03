"""Tests for the linter."""

from __future__ import annotations

import unittest

from cronport.dialects import get_dialect
from cronport.expr import CronExpression
from cronport.lint import LintContext, lint


def rule_ids(expression: str, target: str = "cron", tz: str = "Asia/Shanghai"):
    """The set of rule ids that fire for ``expression``."""
    parsed = CronExpression.parse(expression)
    dialect = get_dialect(target)
    context = LintContext(
        target=target,
        tz=tz,
        supports_seconds=dialect.supports_seconds,
        supports_timezone=dialect.supports_timezone,
        supports_macros=dialect.supports_macros,
    )
    return {issue.rule_id for issue in lint(parsed, context)}


class LintTests(unittest.TestCase):
    def test_a_schedule_that_never_fires_is_an_error(self) -> None:
        issues = lint(
            CronExpression.parse("0 0 30 2 *"), LintContext(target="cron", tz="UTC")
        )
        errors = [issue for issue in issues if issue.severity == "error"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].rule_id, "never-fires")

    def test_february_29_is_not_an_error(self) -> None:
        self.assertNotIn("never-fires", rule_ids("0 0 29 2 *"))

    def test_day_31_is_not_an_error(self) -> None:
        self.assertNotIn("never-fires", rule_ids("0 0 31 * *"))

    def test_the_or_rule_is_reported(self) -> None:
        self.assertIn("dom-dow-or", rule_ids("0 0 13 * 5"))
        self.assertNotIn("dom-dow-or", rule_ids("0 0 13 * *"))
        self.assertNotIn("dom-dow-or", rule_ids("0 0 * * 5"))

    def test_an_even_step_is_accepted(self) -> None:
        self.assertNotIn("step-not-even", rule_ids("*/15 * * * *"))
        self.assertNotIn("step-not-even", rule_ids("*/5 * * * *"))

    def test_an_uneven_step_is_reported(self) -> None:
        self.assertIn("step-not-even", rule_ids("*/7 * * * *"))
        self.assertIn("step-not-even", rule_ids("0 */5 * * *"))

    def test_github_actions_utc_warning(self) -> None:
        self.assertIn("utc-only", rule_ids("0 9 * * 1-5", target="github-actions"))
        self.assertNotIn("utc-only", rule_ids("0 9 * * 1-5", target="cron"))

    def test_github_actions_minimum_interval(self) -> None:
        self.assertIn("sub-five-minutes", rule_ids("*/1 * * * *", target="github-actions"))
        self.assertNotIn("sub-five-minutes", rule_ids("*/15 * * * *", target="github-actions"))

    def test_macros_are_not_portable(self) -> None:
        self.assertIn("macro-not-portable", rule_ids("@daily", target="github-actions"))
        self.assertNotIn("macro-not-portable", rule_ids("@daily", target="cron"))

    def test_seconds_are_reported_for_targets_without_them(self) -> None:
        expression = CronExpression.parse("0 0 9 * * 1-5", allow_seconds=True)
        issues = lint(expression, LintContext(target="cron", tz="UTC"))
        self.assertIn("seconds-unsupported", {issue.rule_id for issue in issues})

    def test_leap_day_is_reported(self) -> None:
        self.assertIn("leap-day", rule_ids("0 0 29 2 *"))

    def test_every_minute_is_reported(self) -> None:
        self.assertIn("every-minute", rule_ids("* * * * *"))

    def test_a_clean_schedule_has_no_errors(self) -> None:
        issues = lint(
            CronExpression.parse("30 2 * * 1-5"), LintContext(target="cron", tz="UTC")
        )
        self.assertEqual([issue for issue in issues if issue.severity == "error"], [])

    def test_issues_are_sorted_by_severity(self) -> None:
        issues = lint(
            CronExpression.parse("0 0 30 2 *"), LintContext(target="cron", tz="UTC")
        )
        levels = [issue.severity for issue in issues]
        self.assertEqual(levels, sorted(levels, key=lambda level: {"error": 0, "warning": 1, "info": 2}[level]))

    def test_every_issue_has_both_languages(self) -> None:
        for expression in ["0 0 13 * 5", "0 0 30 2 *", "*/7 * * * *"]:
            for issue in lint(CronExpression.parse(expression), LintContext(tz="UTC")):
                self.assertTrue(issue.message_en)
                self.assertTrue(issue.message_zh)

    def test_a_broken_rule_cannot_break_the_linter(self) -> None:
        from cronport.lint import Rule

        def explode(expression, context):  # pragma: no cover - deliberately broken
            raise RuntimeError("boom")

        from cronport.lint import RULES

        original = list(RULES)
        try:
            RULES.append(
                Rule(
                    id="broken",
                    severity="info",
                    title_en="broken",
                    title_zh="broken",
                    check=explode,
                )
            )
            issues = lint(CronExpression.parse("0 9 * * 1-5"), LintContext(tz="UTC"))
            # A crashing rule is reported, not silently dropped.
            self.assertIn("broken-failed", {issue.rule_id for issue in issues})
        finally:
            RULES[:] = original


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class DriftMessageTests(unittest.TestCase):
    """The drift message has to state the real numbers."""

    def _message(self, expression: str, field: str) -> str:
        for issue in lint(CronExpression.parse(expression), LintContext(tz="UTC")):
            if issue.rule_id == "step-not-even":
                return issue.message_en
        raise AssertionError(f"{field}: no drift issue for {expression!r}")

    def test_minute_drift_gap(self) -> None:
        message = self._message("*/7 * * * *", "minute")
        self.assertIn("4 minutes instead of 7", message)

    def test_hour_drift_gap(self) -> None:
        message = self._message("0 */5 * * *", "hour")
        self.assertIn("4 units instead of 5", message)

    def test_sub_range_drift_gap(self) -> None:
        # 0-30/7 selects 0, 7, 14, 21, 28 -- so the gap back to the next
        # cycle is 32 minutes, not 7.
        message = self._message("0-30/7 * * * *", "minute")
        self.assertIn("32 minutes instead of 7", message)

    def test_chinese_message_is_not_about_minutes_for_hours(self) -> None:
        issues = lint(CronExpression.parse("0 */5 * * *"), LintContext(tz="UTC"))
        message = [i for i in issues if i.rule_id == "step-not-even"][0].message_zh
        self.assertIn("个单位", message)
        self.assertNotIn("分钟", message)
