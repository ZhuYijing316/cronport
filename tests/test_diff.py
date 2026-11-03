"""Tests for schedule equivalence."""

from __future__ import annotations

import unittest

from cronport.expr import CronExpression


def equivalent(left: str, right: str) -> bool:
    return CronExpression.parse(left).is_equivalent_to(CronExpression.parse(right))


class EquivalenceTests(unittest.TestCase):
    def test_identical_expressions(self) -> None:
        self.assertTrue(equivalent("0 9 * * 1-5", "0 9 * * 1-5"))

    def test_a_range_and_a_list(self) -> None:
        self.assertTrue(equivalent("0 9 * * 1-5", "0 9 * * 1,2,3,4,5"))

    def test_a_step_and_a_list(self) -> None:
        self.assertTrue(equivalent("*/15 * * * *", "0,15,30,45 * * * *"))

    def test_all_days_can_be_written_out(self) -> None:
        # "0 9 * * 0-6" and "0 9 * * *" both fire every day.
        self.assertTrue(equivalent("0 9 * * 0-6", "0 9 * * *"))

    def test_different_weekdays(self) -> None:
        self.assertFalse(equivalent("0 9 * * 1-5", "0 9 * * 1-6"))

    def test_different_hours(self) -> None:
        self.assertFalse(equivalent("0 9 * * *", "0 10 * * *"))

    def test_different_minutes(self) -> None:
        self.assertFalse(equivalent("0 9 * * *", "5 9 * * *"))

    def test_the_or_rule_makes_these_different(self) -> None:
        # "0 0 13 * 5" fires on the 13th OR on Friday,
        # "0 0 13 * *" fires only on the 13th.
        self.assertFalse(equivalent("0 0 13 * 5", "0 0 13 * *"))

    def test_different_domains(self) -> None:
        self.assertFalse(equivalent("0 0 1 * *", "0 0 1 1 *"))

    def test_a_star_and_a_full_range_are_the_same_when_the_other_field_is_free(self) -> None:
        self.assertTrue(equivalent("0 9 * * *", "0 9 1-31 1-12 *"))

    def test_quartz_and_semantics_differ_from_cron_or_semantics(self) -> None:
        cron = CronExpression.parse("0 0 13 * 5")
        quartz = CronExpression.parse("0 0 0 13 * 5 *", dialect="quartz", allow_seconds=True)
        self.assertFalse(cron.is_equivalent_to(quartz))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
