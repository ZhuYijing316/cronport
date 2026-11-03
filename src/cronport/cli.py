"""The ``cronport`` command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, tzinfo
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from . import __version__
from .dialects import (
    DIALECTS,
    SOURCE_DIALECTS,
    Conversion,
    convert,
    get_dialect,
    list_dialects,
    parse_in,
)
from .errors import CronportError
from .fields import FieldSpec
from .expr import CronExpression, resolve_timezone
from .explain import WEEKDAY_NAMES_EN, WEEKDAY_NAMES_ZH, explain
from .lint import LintContext, lint
from .notes import LEVEL_ERROR, LEVEL_INFO, LEVEL_WARNING
from .presets import categories, get_preset, list_presets
from .render import Theme

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_LINT_FAILED = 3
EXIT_DIFFERENT = 4

WEEKDAYS_EN = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
WEEKDAYS_ZH = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


class Translator:
    """Picks the right wording for the chosen language."""

    def __init__(self, lang: str = "en") -> None:
        self.lang = lang

    @property
    def both(self) -> bool:
        return self.lang == "both"

    @property
    def chinese(self) -> bool:
        return self.lang == "zh"

    def text(self, en: str, zh: str) -> str:
        if self.chinese:
            return zh
        return en

    def pair(self, en: str, zh: str) -> Tuple[str, Optional[str]]:
        """The English text and, in bilingual mode, the Chinese one."""
        if self.chinese:
            return zh, None
        if self.both:
            return en, zh
        return en, None


def _weekday(moment: datetime, chinese: bool) -> str:
    index = moment.weekday()
    return WEEKDAYS_ZH[index] if chinese else WEEKDAYS_EN[index]


def _parse_expression(args: argparse.Namespace) -> CronExpression:
    source = getattr(args, "source", "cron")
    return parse_in(source, args.expression)


def _resolve_tz(args: argparse.Namespace) -> tzinfo:
    return resolve_timezone(getattr(args, "tz", None))


def _emit_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


# ----------------------------------------------------------------------
# commands
# ----------------------------------------------------------------------


def cmd_explain(args: argparse.Namespace, theme: Theme) -> int:
    """Explain a schedule in plain language."""
    translator = Translator(args.lang)
    expression = _parse_expression(args)
    explanation = explain(expression)

    if args.json:
        payload: Dict[str, Any] = explanation.to_dict()
        payload["expression"] = expression.expression
        payload["canonical"] = expression.canonical()
        payload["notes"] = [note.to_dict() for note in expression.notes]
        _emit_json(payload)
        return EXIT_OK

    print(theme.header("cronport", expression.expression))
    print()

    english, chinese = translator.pair(explanation.summary_en, explanation.summary_zh)
    print(f"  {theme.key(english)}")
    if chinese:
        print(f"  {theme.key(chinese)}")
    if explanation.pattern_en:
        pattern, pattern_zh = translator.pair(explanation.pattern_en, explanation.pattern_zh)
        print(f"  {theme.dim(pattern)}")
        if pattern_zh:
            print(f"  {theme.dim(pattern_zh)}")
    print()

    headers = [
        translator.text("field", "字段"),
        translator.text("value", "取值"),
        translator.text("meaning", "含义"),
    ]
    rows: List[List[str]] = []
    for item in explanation.fields:
        if translator.chinese:
            rows.append([item.name, item.raw, item.meaning_zh])
        elif translator.both:
            rows.append([item.name, item.raw, item.meaning_en, item.meaning_zh])
        else:
            rows.append([item.name, item.raw, item.meaning_en])
    if translator.both and not translator.chinese:
        headers.append("含义")
    print(theme.heading(translator.text("Field breakdown", "字段拆解")))
    print(theme.table(headers, rows, indent="  "))
    print()

    if expression.notes:
        print(theme.heading(translator.text("Notes", "提示")))
        for note in expression.notes:
            text = note.localized(args.lang)
            print(f"  {theme.warn(theme.symbol('warning'))} {text}")
        print()

    if args.next:
        zone = _resolve_tz(args)
        window = expression.next_window(args.next, tz=zone)
        label = translator.text("Next runs", "接下来运行")
        print(theme.heading(f"{label} · {args.tz or _local_zone_name()}"))
        for occurrence in window.occurrences:
            stamp = occurrence.local.strftime("%Y-%m-%d %H:%M")
            print(f"  {theme.dim(stamp)}  {_weekday(occurrence.local, translator.chinese)}")
        print()
    return EXIT_OK


def cmd_next(args: argparse.Namespace, theme: Theme) -> int:
    """Show the next runs of a schedule."""
    translator = Translator(args.lang)
    expression = _parse_expression(args)
    zone = _resolve_tz(args)
    start = datetime.fromisoformat(args.since) if args.since else None
    window = expression.next_window(args.count, tz=zone, start=start)

    if args.json:
        _emit_json(
            {
                "expression": expression.expression,
                "timezone": args.tz,
                "runs": [
                    {
                        "local": occurrence.local.isoformat(),
                        "utc": occurrence.utc.isoformat(),
                        "note": occurrence.note,
                    }
                    for occurrence in window.occurrences
                ],
                "skipped": [
                    {"local": item.local.isoformat(), "reason": "nonexistent-local-time"}
                    for item in window.skipped
                ],
            }
        )
        return EXIT_OK

    print(theme.header("cronport", expression.expression))
    print()
    label = translator.text("Next runs", "接下来运行")
    print(theme.heading(f"{label} · {args.tz or _local_zone_name()}"))
    for occurrence in window.occurrences:
        stamp = occurrence.local.strftime("%Y-%m-%d %H:%M")
        weekday = _weekday(occurrence.local, translator.chinese)
        line = f"  {theme.dim(stamp)}  {weekday}"
        if occurrence.note == "ambiguous-first":
            line += theme.dim("  (first of two, DST)")
        elif occurrence.note == "ambiguous-second":
            line += theme.dim("  (second of two, DST)")
        print(line)
    if window.skipped:
        print()
        warning = translator.text(
            "skipped (the wall clock time does not exist in this timezone):",
            "已跳过（该墙钟时间在此���区不存在）：",
        )
        print(f"  {theme.warn(theme.symbol('warning'))} {warning}")
        for item in window.skipped:
            print(f"    {theme.dim(item.local.strftime('%Y-%m-%d %H:%M'))}")
    return EXIT_OK


def cmd_prev(args: argparse.Namespace, theme: Theme) -> int:
    """Show the previous runs of a schedule."""
    translator = Translator(args.lang)
    expression = _parse_expression(args)
    zone = _resolve_tz(args)
    end = datetime.fromisoformat(args.until) if args.until else None
    window = expression.previous_window(args.count, tz=zone, end=end)

    if args.json:
        _emit_json(
            {
                "expression": expression.expression,
                "timezone": args.tz,
                "runs": [
                    {
                        "local": occurrence.local.isoformat(),
                        "utc": occurrence.utc.isoformat(),
                        "note": occurrence.note,
                    }
                    for occurrence in window.occurrences
                ],
            }
        )
        return EXIT_OK

    print(theme.header("cronport", expression.expression))
    print()
    label = translator.text("Previous runs", "之前运行")
    print(theme.heading(f"{label} · {args.tz or _local_zone_name()}"))
    for occurrence in window.occurrences:
        stamp = occurrence.local.strftime("%Y-%m-%d %H:%M")
        print(f"  {theme.dim(stamp)}  {_weekday(occurrence.local, translator.chinese)}")
    return EXIT_OK


def cmd_convert(args: argparse.Namespace, theme: Theme) -> int:
    """Convert a schedule between dialects."""
    translator = Translator(args.lang)
    expression = _parse_expression(args)
    targets = [args.to] if args.to else list(DIALECTS)

    conversions: List[Conversion] = []
    for target in targets:
        conversions.append(convert(expression, target, tz=args.tz))

    if args.json:
        _emit_json(
            {
                "expression": expression.expression,
                "timezone": args.tz,
                "conversions": [item.to_dict() for item in conversions],
            }
        )
        return EXIT_OK

    print(theme.header("cronport", expression.expression))
    print()
    label = translator.text("Converted", "转换结果")
    source_label = translator.text("from", "源")
    print(theme.heading(f"{label} · {source_label} {expression.dialect}"))
    print()

    headers = [
        translator.text("target", "目标"),
        translator.text("expression", "表达式"),
        translator.text("note", "说明"),
    ]
    rows: List[List[str]] = []
    for item in conversions:
        note = ""
        if item.notes:
            worst = min(
                item.notes,
                key=lambda note: {"error": 0, "warning": 1, "info": 2}[note.level],
            )
            marker = {
                LEVEL_ERROR: theme.error(theme.symbol("error")),
                LEVEL_WARNING: theme.warn(theme.symbol("warning")),
                LEVEL_INFO: theme.dim(theme.symbol("info")),
            }[worst.level]
            count = len(item.notes)
            suffix = f" x{count}" if count > 1 else ""
            note = f"{marker} {worst.level}{suffix}"
        expression = item.expression
        if "\n" in expression:
            first, _, rest = expression.partition("\n")
            lines = len(rest.split("\n")) + 1
            expression = f"{first}  ⏎ +{lines - 1} more line"
        rows.append([item.target, expression, note])
    print(theme.table(headers, rows, indent="  "))
    print()

    for item in conversions:
        if not item.notes and "\n" not in item.expression:
            continue
        print(theme.heading(item.target))
        if "\n" in item.expression:
            for line in item.expression.split("\n"):
                print(f"  {theme.value(line)}")
            print()
        for note in item.notes:
            painter = {
                LEVEL_ERROR: theme.error,
                LEVEL_WARNING: theme.warn,
                LEVEL_INFO: theme.dim,
            }[note.level]
            marker = {
                LEVEL_ERROR: theme.symbol("error"),
                LEVEL_WARNING: theme.symbol("warning"),
                LEVEL_INFO: theme.symbol("info"),
            }[note.level]
            print(f"  {painter(marker)} {note.localized(args.lang)}")
        print()

    return EXIT_OK


def cmd_lint(args: argparse.Namespace, theme: Theme) -> int:
    """Check a schedule for the ways it can silently go wrong."""
    translator = Translator(args.lang)
    expression = _parse_expression(args)
    target = args.target or "cron"
    dialect = get_dialect(target)
    context = LintContext(
        target=target,
        tz=args.tz,
        supports_seconds=dialect.supports_seconds,
        supports_timezone=dialect.supports_timezone,
        supports_macros=dialect.supports_macros,
    )
    issues = lint(expression, context)

    has_errors = any(issue.severity == LEVEL_ERROR for issue in issues)
    has_warnings = any(issue.severity == LEVEL_WARNING for issue in issues)

    if args.json:
        _emit_json(
            {
                "expression": expression.expression,
                "target": target,
                "issues": [issue.to_dict() for issue in issues],
                "ok": not (has_errors or has_warnings),
                "errors": sum(1 for issue in issues if issue.severity == LEVEL_ERROR),
                "warnings": sum(1 for issue in issues if issue.severity == LEVEL_WARNING),
            }
        )
        return EXIT_LINT_FAILED if _lint_should_fail(has_errors, has_warnings, args) else EXIT_OK

    print(theme.header("cronport", expression.expression))
    print()
    label = translator.text("Target", "目标")
    print(f"  {theme.dim(label)}: {theme.value(target)}")
    print()

    if not issues:
        print(f"  {theme.ok(theme.symbol('ok'))} {translator.text('No problems found.', '没有发现问题。')}")
        return EXIT_OK

    count = len(issues)
    summary = translator.text(
        f"{count} issue(s) found",
        f"发现 {count} 个问题",
    )
    print(theme.heading(summary))
    print()

    for issue in issues:
        painter = {
            LEVEL_ERROR: theme.error,
            LEVEL_WARNING: theme.warn,
            LEVEL_INFO: theme.dim,
        }[issue.severity]
        marker = {
            LEVEL_ERROR: theme.symbol("error"),
            LEVEL_WARNING: theme.symbol("warning"),
            LEVEL_INFO: theme.symbol("info"),
        }[issue.severity]
        print(f"  {painter(marker)} {theme.bold(issue.rule_id)}")
        print(f"      {issue.message(args.lang)}")
        hint = issue.hint(args.lang)
        if hint:
            print(f"      {theme.dim('hint: ' + hint)}")
        print()

    if _lint_should_fail(has_errors, has_warnings, args):
        return EXIT_LINT_FAILED
    return EXIT_OK


def _lint_should_fail(has_errors: bool, has_warnings: bool, args: argparse.Namespace) -> bool:
    """Whether the linter should report a non-zero exit code."""
    if has_errors:
        return True
    return bool(has_warnings and getattr(args, "strict", False))


def cmd_diff(args: argparse.Namespace, theme: Theme) -> int:
    """Compare two schedules and say whether they really are the same."""
    translator = Translator(args.lang)
    left = parse_in(args.source, args.left)
    right = parse_in(args.source, args.right)
    equivalent = left.is_equivalent_to(right)

    if args.json:
        _emit_json(
            {
                "left": left.expression,
                "right": right.expression,
                "equivalent": equivalent,
                "differences": _field_differences(left, right),
            }
        )
        return EXIT_OK if equivalent else EXIT_DIFFERENT

    print(theme.header("cronport", f"{left.expression}  vs  {right.expression}"))
    print()

    if equivalent:
        message = translator.text(
            "both schedules fire at exactly the same times",
            "两个调度的触发时刻完全相同",
        )
        print(f"  {theme.ok(theme.symbol('ok'))} {theme.ok(message)}")
        print()
        return EXIT_OK

    message = translator.text(
        "the schedules fire at different times",
        "两个调度的触发时刻不同",
    )
    print(f"  {theme.error(theme.symbol('error'))} {theme.error(message)}")
    print()

    rows: List[List[str]] = []
    for name, left_spec, right_spec in _field_pairs(left, right):
        if left_spec.values == right_spec.values:
            continue
        rows.append([name, left_spec.raw, right_spec.raw])
    if rows:
        headers = [
            translator.text("field", "字段"),
            translator.text("left", "左侧"),
            translator.text("right", "右侧"),
        ]
        print(theme.table(headers, rows))
        print()
    return EXIT_DIFFERENT


def cmd_presets(args: argparse.Namespace, theme: Theme) -> int:
    """Show the built-in schedules."""
    translator = Translator(args.lang)

    if args.name:
        preset = get_preset(args.name)
        if preset is None:
            raise CronportError(
                f"unknown preset {args.name!r}",
                f"未知的预设 {args.name!r}",
                hint="run 'cronport presets' to list them",
                hint_zh="运行 'cronport presets' 查看全部预设",
            )
        expression = CronExpression.parse(preset.expression)
        if args.json:
            payload = preset.to_dict()
            payload["summary"] = explain(expression).to_dict()["summary"]
            _emit_json(payload)
            return EXIT_OK
        print(theme.header("cronport", preset.expression))
        print()
        title, title_zh = translator.pair(preset.title_en, preset.title_zh)
        print(f"  {theme.key(title)}")
        if title_zh:
            print(f"  {theme.key(title_zh)}")
        print(f"  {theme.dim(preset.key)}")
        print()
        print(theme.table([translator.text("target", "目标"), translator.text("expression", "表达式")],
                          [[item.target, item.expression] for item in
                           [convert(expression, name) for name in DIALECTS]]))
        return EXIT_OK

    presets = list_presets(args.category)
    if args.json:
        _emit_json({"presets": [preset.to_dict() for preset in presets]})
        return EXIT_OK

    print(theme.header("cronport"))
    print()
    headers = [
        translator.text("key", "标识"),
        translator.text("schedule", "调度"),
        translator.text("description", "说明"),
        translator.text("category", "分类"),
    ]
    rows: List[List[str]] = []
    for preset in presets:
        title, title_zh = translator.pair(preset.title_en, preset.title_zh)
        description = title_zh if title_zh else title
        rows.append([preset.key, preset.expression, description, preset.category])
    print(theme.table(headers, rows))
    print()
    print(theme.dim(translator.text(
        "use 'cronport presets <key>' to see one in every dialect",
        "使用 'cronport presets <key>' 查看某个预设在各方言下的样子",
    )))
    return EXIT_OK


def cmd_dialects(args: argparse.Namespace, theme: Theme) -> int:
    """List the supported dialects."""
    translator = Translator(args.lang)
    if args.json:
        _emit_json(
            {
                "dialects": [
                    {
                        "name": dialect.name,
                        "label": dialect.label,
                        "aliases": list(dialect.aliases),
                        "supports_seconds": dialect.supports_seconds,
                        "supports_timezone": dialect.supports_timezone,
                        "can_be_source": dialect.name in SOURCE_DIALECTS,
                    }
                    for dialect in list_dialects()
                ]
            }
        )
        return EXIT_OK

    print(theme.header("cronport"))
    print()
    headers = [
        translator.text("name", "名称"),
        translator.text("what it is", "说明"),
        translator.text("aliases", "别名"),
    ]
    rows: List[List[str]] = []
    for dialect in list_dialects():
        rows.append([dialect.name, dialect.label, ", ".join(dialect.aliases) or "-"])
    print(theme.table(headers, rows))
    return EXIT_OK


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _field_pairs(
    left: CronExpression, right: CronExpression
) -> Iterator[Tuple[str, FieldSpec, FieldSpec]]:
    left_fields = dict(left.fields)
    right_fields = dict(right.fields)
    for name, left_spec in left_fields.items():
        right_spec = right_fields.get(name)
        if right_spec is None:
            continue
        yield name, left_spec, right_spec


def _field_differences(left: CronExpression, right: CronExpression) -> List[Dict[str, Any]]:
    differences: List[Dict[str, Any]] = []
    for name, left_spec, right_spec in _field_pairs(left, right):
        if left_spec.values != right_spec.values:
            differences.append(
                {
                    "field": name,
                    "left": left_spec.raw,
                    "right": right_spec.raw,
                }
            )
    return differences


def _dialect_argument(name: str, sources_only: bool = False) -> Callable[[str], str]:
    """An argparse type that accepts a dialect name or one of its aliases."""
    from .dialects import SOURCE_DIALECTS, canonical_name
    from .errors import UnknownDialectError

    def parse(value: str) -> str:
        try:
            canonical = canonical_name(value)
        except UnknownDialectError:
            known = ", ".join(sorted(SOURCE_DIALECTS if sources_only else DIALECTS))
            raise argparse.ArgumentTypeError(
                f"unknown dialect {value!r}; known dialects: {known}"
            ) from None
        if sources_only and canonical not in SOURCE_DIALECTS:
            known = ", ".join(sorted(SOURCE_DIALECTS))
            raise argparse.ArgumentTypeError(
                f"{canonical!r} cannot be read as a source; "
                f"cronport can read: {known}"
            )
        return canonical

    parse.__name__ = name
    return parse


def _local_zone_name() -> str:
    name = datetime.now().astimezone().tzname()
    return name or "local"


# ----------------------------------------------------------------------
# parser
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="cronport",
        description=(
            "One schedule, every runtime: explain, convert and lint cron "
            "expressions across cron, systemd, Kubernetes, GitHub Actions, "
            "AWS EventBridge and Quartz."
        ),
        epilog="Run 'cronport <command> --help' for details on a command.",
    )
    parser.add_argument("--version", action="version", version=f"cronport {__version__}")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine readable JSON instead of a table",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="never colour the output",
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="use ASCII characters instead of box drawing ones",
    )
    parser.add_argument(
        "--lang",
        choices=("en", "zh", "both"),
        default="en",
        help="output language (default: en)",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    def add_source(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--from",
            dest="source",
            default="cron",
            type=_dialect_argument("source_dialect", sources_only=True),
            metavar="{" + ",".join(sorted(SOURCE_DIALECTS)) + "}",
            help="the dialect the expression is written in (default: cron)",
        )

    explain_parser = subparsers.add_parser(
        "explain",
        help="describe a schedule in plain language",
        description="Describe a schedule in plain language, field by field.",
    )
    explain_parser.add_argument("expression", help="the schedule to explain")
    add_source(explain_parser)
    explain_parser.add_argument(
        "-n",
        "--next",
        type=int,
        default=0,
        metavar="N",
        help="also show the next N run times",
    )
    explain_parser.add_argument("--tz", help="timezone for the run times, e.g. Asia/Shanghai")
    explain_parser.set_defaults(func=cmd_explain)

    next_parser = subparsers.add_parser(
        "next",
        help="show the next run times",
        description="Show when a schedule fires next.",
    )
    next_parser.add_argument("expression", help="the schedule")
    add_source(next_parser)
    next_parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=5,
        metavar="N",
        help="how many run times to show (default: 5)",
    )
    next_parser.add_argument("--tz", help="timezone, e.g. Asia/Shanghai or UTC")
    next_parser.add_argument(
        "--since",
        dest="since",
        help="start looking from this ISO timestamp",
    )
    next_parser.set_defaults(func=cmd_next)

    prev_parser = subparsers.add_parser(
        "prev",
        help="show the previous run times",
        description="Show when a schedule fired last.",
    )
    prev_parser.add_argument("expression", help="the schedule")
    add_source(prev_parser)
    prev_parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=5,
        metavar="N",
        help="how many run times to show (default: 5)",
    )
    prev_parser.add_argument("--tz", help="timezone, e.g. Asia/Shanghai or UTC")
    prev_parser.add_argument(
        "--until",
        dest="until",
        help="stop looking before this ISO timestamp",
    )
    prev_parser.set_defaults(func=cmd_prev)

    convert_parser = subparsers.add_parser(
        "convert",
        help="convert a schedule to another dialect",
        description="Convert a schedule into another scheduler's syntax.",
    )
    convert_parser.add_argument("expression", help="the schedule")
    add_source(convert_parser)
    convert_parser.add_argument(
        "--to",
        type=_dialect_argument("target_dialect"),
        metavar="{" + ",".join(sorted(DIALECTS)) + "}",
        help="target dialect (default: every dialect)",
    )
    convert_parser.add_argument("--tz", help="timezone to apply to the target")
    convert_parser.set_defaults(func=cmd_convert)

    lint_parser = subparsers.add_parser(
        "lint",
        help="check a schedule for hidden surprises",
        description=(
            "Check a schedule for the ways it can silently mean something "
            "different from what you meant."
        ),
    )
    lint_parser.add_argument("expression", help="the schedule")
    add_source(lint_parser)
    lint_parser.add_argument(
        "--target",
        type=_dialect_argument("lint_target"),
        metavar="{" + ",".join(sorted(DIALECTS)) + "}",
        help="the scheduler it will run on (default: cron)",
    )
    lint_parser.add_argument("--tz", help="timezone the schedule will run in")
    lint_parser.add_argument(
        "--strict",
        action="store_true",
        help="also fail on warnings, not only on errors",
    )
    lint_parser.set_defaults(func=cmd_lint)

    diff_parser = subparsers.add_parser(
        "diff",
        help="check whether two schedules are really the same",
        description=(
            "Compare two schedules and tell you whether they fire at exactly "
            "the same times."
        ),
    )
    diff_parser.add_argument("left", help="the first schedule")
    diff_parser.add_argument("right", help="the second schedule")
    add_source(diff_parser)
    diff_parser.set_defaults(func=cmd_diff)

    presets_parser = subparsers.add_parser(
        "presets",
        help="show ready made schedules",
        description="A library of schedules people actually use.",
    )
    presets_parser.add_argument("name", nargs="?", help="a preset key to show in detail")
    presets_parser.add_argument("--category", help="only show one category")
    presets_parser.set_defaults(func=cmd_presets)

    dialects_parser = subparsers.add_parser(
        "dialects",
        help="list the supported dialects",
        description="List every scheduler dialect cronport can speak.",
    )
    dialects_parser.set_defaults(func=cmd_dialects)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """The entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_USAGE

    theme = Theme(color=False if args.no_color else None, ascii_only=args.ascii or None)
    try:
        return int(args.func(args, theme))
    except CronportError as error:
        _print_error(error, args.lang, theme)
        return EXIT_ERROR
    except BrokenPipeError:  # pragma: no cover - piping into head
        return EXIT_OK
    except KeyboardInterrupt:  # pragma: no cover
        return 130


def _print_error(error: CronportError, lang: str, theme: Theme) -> None:
    print(f"{theme.error(theme.symbol('error'))} {error.localized(lang)}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
