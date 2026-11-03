"""Tests for the scheduler: next runs, previous runs and daylight saving."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from cronport.errors import NoOccurrenceError
from cronport.expr import CronExpression, resolve_timezone

SHANGHAI = resolve_timezone("Asia/Shanghai")
NEW_YORK = resolve_timezone("America/New_York")


class NextRunTests(unittest.TestCase):
    def test_weekday_schedule(self) -> None:
        expression = CronExpression.parse("0 9 * * 1-5")
        runs = expression.next_runs(5, tz=SHANGHAI)
        self.assertEqual(
            [moment.strftime("%Y-%m-%d %H:%M") for moment in runs],
            [
                "2026-11-04 09:00",
                "2026-11-05 09:00",
                "2026-11-06 09:00",
                "2026-11-09 09:00",
                "2026-11-10 09:00",
            ],
        )

    def test_every_15_minutes(self) -> None:
        expression = CronExpression.parse("*/15 * * * *")
        runs = expression.next_runs(4, tz=SHANGHAI, start=datetime(2026, 11, 4, 9, 7))
        self.assertEqual(
            [moment.strftime("%H:%M") for moment in runs],
            ["09:15", "09:30", "09:45", "10:00"],
        )

    def test_month_end(self) -> None:
        expression = CronExpression.parse("0 0 31 * *")
        runs = expression.next_runs(3, tz=SHANGHAI, start=datetime(2026, 1, 1))
        self.assertEqual(
            [moment.strftime("%Y-%m-%d") for moment in runs],
            ["2026-01-31", "2026-03-31", "2026-05-31"],
        )

    def test_leap_day(self) -> None:
        expression = CronExpression.parse("0 0 29 2 *")
        runs = expression.next_runs(2, tz=SHANGHAI, start=datetime(2026, 3, 1))
        self.assertEqual(
            [moment.strftime("%Y-%m-%d") for moment in runs],
            ["2028-02-29", "2032-02-29"],
        )

    def test_a_schedule_that_never_fires(self) -> None:
        expression = CronExpression.parse("0 0 30 2 *")
        with self.assertRaises(NoOccurrenceError):
            expression.next_runs(1, tz=SHANGHAI)

    def test_a_run_at_the_starting_point_is_included(self) -> None:
        expression = CronExpression.parse("0 * * * *")
        runs = expression.next_runs(1, tz=SHANGHAI, start=datetime(2026, 11, 4, 9, 0))
        self.assertEqual(runs[0].strftime("%H:%M"), "09:00")

    def test_starting_point_in_the_middle_of_a_minute(self) -> None:
        expression = CronExpression.parse("0 * * * *")
        runs = expression.next_runs(1, tz=SHANGHAI, start=datetime(2026, 11, 4, 9, 30))
        self.assertEqual(runs[0].strftime("%H:%M"), "10:00")


class DaylightSavingTests(unittest.TestCase):
    def test_a_wall_clock_time_that_does_not_exist_is_skipped(self) -> None:
        # On 8 March 2026 the clock in New York jumps from 02:00 to 03:00,
        # so 02:30 never happens on that day.
        expression = CronExpression.parse("30 2 * * *")
        window = expression.next_window(
            3, tz=NEW_YORK, start=datetime(2026, 3, 6, 12, 0)
        )
        stamps = [moment.local.strftime("%Y-%m-%d %H:%M") for moment in window.occurrences]
        self.assertEqual(stamps, ["2026-03-07 02:30", "2026-03-09 02:30", "2026-03-10 02:30"])
        self.assertEqual(len(window.skipped), 1)
        self.assertEqual(window.skipped[0].local.strftime("%Y-%m-%d %H:%M"), "2026-03-08 02:30")

    def test_a_wall_clock_time_that_happens_twice_fires_twice(self) -> None:
        # On 1 November 2026 the clock in New York goes back from 02:00 to
        # 01:00, so 01:30 happens twice.
        expression = CronExpression.parse("30 1 * * *")
        window = expression.next_window(
            3, tz=NEW_YORK, start=datetime(2026, 10, 31, 12, 0)
        )
        self.assertEqual(
            [moment.local.strftime("%Y-%m-%d %H:%M %Z") for moment in window.occurrences],
            ["2026-11-01 01:30 EDT", "2026-11-01 01:30 EST", "2026-11-02 01:30 EST"],
        )
        self.assertEqual(window.occurrences[0].note, "ambiguous-first")
        self.assertEqual(window.occurrences[1].note, "ambiguous-second")

    def test_utc_is_never_affected(self) -> None:
        expression = CronExpression.parse("30 2 * * *")
        window = expression.next_window(
            2, tz=timezone.utc, start=datetime(2026, 3, 7, 12, 0)
        )
        self.assertEqual(window.skipped, [])
        self.assertEqual(
            [moment.local.strftime("%Y-%m-%d %H:%M") for moment in window.occurrences],
            ["2026-03-08 02:30", "2026-03-09 02:30"],
        )


class PreviousRunTests(unittest.TestCase):
    def test_previous_runs(self) -> None:
        expression = CronExpression.parse("0 9 * * 1-5")
        runs = expression.previous_runs(
            3, tz=SHANGHAI, end=datetime(2026, 11, 4, 12, 0)
        )
        self.assertEqual(
            [moment.strftime("%Y-%m-%d %H:%M") for moment in runs],
            ["2026-11-04 09:00", "2026-11-03 09:00", "2026-11-02 09:00"],
        )

    def test_previous_runs_are_in_descending_order(self) -> None:
        expression = CronExpression.parse("*/20 * * * *")
        runs = expression.previous_runs(5, tz=SHANGHAI, end=datetime(2026, 11, 4, 12, 0))
        self.assertEqual(runs, sorted(runs, reverse=True))


class TimezoneTests(unittest.TestCase):
    def test_utc(self) -> None:
        self.assertEqual(resolve_timezone("UTC"), timezone.utc)

    def test_fixed_offset(self) -> None:
        zone = resolve_timezone("+08:00")
        moment = datetime(2026, 11, 4, 9, 0, tzinfo=zone)
        self.assertEqual(moment.utcoffset(), timedelta(hours=8))

    def test_unknown_zone(self) -> None:
        from cronport.errors import CronportError

        with self.assertRaises(CronportError):
            resolve_timezone("Mars/Olympus_Mons")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
