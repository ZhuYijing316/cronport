"""The linter: everything that can silently bite you.

Each rule is a small function plus some metadata, and the registry is a plain
list, so adding a rule (or writing your own) is a one-liner.

The rules are not style opinions.  Every one of them describes a way a
schedule can end up meaning something different from what its author
intended.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from .expr import CronExpression, DaySemantics, days_in_month
from .notes import LEVEL_ERROR, LEVEL_INFO, LEVEL_WARNING

SEVERITY_ORDER = {LEVEL_ERROR: 0, LEVEL_WARNING: 1, LEVEL_INFO: 2}


@dataclass(frozen=True)
class Issue:
    """One thing worth telling the user about."""

    rule_id: str
    severity: str
    message_en: str
    message_zh: str
    hint_en: str = ""
    hint_zh: str = ""

    def message(self, lang: str = "en") -> str:
        return self.message_zh if lang.startswith("zh") and self.message_zh else self.message_en

    def hint(self, lang: str = "en") -> str:
        return self.hint_zh if lang.startswith("zh") and self.hint_zh else self.hint_en

    def to_dict(self) -> dict:
        return {
            "rule": self.rule_id,
            "severity": self.severity,
            "message": {"en": self.message_en, "zh": self.message_zh},
            "hint": {"en": self.hint_en, "zh": self.hint_zh},
        }


@dataclass
class LintContext:
    """What the linter needs to know about the target."""

    target: str = "cron"
    tz: Optional[str] = None
    #: Extra dialects that are known to the linter.
    supports_seconds: bool = False
    supports_timezone: bool = True
    supports_macros: bool = True


@dataclass(frozen=True)
class Rule:
    """A lint rule."""

    id: str
    severity: str
    title_en: str
    title_zh: str
    check: Callable[[CronExpression, LintContext], Optional[Issue]]

    def run(self, expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
        """Run the rule, turning a crash into a visible issue.

        A broken rule must not take the whole linter down, but it must not
        disappear silently either -- that would hide the very bug it is.
        """
        try:
            return self.check(expr, ctx)
        except Exception as error:  # pragma: no cover - defensive
            return Issue(
                rule_id=f"{self.id}-failed",
                severity=LEVEL_ERROR,
                message_en=f"the rule {self.id!r} crashed and was skipped: {error}",
                message_zh=f"规则 {self.id!r} 抛出异常并被跳过：{error}",
            )


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _steps(raw: str) -> List[Tuple[Optional[int], Optional[int], int]]:
    """Every stepped term in a field, as ``(first, last, step)``.

    ``first`` and ``last`` are ``None`` for a term that starts at the bottom
    of the field's range.
    """
    found: List[Tuple[Optional[int], Optional[int], int]] = []
    for term in raw.split(","):
        if "/" not in term:
            continue
        base, _, step_text = term.partition("/")
        if not step_text.isdigit():
            continue
        step = int(step_text)
        if step <= 0:
            continue
        if base == "*":
            found.append((None, None, step))
        elif "-" in base:
            start_text, _, end_text = base.partition("-")
            if start_text.isdigit() and end_text.isdigit():
                found.append((int(start_text), int(end_text), step))
        elif base.isdigit():
            found.append((int(base), int(base), step))
    return found


def _drift_message(
    field_name: str,
    low: int,
    high: int,
    step: int,
    first: Optional[int],
    last: Optional[int],
) -> Tuple[str, str]:
    """Describe the uneven interval a step produces at the range boundary."""
    size = high - low + 1
    remainder = size % step
    start = low if first is None else first
    end = high if last is None else last
    short_gap = (high + 1 - end) if end < high else step
    short_gap = min(short_gap, step)
    en = (
        f"the step {step} does not divide the {size} {field_name} values evenly, "
        f"so the interval is not uniform: the last firing of a {field_name} is only "
        f"{short_gap} minute(s) before the cycle starts again"
    )
    if field_name != "minute":
        en = en.replace("minute(s)", "unit(s)")
    zh = (
        f"步长 {step} 无法整除 {field_name} 的 {size} 个取值，间隔并不均匀："
        f"该周期最后一次触发距下一周期开始只有 {short_gap} 分钟"
    )
    if field_name != "minute":
        zh = zh.replace("只有 {short_gap} 分钟", f"只有 {short_gap} 个单位")
    return en, zh


# ----------------------------------------------------------------------
# rules
# ----------------------------------------------------------------------


def _rule_never_fires(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """The schedule can never match any real date."""
    if not expr._dom_constrained:
        return None
    months = expr.month.sorted_values()
    days = expr.dom.sorted_values()
    if not months or not days:
        return None
    possible = False
    for month in months:
        # 2024 is a leap year, so February can reach 29 days.
        limit = days_in_month(2024, month)
        if any(day <= limit for day in days):
            possible = True
            break
    if possible:
        return None
    return Issue(
        rule_id="never-fires",
        severity=LEVEL_ERROR,
        message_en=(
            "this schedule can never fire: the day-of-month values do not exist in "
            "the selected months"
        ),
        message_zh="该调度永远不会触发：所选的「日」在所选的月份里根本不存在",
        hint_en="check for a date such as the 30th of February",
        hint_zh="检查一下是不是写了「2 月 30 日」这类不存在的日期",
    )


def _rule_dom_dow_or(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """Both day fields restricted means OR, not AND."""
    if expr.day_semantics is not DaySemantics.OR:
        return None
    if not (expr._dom_constrained and expr._dow_constrained):
        return None
    return Issue(
        rule_id="dom-dow-or",
        severity=LEVEL_WARNING,
        message_en=(
            "day-of-month and day-of-week are both restricted, so the schedule fires "
            "when EITHER of them matches (OR), not when both match (AND)"
        ),
        message_zh=(
            "「日」和「星期」同时被限定，触发条件是满足任意一个（OR），而不是同时满足（AND）"
        ),
        hint_en=(
            "if you really mean 'both', cron cannot express it -- use Quartz, or split "
            "the schedule into two rules"
        ),
        hint_zh=(
            "如果确实需要「同时满足」，cron 无法表达——请改用 Quartz，或拆成两条规则"
        ),
    )


def _rule_step_drift(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """A step that does not divide the field evenly makes the interval uneven."""
    fields = (
        ("minute", expr.minute, 0, 59),
        ("hour", expr.hour, 0, 23),
        ("day-of-month", expr.dom, 1, 31),
        ("month", expr.month, 1, 12),
        ("day-of-week", expr.dow, 0, 6),
    )
    for name, spec, low, high in fields:
        size = high - low + 1
        for first, last, step in _steps(spec.raw):
            if size % step == 0:
                continue
            en, zh = _drift_message(name, low, high, step, first, last)
            return Issue(
                rule_id="step-not-even",
                severity=LEVEL_WARNING,
                message_en=en,
                message_zh=zh,
                hint_en=(
                    f"use a step that divides {size} evenly, such as "
                    f"{_even_steps(size)[0]}"
                ),
                hint_zh=f"请使用能整除 {size} 的步长，例如 {_even_steps(size)[0]}",
            )
    return None


def _even_steps(size: int) -> List[int]:
    """Steps that divide ``size`` evenly and are actually useful."""
    candidates = [step for step in range(2, min(size, 60) + 1) if size % step == 0]
    return candidates[:5] or [1]


def _rule_sub_five_minutes(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """GitHub Actions only guarantees a five minute minimum interval."""
    if ctx.target != "github-actions":
        return None
    minutes = expr.minute.sorted_values()
    hours = expr.hour.sorted_values()
    if len(minutes) > 1:
        gap = min(minutes[index + 1] - minutes[index] for index in range(len(minutes) - 1))
    elif len(hours) > 1:
        gap = (60 - minutes[-1]) + minutes[0]
    else:
        return None
    if gap >= 5:
        return None
    return Issue(
        rule_id="sub-five-minutes",
        severity=LEVEL_WARNING,
        message_en=(
            f"this schedule fires roughly every {gap} minute(s), but GitHub Actions "
            "only guarantees that scheduled workflows run at least every 5 minutes"
        ),
        message_zh=(
            f"该调度约每 {gap} 分钟触发一次，但 GitHub Actions 只保证调度间隔不短于 5 分钟"
        ),
        hint_en="a five minute or longer interval is much more reliable",
        hint_zh="间隔不低于 5 分钟会可靠得多",
    )


def _rule_utc_only(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """Some targets have no timezone at all."""
    if ctx.target == "github-actions":
        return Issue(
            rule_id="utc-only",
            severity=LEVEL_WARNING,
            message_en=(
                "GitHub Actions evaluates schedules in UTC and offers no timezone "
                "setting, so this schedule does not run at your local time"
            ),
            message_zh=(
                "GitHub Actions 的调度固定按 UTC 计算且没有时区设置，"
                "因此它不会在你所在的本地时间触发"
            ),
            hint_en="convert the time yourself: local time minus your UTC offset",
            hint_zh="请自行换算时间：本地时间减去你的 UTC 偏移",
        )
    if ctx.target == "aws-eventbridge":
        return Issue(
            rule_id="utc-only",
            severity=LEVEL_INFO,
            message_en=(
                "EventBridge rules run in UTC; EventBridge Scheduler can pin a "
                "timezone with scheduleExpressionTimezone"
            ),
            message_zh=(
                "EventBridge 规则按 UTC 运行；EventBridge Scheduler 可以用 "
                "scheduleExpressionTimezone 字段指定时区"
            ),
        )
    return None


def _rule_seconds_unsupported(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """The target cannot express seconds."""
    if not expr.has_seconds or ctx.supports_seconds:
        return None
    return Issue(
        rule_id="seconds-unsupported",
        severity=LEVEL_WARNING,
        message_en=f"{ctx.target} has no seconds field; the seconds part was dropped",
        message_zh=f"{ctx.target} 没有秒字段，秒部分已被丢弃",
    )


def _rule_macro_not_portable(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """``@daily`` and friends only exist in some places."""
    if not expr.expression.strip().startswith("@"):
        return None
    if ctx.supports_macros:
        return None
    return Issue(
        rule_id="macro-not-portable",
        severity=LEVEL_WARNING,
        message_en=(
            f"{ctx.target} does not understand the '@macro' shorthand "
            f"({expr.expression.strip()})"
        ),
        message_zh=f"{ctx.target} 不支持 '@宏' 简写（{expr.expression.strip()}）",
        hint_en="write the fields out in full instead",
        hint_zh="请把各个字段完整写出来",
    )


def _rule_day_31(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """The 29th to 31st do not exist in every month."""
    if not expr._dom_constrained:
        return None
    days = expr.dom.sorted_values()
    tricky = [day for day in days if day >= 29]
    if not tricky:
        return None
    listed = ", ".join(str(day) for day in tricky)
    return Issue(
        rule_id="short-month",
        severity=LEVEL_INFO,
        message_en=(
            f"day {listed} does not exist in every month, so the schedule skips "
            "those months entirely"
        ),
        message_zh=f"「{listed} 号」并不是每个月都有，该调度会直接跳过没有这一天的月份",
        hint_en="add an explicit month list if you need a predictable day of month",
        hint_zh="如果需要确定的结果，请显式列出月份",
    )


def _rule_leap_day(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """February 29th only happens once every four years."""
    if expr.dom.sorted_values() != [29] or expr.month.sorted_values() != [2]:
        return None
    return Issue(
        rule_id="leap-day",
        severity=LEVEL_INFO,
        message_en="February 29th only exists in leap years, so this schedule fires once every four years",
        message_zh="2 月 29 日只在闰年存在，该调度每四年才会触发一次",
        hint_en="make sure your alerting expects that",
        hint_zh="请确认你的告警能接受这种频率",
    )


def _rule_top_of_hour(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """Everyone schedules at :00, so everyone queues at :00."""
    if expr.minute.sorted_values() != [0]:
        return None
    if len(expr.hour.sorted_values()) != 1:
        return None
    return Issue(
        rule_id="top-of-hour",
        severity=LEVEL_INFO,
        message_en=(
            "this schedule fires exactly on the hour, which is the busiest minute of "
            "the hour for shared infrastructure"
        ),
        message_zh="该调度正好卡在整点触发，而整点是共享基础设施最拥挤的时刻",
        hint_en="an odd minute such as :07 spreads the load",
        hint_zh="换成 07 这种不规则分钟可以把负载摊开",
    )


def _rule_every_minute(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """Running every minute is 1440 runs a day."""
    if len(expr.minute.sorted_values()) != 60:
        return None
    return Issue(
        rule_id="every-minute",
        severity=LEVEL_WARNING,
        message_en="this schedule fires 1440 times a day",
        message_zh="该调度每天会触发 1440 次",
        hint_en="if the job does not need minute-level precision, use a longer interval",
        hint_zh="如果任务不需要分钟级精度，请把间隔拉长",
    )


def _rule_no_timezone(expr: CronExpression, ctx: LintContext) -> Optional[Issue]:
    """Without a timezone the schedule depends on the machine."""
    if ctx.tz:
        return None
    if ctx.target in ("github-actions", "aws-eventbridge", "cron", "kubernetes", "gcp-scheduler"):
        return Issue(
            rule_id="no-timezone",
            severity=LEVEL_INFO,
            message_en=(
                "no timezone was given, so this schedule follows whatever timezone "
                "the machine or the service happens to use"
            ),
            message_zh=(
                "没有指定时区，该调度会跟随机器或服务本身所使用的时区"
            ),
            hint_en="pass --tz to see the exact run times",
            hint_zh="加上 --tz 可以看到精确的运行时刻",
        )
    return None


#: The rule registry.  Add your own by appending a :class:`Rule`.
RULES: List[Rule] = [
    Rule(
        id="never-fires",
        severity=LEVEL_ERROR,
        title_en="Schedule never fires",
        title_zh="调度永远不会触发",
        check=_rule_never_fires,
    ),
    Rule(
        id="dom-dow-or",
        severity=LEVEL_WARNING,
        title_en="Day fields use OR semantics",
        title_zh="两个「日」字段是「或」关系",
        check=_rule_dom_dow_or,
    ),
    Rule(
        id="step-not-even",
        severity=LEVEL_WARNING,
        title_en="Step does not divide the range evenly",
        title_zh="步长无法整除取值范围",
        check=_rule_step_drift,
    ),
    Rule(
        id="sub-five-minutes",
        severity=LEVEL_WARNING,
        title_en="Interval is shorter than GitHub Actions allows",
        title_zh="间隔短于 GitHub Actions 的限制",
        check=_rule_sub_five_minutes,
    ),
    Rule(
        id="utc-only",
        severity=LEVEL_WARNING,
        title_en="Target runs in UTC",
        title_zh="目标按 UTC 运行",
        check=_rule_utc_only,
    ),
    Rule(
        id="seconds-unsupported",
        severity=LEVEL_WARNING,
        title_en="Target has no seconds field",
        title_zh="目标没有秒字段",
        check=_rule_seconds_unsupported,
    ),
    Rule(
        id="macro-not-portable",
        severity=LEVEL_WARNING,
        title_en="@macro is not supported by the target",
        title_zh="目标不支持 @宏",
        check=_rule_macro_not_portable,
    ),
    Rule(
        id="every-minute",
        severity=LEVEL_WARNING,
        title_en="Runs 1440 times a day",
        title_zh="每天运行 1440 次",
        check=_rule_every_minute,
    ),
    Rule(
        id="short-month",
        severity=LEVEL_INFO,
        title_en="Day of month does not exist in every month",
        title_zh="并非每个月都有这一天",
        check=_rule_day_31,
    ),
    Rule(
        id="leap-day",
        severity=LEVEL_INFO,
        title_en="Only fires in leap years",
        title_zh="只在闰年触发",
        check=_rule_leap_day,
    ),
    Rule(
        id="top-of-hour",
        severity=LEVEL_INFO,
        title_en="Fires exactly on the hour",
        title_zh="正好卡在整点触发",
        check=_rule_top_of_hour,
    ),
    Rule(
        id="no-timezone",
        severity=LEVEL_INFO,
        title_en="No timezone was specified",
        title_zh="未指定时区",
        check=_rule_no_timezone,
    ),
]


def lint(expr: CronExpression, ctx: Optional[LintContext] = None) -> List[Issue]:
    """Run every rule against ``expr``."""
    context = ctx or LintContext()
    issues: List[Issue] = []
    for rule in RULES:
        issue = rule.run(expr, context)
        if issue is not None:
            issues.append(issue)
    issues.sort(key=lambda issue: (SEVERITY_ORDER.get(issue.severity, 9), issue.rule_id))
    return issues
