"""Tests for the command line interface."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from cronport.cli import EXIT_DIFFERENT, EXIT_ERROR, EXIT_LINT_FAILED, EXIT_OK, main


def run(*argv: str) -> tuple:
    """Run the CLI and capture what it printed."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class ExplainTests(unittest.TestCase):
    def test_explain_prints_a_summary(self) -> None:
        code, out, _ = run("explain", "0 9 * * 1-5")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Monday to Friday", out)
        self.assertIn("day-of-week", out)

    def test_explain_in_chinese(self) -> None:
        code, out, _ = run("--lang", "zh", "explain", "0 9 * * 1-5")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("周一至周五", out)

    def test_explain_bilingual(self) -> None:
        code, out, _ = run("--lang", "both", "explain", "0 9 * * 1-5")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Monday to Friday", out)
        self.assertIn("周一至周五", out)

    def test_explain_with_next_runs(self) -> None:
        code, out, _ = run("explain", "0 9 * * 1-5", "-n", "3", "--tz", "UTC")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("2026-11-04", out)

    def test_json_output_is_valid_json(self) -> None:
        code, out, _ = run("--json", "explain", "0 9 * * 1-5")
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertIn("summary", payload)
        self.assertEqual(payload["canonical"], "0 9 * * 1-5")

    def test_a_bad_expression_fails_cleanly(self) -> None:
        code, _, err = run("explain", "0 9 * *")
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("expected 5 fields", err)


class NextTests(unittest.TestCase):
    def test_next_prints_run_times(self) -> None:
        code, out, _ = run("next", "0 9 * * 1-5", "-n", "3", "--tz", "UTC")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("2026-11-04 09:00", out)

    def test_next_json(self) -> None:
        code, out, _ = run("--json", "next", "0 9 * * 1-5", "-n", "2", "--tz", "UTC")
        payload = json.loads(out)
        self.assertEqual(len(payload["runs"]), 2)
        self.assertEqual(payload["runs"][0]["local"][:10], "2026-11-04")

    def test_prev(self) -> None:
        code, out, _ = run("prev", "0 9 * * 1-5", "-n", "2", "--tz", "UTC")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("2026-11-03", out)


class ConvertTests(unittest.TestCase):
    def test_convert_to_one_target(self) -> None:
        code, out, _ = run("convert", "0 9 * * 1-5", "--to", "systemd")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Mon..Fri *-*-* 09:00:00", out)

    def test_convert_to_every_target(self) -> None:
        code, out, _ = run("convert", "0 9 * * 1-5")
        self.assertEqual(code, EXIT_OK)
        for target in [
            "cron",
            "systemd",
            "kubernetes",
            "github-actions",
            "aws-eventbridge",
            "quartz",
            "gcp-scheduler",
        ]:
            self.assertIn(target, out)

    def test_convert_json(self) -> None:
        code, out, _ = run("--json", "convert", "0 9 * * 1-5", "--to", "systemd")
        payload = json.loads(out)
        self.assertEqual(payload["conversions"][0]["expression"], "Mon..Fri *-*-* 09:00:00")


class LintTests(unittest.TestCase):
    def test_a_clean_schedule_exits_zero(self) -> None:
        code, out, _ = run("lint", "30 2 * * 1-5", "--tz", "UTC")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("No problems found", out)

    def test_an_error_exits_with_three(self) -> None:
        code, out, _ = run("lint", "0 0 30 2 *", "--tz", "UTC")
        self.assertEqual(code, EXIT_LINT_FAILED)
        self.assertIn("never-fires", out)

    def test_lint_json(self) -> None:
        code, out, _ = run("--json", "lint", "0 0 13 * 5", "--tz", "UTC")
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        self.assertTrue(any(issue["rule"] == "dom-dow-or" for issue in payload["issues"]))


class DiffTests(unittest.TestCase):
    def test_equivalent_schedules_exit_zero(self) -> None:
        code, out, _ = run("diff", "0 9 * * 1-5", "0 9 * * 1,2,3,4,5")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("same times", out)

    def test_different_schedules_exit_with_four(self) -> None:
        code, out, _ = run("diff", "0 9 * * 1-5", "0 10 * * 1-5")
        self.assertEqual(code, EXIT_DIFFERENT)
        self.assertIn("different times", out)


class PresetTests(unittest.TestCase):
    def test_presets_are_listed(self) -> None:
        code, out, _ = run("presets")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("every-15-minutes", out)

    def test_one_preset_is_shown_in_detail(self) -> None:
        code, out, _ = run("presets", "daily-9am")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("0 9 * * *", out)

    def test_an_unknown_preset_fails(self) -> None:
        code, _, err = run("presets", "nope")
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("unknown preset", err)


class MiscTests(unittest.TestCase):
    def test_dialects_are_listed(self) -> None:
        code, out, _ = run("dialects")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("github-actions", out)

    def test_no_command_prints_help(self) -> None:
        code, out, _ = run()
        self.assertEqual(code, 2)
        self.assertIn("usage", out.lower())

    def test_ascii_mode_avoids_box_drawing(self) -> None:
        code, out, _ = run("--ascii", "explain", "0 9 * * 1-5")
        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("─", out)
        self.assertIn("+", out)

    def test_no_color_mode_has_no_escape_codes(self) -> None:
        code, out, _ = run("--no-color", "explain", "0 9 * * 1-5")
        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("\033[", out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
