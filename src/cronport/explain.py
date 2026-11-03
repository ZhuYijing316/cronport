"""Turning a schedule into a sentence a human can read.

The goal is not to describe the fields, it is to answer the question the user
actually has: *when does this thing run?*  Everything here is written twice,
once in English and once in Chinese, because cronport speaks both.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .expr import CronExpression, DaySemantics
from .fields import FieldSpec

WEEKDAY_NAMES_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
WEEKDAY_NAMES_ZH = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
MONTH_NAMES_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
MONTH_NAMES_ZH = (
    "1 月",
    "2 月",
    "3 月",
    "4 月",
    "5 月",
    "6 月",
    "7 月",
    "8 月",
    "9 月",
    "10 月",
    "11 月",
    "12 月",
)


@dataclass(frozen=True)
class FieldExplanation:
    """What one field of the expression means."""

    name: str
    raw: str
    values: Tuple[int, ...]
    meaning_en: str
    meaning_zh: str


@dataclass
class Explanation:
    """The full explanation of a schedule."""

    summary_en: str
    summary_zh: str
    fields: List[FieldExplanation] = field(default_factory=list)
    pattern_en: str = ""
    pattern_zh: str = ""
    notes: List[str] = field(default_factory=list)

    def summary(self, lang: str = "en") -> str:
        return self.summary_zh if lang.startswith("zh") else self.summary_en

    def to_dict(self) -> Dict[str, object]:
        return {
            "summary": {"en": self.summary_en, "zh": self.summary_zh},
            "pattern": {"en": self.pattern_en, "zh": self.pattern_zh},
            "fields": [
                {
                    "name": item.name,
                    "raw": item.raw,
                    "values": list(item.values),
                    "meaning": {"en": item.meaning_en, "zh": item.meaning_zh},
                }
                for item in self.fields
            ],
        }


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _is_progression(values: Sequence[int], step: Optional[int] = None) -> Optional[int]:
    """Return the step if ``values`` is an arithmetic progression."""
    if len(values) < 2:
        return None
    if step is None:
        step = values[1] - values[0]
    if step <= 0:
        return None
    for index in range(len(values) - 1):
        if values[index + 1] - values[index] != step:
            return None
    return step


def _join_en(items: Sequence[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def _join_zh(items: Sequence[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return "、".join(items[:-1]) + "和" + items[-1]


def _weekday_names(values: Sequence[int]) -> List[str]:
    return [WEEKDAY_NAMES_EN[value - 1] for value in values]


def _weekday_phrase(values: Sequence[int]) -> Tuple[str, str]:
    """``(english, chinese)`` for a set of cron day-of-week numbers."""
    ordered = sorted(values)
    if len(ordered) == 7:
        return "every day", "每天"
    if len(ordered) == 1:
        name_en = WEEKDAY_NAMES_EN[ordered[0] - 1]
        name_zh = WEEKDAY_NAMES_ZH[ordered[0] - 1]
        return f"on {name_en}", f"每{name_zh}"
    # Contiguous runs become ranges, for example Monday to Friday.
    groups: List[List[int]] = []
    for value in ordered:
        if groups and value == groups[-1][-1] + 1:
            groups[-1].append(value)
        else:
            groups.append([value])
    if len(groups) == 1:
        group = groups[0]
        first_en = WEEKDAY_NAMES_EN[group[0] - 1]
        last_en = WEEKDAY_NAMES_EN[group[-1] - 1]
        first_zh = WEEKDAY_NAMES_ZH[group[0] - 1]
        last_zh = WEEKDAY_NAMES_ZH[group[-1] - 1]
        return f"on {first_en} to {last_en}", f"{first_zh}至{last_zh}"
    en = ", ".join(WEEKDAY_NAMES_EN[value - 1] for value in ordered)
    zh = "、".join(WEEKDAY_NAMES_ZH[value - 1] for value in ordered)
    return f"on {en}", f"每{zh}"


def _dom_phrase(values: Sequence[int]) -> Tuple[str, str]:
    """``(english, chinese)`` for a set of day-of-month numbers."""
    ordered = sorted(values)
    if len(ordered) == 1:
        day = ordered[0]
        suffix = "th"
        if day % 10 == 1 and day != 11:
            suffix = "st"
        elif day % 10 == 2 and day != 12:
            suffix = "nd"
        elif day % 10 == 3 and day != 13:
            suffix = "rd"
        return f"on the {day}{suffix} of the month", f"每月 {day} 号"
    return (
        f"on the {_join_en([str(value) for value in ordered])} of the month",
        f"每月 {_join_zh([str(value) for value in ordered])} 号",
    )


def _month_phrase(values: Sequence[int]) -> Tuple[str, str]:
    """``(english, chinese)`` for a set of month numbers."""
    ordered = sorted(values)
    if len(ordered) == 12:
        return "", ""
    if len(ordered) == 1:
        return f"in {MONTH_NAMES_EN[ordered[0] - 1]}", f"{MONTH_NAMES_ZH[ordered[0] - 1]}"
    en = _join_en([MONTH_NAMES_EN[value - 1] for value in ordered])
    zh = _join_zh([MONTH_NAMES_ZH[value - 1] for value in ordered])
    return f"in {en}", f"{zh}"


def _time_phrase(expr: CronExpression) -> Tuple[str, str]:
    """``(english, chinese)`` describing when during a day the schedule fires."""
    minutes = expr.minute.sorted_values()
    hours = expr.hour.sorted_values()

    every_minute = len(minutes) == 60 and len(hours) == 24
    if every_minute:
        return "every minute", "每分钟"

    if len(minutes) == 1 and len(hours) == 1:
        return (
            f"at {hours[0]:02d}:{minutes[0]:02d}",
            f"{hours[0]:02d}:{minutes[0]:02d}",
        )

    if len(minutes) == 1 and len(hours) == 24:
        return (
            f"every hour at minute {minutes[0]}",
            f"每小时第 {minutes[0]} 分",
        )

    if len(minutes) > 1 and len(hours) == 24:
        step = _is_progression(minutes)
        if step and minutes[0] == 0 and (60 % step == 0):
            return f"every {step} minutes", f"每 {step} 分钟"
        listed = _join_en([str(value) for value in minutes])
        listed_zh = _join_zh([str(value) for value in minutes])
        return f"at minutes {listed} of every hour", f"每小时的第 {listed_zh} 分钟"

    if len(minutes) > 1 and len(hours) == 1:
        step = _is_progression(minutes)
        if step and minutes[0] == 0 and (60 % step == 0):
            return (
                f"every {step} minutes during the {hours[0]:02d}:00 hour",
                f"{hours[0]:02d} 点这一小时内每 {step} 分钟",
            )
        times_en = _join_en([f"{hours[0]:02d}:{value:02d}" for value in minutes])
        times_zh = _join_zh([f"{hours[0]:02d}:{value:02d}" for value in minutes])
        return f"at {times_en}", times_zh

    if len(minutes) == 1 and len(hours) > 1:
        times_en = _join_en([f"{value:02d}:{minutes[0]:02d}" for value in hours])
        times_zh = _join_zh([f"{value:02d}:{minutes[0]:02d}" for value in hours])
        return f"at {times_en}", times_zh

    times_en = _join_en([f"{hour:02d}:{minute:02d}" for hour in hours for minute in minutes])
    times_zh = _join_zh([f"{hour:02d}:{minute:02d}" for hour in hours for minute in minutes])
    return f"at {times_en}", times_zh


def _date_phrase(expr: CronExpression) -> Tuple[str, str]:
    """``(english, chinese)`` describing which days the schedule fires on."""
    dom_constrained = expr._dom_constrained
    dow_constrained = expr._dow_constrained

    if not dom_constrained and not dow_constrained:
        return "every day", "每天"

    if dom_constrained and dow_constrained:
        dom_en, dom_zh = _dom_phrase(expr.dom.sorted_values())
        dow_en, dow_zh = _weekday_phrase(expr.dow.sorted_values())
        if expr.day_semantics is DaySemantics.OR:
            return (
                f"{dom_en} or {dow_en}",
                f"{dom_zh}，或{dow_zh}",
            )
        return f"{dom_en} and {dow_en}", f"{dom_zh}且{dow_zh}"

    if dom_constrained:
        return _dom_phrase(expr.dom.sorted_values())
    return _weekday_phrase(expr.dow.sorted_values())


# ----------------------------------------------------------------------
# public API
# ----------------------------------------------------------------------


def explain(expr: CronExpression) -> Explanation:
    """Build a full explanation of ``expr``."""
    time_en, time_zh = _time_phrase(expr)
    date_en, date_zh = _date_phrase(expr)
    month_en, month_zh = _month_phrase(expr.month.sorted_values())

    if date_en == "every day":
        summary_en = f"{time_en}, every day"
    else:
        summary_en = f"{time_en} {date_en}"
    if month_en:
        summary_en = f"{summary_en} {month_en}"
    summary_en = summary_en[0].upper() + summary_en[1:]

    gap = " " if time_zh[:1].isdigit() else ""
    if month_zh:
        summary_zh = f"{month_zh}，{date_zh}{gap}{time_zh}"
    else:
        summary_zh = f"{date_zh}{gap}{time_zh}"

    explanation = Explanation(
        summary_en=summary_en,
        summary_zh=summary_zh,
        fields=_field_explanations(expr),
    )
    pattern_en, pattern_zh = _detect_pattern(expr)
    explanation.pattern_en = pattern_en
    explanation.pattern_zh = pattern_zh
    return explanation


def _field_explanations(expr: CronExpression) -> List[FieldExplanation]:
    """One line per field, in the order the fields appear."""
    result: List[FieldExplanation] = []

    for name, spec in expr.fields:
        values = spec.sorted_values()
        meaning_en, meaning_zh = _field_meaning(name, spec)
        result.append(
            FieldExplanation(
                name=name,
                raw=spec.raw,
                values=tuple(values),
                meaning_en=meaning_en,
                meaning_zh=meaning_zh,
            )
        )
    return result


def _field_meaning(name: str, spec: FieldSpec) -> Tuple[str, str]:
    """A short description of what one field selects."""
    values = spec.sorted_values()
    if spec.is_question:
        return "no specific value", "不限定"

    if name == "minute":
        if len(values) == 60:
            return "every minute", "每分钟"
        if len(values) == 1:
            return f"minute {values[0]}", f"第 {values[0]} 分钟"
        step = _is_progression(values)
        if step:
            return f"every {step} minutes", f"每 {step} 分钟"
        listed = _join_en([str(value) for value in values])
        listed_zh = _join_zh([str(value) for value in values])
        return f"minutes {listed}", f"第 {listed_zh} 分钟"

    if name == "hour":
        if len(values) == 24:
            return "every hour", "每小时"
        if len(values) == 1:
            return f"{values[0]:02d}:00", f"{values[0]:02d} 点"
        listed = _join_en([f"{value:02d}" for value in values])
        listed_zh = _join_zh([f"{value:02d}" for value in values])
        return f"hours {listed}", f"{listed_zh} 点"

    if name == "day-of-month":
        if len(values) == 31:
            return "every day of the month", "每月的每一天"
        return _dom_phrase(values)

    if name == "month":
        if len(values) == 12:
            return "every month", "每月"
        return _month_phrase(values)

    if name == "day-of-week":
        if len(values) == 7:
            return "every day of the week", "每周的每一天"
        return _weekday_phrase(values)

    if name == "second":
        if len(values) == 60:
            return "every second", "每秒"
        listed = _join_en([str(value) for value in values])
        listed_zh = _join_zh([str(value) for value in values])
        return f"seconds {listed}", f"第 {listed_zh} 秒"

    if name == "year":
        listed = _join_en([str(value) for value in values])
        listed_zh = _join_zh([str(value) for value in values])
        return f"years {listed}", f"{listed_zh} 年"

    return ", ".join(str(value) for value in values), ", ".join(str(value) for value in values)


def _detect_pattern(expr: CronExpression) -> Tuple[str, str]:
    """Recognise a few well known shapes and name them."""
    minutes = expr.minute.sorted_values()
    hours = expr.hour.sorted_values()
    dom = expr.dom.sorted_values()
    dow = expr.dow.sorted_values()
    month = expr.month.sorted_values()

    every_day = not expr._dom_constrained and not expr._dow_constrained
    weekdays = dow == [1, 2, 3, 4, 5] and not expr._dom_constrained
    weekends = dow == [0, 6] and not expr._dom_constrained

    if every_day and minutes == [0] and hours == [0]:
        return "daily at midnight", "每天午夜"
    if every_day and minutes == [0] and len(hours) == 1:
        return f"daily at {hours[0]:02d}:00", f"每天 {hours[0]:02d}:00"
    if weekdays and minutes == [0] and len(hours) == 1:
        return f"weekdays at {hours[0]:02d}:00", f"工作日 {hours[0]:02d}:00"
    if weekends and minutes == [0] and len(hours) == 1:
        return f"weekends at {hours[0]:02d}:00", f"周末 {hours[0]:02d}:00"
    if every_day and len(minutes) == 60 and len(hours) == 24:
        return "every minute", "每分钟"
    if every_day and len(minutes) > 1 and len(hours) == 24:
        step = _is_progression(minutes)
        if step and 60 % step == 0:
            return f"every {step} minutes", f"每 {step} 分钟"
    if every_day and len(minutes) == 1 and len(hours) == 24:
        return "hourly", "每小时"
    if dom == [1] and not expr._dow_constrained and month == list(range(1, 13)):
        return "monthly on the 1st", "每月 1 号"
    return "", ""
