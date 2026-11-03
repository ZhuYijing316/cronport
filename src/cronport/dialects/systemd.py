"""The systemd dialect.

``OnCalendar=`` does not look like cron at all::

    [Timer]
    OnCalendar=Mon..Fri *-*-* 09:00:00

Three things make it interesting to convert:

* systemd's date component and its weekday component are combined with
  **AND**, while cron combines the two day fields with **OR**.
* systemd ORs several ``OnCalendar=`` lines together, which is the only way to
  express cron's OR rule faithfully.
* systemd understands step values in the time component (``*:0/15``).
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Dict, List, Optional, Set

from ..errors import CronSyntaxError
from ..expr import CronExpression, DaySemantics
from ..fields import compress
from .base import (
    LEVEL_INFO,
    LEVEL_WARNING,
    Conversion,
    Dialect,
    Note,
    dom_component,
    dow_component,
    month_component,
    time_component,
)

#: The shorthands systemd accepts in ``OnCalendar=``.
SHORTHANDS: Dict[str, str] = {
    "minutely": "* * * * *",
    "hourly": "0 * * * *",
    "daily": "0 0 * * *",
    "midnight": "0 0 * * *",
    "weekly": "0 0 * * 0",
    "monthly": "0 0 1 * *",
    "quarterly": "0 0 1 1,4,7,10 *",
    "semiannually": "0 0 1 1,7 *",
    "yearly": "0 0 1 1 *",
    "annually": "0 0 1 1 *",
}

_DOW_LOOKUP = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}

_WEEKDAY_TOKEN = re.compile(r"^[A-Za-z]{3}(\.\.[A-Za-z]{3}|[,].*)?$")


class SystemdDialect(Dialect):
    """systemd timers (``OnCalendar=``)."""

    name = "systemd"
    label = "systemd timer (OnCalendar=)"
    aliases = ("systemd-timer", "oncalendar", "timer")
    supports_timezone = True
    supports_seconds = True

    # -- rendering ---------------------------------------------------

    def render(self, expr: CronExpression, *, tz: Optional[str] = None) -> Conversion:
        notes: List[Note] = []
        time_part = self._time_part(expr)

        dom_constrained = expr._dom_constrained
        dow_constrained = expr._dow_constrained
        or_semantics = (
            expr.day_semantics is DaySemantics.OR and dom_constrained and dow_constrained
        )

        if or_semantics:
            # systemd ORs multiple OnCalendar= lines, so the faithful
            # translation of cron's OR rule is two lines.
            lines = [
                f"{self._date_part(expr, dom=True, dow=False)} {time_part}",
                f"{self._date_part(expr, dom=False, dow=True)} {time_part}",
            ]
            notes.append(
                Note(
                    LEVEL_WARNING,
                    "cron fires when day-of-month OR day-of-week matches. systemd "
                    "combines the two day fields with AND, so the faithful translation "
                    "needs two OnCalendar= lines (systemd ORs multiple lines together).",
                    "cron 在「日」或「星期」任一匹配时触发；systemd 的这两个字段是「且」的关系，"
                    "因此忠实的翻译需要两行 OnCalendar=（systemd 会把多行按「或」合并）。",
                )
            )
        elif dow_constrained and not dom_constrained:
            lines = [f"{self._date_part(expr, dom=False, dow=True)} {time_part}"]
        else:
            lines = [f"{self._date_part(expr, dom=True, dow=False)} {time_part}"]

        if expr.has_seconds:
            notes.append(
                Note(
                    LEVEL_WARNING,
                    "systemd timers support seconds, so the seconds field was kept",
                    "systemd 定时器支持秒，秒字段已保留",
                )
            )

        expression = "\n".join(lines)
        if tz:
            # Every OnCalendar= line needs its own timezone suffix.
            expression = "\n".join(f"{line} {tz}" for line in lines)
            notes.append(
                Note(
                    LEVEL_INFO,
                    f"the timezone was appended to the OnCalendar= value ({tz}); "
                    "without it systemd uses the machine's local timezone",
                    f"时区已附加到 OnCalendar= 的值后面（{tz}）；不写时 systemd 使用机器本地时区",
                )
            )
        return Conversion(self.name, expression, notes)

    def _time_part(self, expr: CronExpression) -> str:
        hours = time_component(expr.hour.values, 0, 23)
        minutes = time_component(expr.minute.values, 0, 59)
        if expr.second is not None:
            seconds = time_component(expr.second.values, 0, 59)
        else:
            seconds = "00"
        return f"{hours}:{minutes}:{seconds}"

    def _date_part(self, expr: CronExpression, *, dom: bool, dow: bool) -> str:
        pieces: List[str] = []
        if dow:
            pieces.append(dow_component(expr.dow.values))
        month_restricted = not expr.month.is_star
        if dom and month_restricted:
            pieces.append(f"*-{month_component(expr.month.values)}-{dom_component(expr.dom.values)}")
        elif dom:
            pieces.append(f"*-*-{dom_component(expr.dom.values)}")
        elif month_restricted:
            pieces.append(f"*-{month_component(expr.month.values)}-*")
        else:
            pieces.append("*-*-*")
        return " ".join(pieces)

    # -- parsing -----------------------------------------------------

    def parse(self, text: str) -> CronExpression:
        raw = text.strip()
        if not raw:
            raise CronSyntaxError("OnCalendar value is empty", "OnCalendar 的值为空")

        lowered = raw.lower()
        if lowered in SHORTHANDS:
            return CronExpression.parse(SHORTHANDS[lowered], dialect="cron")

        # A trailing timezone is not part of the schedule itself.
        tokens = raw.split()
        if len(tokens) > 1:
            last = tokens[-1]
            looks_like_zone = "/" in last or last.upper() in ("UTC", "GMT")
            if looks_like_zone:
                tokens = tokens[:-1]

        weekday: Optional[Set[int]] = None
        days: Optional[Set[int]] = None
        months: Optional[Set[int]] = None
        dom_restricted = False
        month_restricted = False
        hours: Set[int] = set(range(24))
        minutes: Set[int] = set(range(60))
        seconds: Set[int] = {0}

        for token in tokens:
            if ":" in token:
                hours, minutes, seconds = _parse_time(token)
            elif _WEEKDAY_TOKEN.match(token):
                weekday = _parse_weekdays(token)
            elif "-" in token or "*" in token:
                days, months, dom_restricted, month_restricted = _parse_date(token)
            else:
                raise CronSyntaxError(
                    f"cannot understand the OnCalendar component {token!r}",
                    f"无法识别的 OnCalendar 片段 {token!r}",
                    expression=text,
                    hint="expected something like 'Mon..Fri *-*-* 09:00:00'",
                    hint_zh="应当形如 'Mon..Fri *-*-* 09:00:00'",
                )

        notes: List[Note] = []
        # systemd ANDs its weekday and its date component.  cron ORs its two
        # day fields, so an unrestricted field has to stay '*' here, otherwise
        # the cron expression would silently fire far more often.
        if dom_restricted and weekday is not None:
            notes.append(
                Note(
                    LEVEL_WARNING,
                    "systemd combines the weekday and the date with AND, while cron "
                    "combines its two day fields with OR. This cron expression fires "
                    "more often than the original systemd schedule.",
                    "systemd 的「星期」与「日期」是「且」的关系，而 cron 的两个「日」字段是"
                    "「或」的关系，因此转换出的 cron 表达式触发次数会比原 systemd 更多。",
                )
            )

        dom_expr = compress(sorted(days)) if dom_restricted else "*"
        month_expr = compress(sorted(months)) if month_restricted else "*"
        dow_expr = compress(sorted(weekday)) if weekday is not None else "*"

        cron_text = (
            f"{compress(sorted(minutes))} {compress(sorted(hours))} "
            f"{dom_expr} {month_expr} {dow_expr}"
        )
        if seconds != {0}:
            cron_text = f"{compress(sorted(seconds))} {cron_text}"
            expression = CronExpression.parse(
                cron_text, dialect="cron", allow_seconds=True
            )
        else:
            expression = CronExpression.parse(cron_text, dialect="cron")
        if notes:
            expression = replace(expression, notes=tuple(notes))
        return expression


def _parse_component(
    text: str,
    low: int,
    high: int,
    names: Optional[Dict[str, int]] = None,
) -> Set[int]:
    """Parse one systemd component into the set of values it selects."""
    values: Set[int] = set()
    for term in text.split(","):
        term = term.strip()
        if not term:
            continue
        step = 1
        if "/" in term:
            term, _, step_text = term.partition("/")
            if not step_text.isdigit() or int(step_text) == 0:
                raise CronSyntaxError(
                    f"invalid repetition {step_text!r} in systemd component {text!r}",
                    f"systemd 片段 {text!r} 中的重复值 {step_text!r} 无效",
                )
            step = int(step_text)
        if ".." in term:
            start_text, _, end_text = term.partition("..")
            start = _lookup(start_text, names)
            end = _lookup(end_text, names)
            values.update(range(start, end + 1, step))
        else:
            start = _lookup(term, names)
            if step > 1:
                values.update(range(start, high + 1, step))
            else:
                values.add(start)
    for value in list(values):
        if not (low <= value <= high):
            raise CronSyntaxError(
                f"value {value} is out of range ({low}-{high})",
                f"值 {value} 超出范围（{low}-{high}）",
            )
    return values


def _lookup(text: str, names: Optional[Dict[str, int]]) -> int:
    cleaned = text.strip()
    if cleaned == "*":
        raise CronSyntaxError(
            "a bare '*' cannot be converted to a single value",
            "单独的 '*' 无法转换成单个值",
        )
    if names and not cleaned.isdigit():
        key = cleaned.lower()[:3]
        if key not in names:
            raise CronSyntaxError(
                f"unknown name {cleaned!r}",
                f"未知的名称 {cleaned!r}",
            )
        return names[key]
    if not cleaned.isdigit():
        raise CronSyntaxError(
            f"invalid value {cleaned!r}",
            f"无效的值 {cleaned!r}",
        )
    return int(cleaned)


def _parse_weekdays(token: str) -> Set[int]:
    return _parse_component(token, 0, 6, _DOW_LOOKUP)


def _parse_date(token: str) -> tuple:
    """Parse ``*-MM-DD`` / ``*-*-DD`` into (days, months, dom, month).

    The two booleans say whether the component actually *restricts* the
    schedule, which matters: an unrestricted day-of-month has to stay ``*``
    in the cron expression, otherwise cron would apply its OR rule.
    """
    parts = token.split("-")
    if len(parts) != 3:
        raise CronSyntaxError(
            f"cannot understand the date component {token!r}",
            f"无法识别的日期片段 {token!r}",
            hint="expected a year-month-day shape such as *-*-*",
            hint_zh="应当是「年-月-日」形式，例如 *-*-*",
        )
    _, month_part, day_part = parts
    month_restricted = month_part not in ("*", "")
    dom_restricted = day_part not in ("*", "")
    months = (
        _parse_component(month_part, 1, 12) if month_restricted else set(range(1, 13))
    )
    days = _parse_component(day_part, 1, 31) if dom_restricted else set(range(1, 32))
    return days, months, dom_restricted, month_restricted


def _parse_time(token: str) -> tuple:
    """Parse ``HH:MM:SS`` into (hours, minutes, seconds)."""
    pieces = token.split(":")
    if len(pieces) == 2:
        hour_part, minute_part = pieces
        second_part = "0"
    elif len(pieces) == 3:
        hour_part, minute_part, second_part = pieces
    else:
        raise CronSyntaxError(
            f"cannot understand the time component {token!r}",
            f"无法识别的时间片段 {token!r}",
            hint="expected HH:MM:SS",
            hint_zh="应当形如 HH:MM:SS",
        )
    hours = (
        _parse_component(hour_part, 0, 23)
        if hour_part not in ("*", "")
        else set(range(24))
    )
    minutes = (
        _parse_component(minute_part, 0, 59)
        if minute_part not in ("*", "")
        else set(range(60))
    )
    seconds = (
        _parse_component(second_part, 0, 59)
        if second_part not in ("*", "")
        else set(range(60))
    )
    return hours, minutes, seconds
