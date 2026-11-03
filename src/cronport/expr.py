"""The core expression model.

:class:`CronExpression` is the single source of truth in cronport.  Every
dialect (systemd, Kubernetes, GitHub Actions, ...) is parsed *into* this model
and rendered *out of* it, which is what makes cross dialect conversion
possible at all.

The model deliberately keeps the two pieces of classic cron trivia that trip
people up:

* **day-of-month / day-of-week semantics.**  Vixie cron treats the two fields
  as an *OR* when both of them are restricted, while Quartz treats them as an
  *AND*.  The model stores which rule applies so that conversions and the
  linter can reason about it.
* **DST correctness.**  Cron fires on *wall clock* time.  A wall clock time
  that does not exist (spring forward) is skipped; one that exists twice (fall
  back) fires twice.
"""

from __future__ import annotations

import bisect
import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone, tzinfo
from enum import Enum
from typing import Dict, Iterable, Iterator, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import CronSyntaxError, CronportError, NoOccurrenceError
from .fields import (
    DOW_ALIASES,
    MONTH_ALIASES,
    FieldSpec,
    format_field,
    parse_field,
)
from .notes import Note


#: ``@macro`` shorthands understood by Vixie cron.
MACROS: Dict[str, str] = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

#: Macros that have no schedule at all.
NON_SCHEDULABLE_MACROS = ("@reboot",)

#: How the day-of-month and day-of-week fields combine.
class DaySemantics(Enum):
    """How the day-of-month and day-of-week fields combine."""

    #: Vixie cron / Kubernetes / GitHub Actions: one of the two is enough.
    OR = "or"
    #: Quartz: both have to match.
    AND = "and"


@dataclass(frozen=True)
class Occurrence:
    """A single firing of a schedule."""

    local: datetime
    """The wall clock time in the requested timezone."""

    utc: datetime
    """The same instant expressed in UTC."""

    note: str = ""
    """Empty for a regular occurrence, otherwise a short DST remark."""


@dataclass(frozen=True)
class ScheduleWindow:
    """The result of looking forward (or backward) in time."""

    occurrences: List[Occurrence] = field(default_factory=list)
    skipped: List[Occurrence] = field(default_factory=list)
    """Wall clock times that do not exist in the requested timezone."""

    def __iter__(self) -> Iterator[Occurrence]:
        return iter(self.occurrences)

    def __len__(self) -> int:
        return len(self.occurrences)

    @property
    def datetimes(self) -> List[datetime]:
        return [occurrence.local for occurrence in self.occurrences]


@dataclass(frozen=True)
class CronExpression:
    """A parsed cron expression.

    The object is immutable and hashable, so it can be used as a dictionary
    key or stored in a set.
    """

    expression: str
    minute: FieldSpec
    hour: FieldSpec
    dom: FieldSpec
    month: FieldSpec
    dow: FieldSpec
    second: Optional[FieldSpec] = None
    year: Optional[FieldSpec] = None
    day_semantics: DaySemantics = DaySemantics.OR
    dialect: str = "cron"
    notes: Tuple[Note, ...] = ()
    """Caveats that came up while parsing, for example a lost AND semantics."""

    # ------------------------------------------------------------------
    # parsing
    # ------------------------------------------------------------------

    @classmethod
    def parse(
        cls,
        expression: str,
        *,
        dialect: str = "cron",
        allow_seconds: bool = False,
        allow_question: bool = False,
        day_semantics: Optional[DaySemantics] = None,
    ) -> "CronExpression":
        """Parse ``expression`` into a :class:`CronExpression`.

        Parameters
        ----------
        expression:
            The raw expression.
        dialect:
            Name of the source dialect; only used for error messages and for
            choosing the default field layout.
        allow_seconds:
            Accept a leading seconds field (Quartz style).
        allow_question:
            Accept Quartz' ``?`` placeholder in the day fields.
        day_semantics:
            Override the day-of-month / day-of-week combination rule.
        """
        text = expression.strip()
        if not text:
            raise CronSyntaxError(
                "expression is empty",
                "表达式为空",
                expression=expression,
            )

        if text.startswith("@"):
            macro = text.lower()
            if macro in NON_SCHEDULABLE_MACROS:
                raise CronSyntaxError(
                    f"{macro} is not a schedule: it has no recurring run times",
                    f"{macro} 不是调度表达式：它没有固定的运行时间",
                    expression=expression,
                    hint="it only means 'run once at boot'",
                    hint_zh="它只表示「开机时运行一次」",
                )
            if macro not in MACROS:
                known = ", ".join(sorted(MACROS))
                raise CronSyntaxError(
                    f"unknown macro {macro!r}",
                    f"未知的宏 {macro!r}",
                    expression=expression,
                    hint=f"known macros: {known}",
                    hint_zh=f"可用宏：{known}",
                )
            text = MACROS[macro]
            allow_question = False

        parts = text.split()
        if dialect == "quartz":
            semantics = day_semantics or DaySemantics.AND
            allow_question = True
        else:
            semantics = day_semantics or DaySemantics.OR

        seconds_spec: Optional[FieldSpec] = None
        year_spec: Optional[FieldSpec] = None

        if len(parts) == 5:
            minute_raw, hour_raw, dom_raw, month_raw, dow_raw = parts
        elif len(parts) == 6 and allow_seconds:
            seconds_raw, minute_raw, hour_raw, dom_raw, month_raw, dow_raw = parts
            seconds_spec = parse_field(
                seconds_raw, "second", 0, 59, expression=expression
            )
        elif len(parts) == 7 and allow_seconds:
            (
                seconds_raw,
                minute_raw,
                hour_raw,
                dom_raw,
                month_raw,
                dow_raw,
                year_raw,
            ) = parts
            seconds_spec = parse_field(
                seconds_raw, "second", 0, 59, expression=expression
            )
            year_spec = parse_field(
                year_raw, "year", 1970, 2099, expression=expression
            )
        else:
            expected = "6 or 7" if allow_seconds else "5"
            raise CronSyntaxError(
                f"expected {expected} fields, got {len(parts)}",
                f"期望 {expected} 个字段，实际得到 {len(parts)} 个",
                expression=expression,
                hint="format: minute hour day-of-month month day-of-week",
                hint_zh="格式：分 时 日 月 星期",
            )

        minute = parse_field(minute_raw, "minute", 0, 59, expression=expression)
        hour = parse_field(hour_raw, "hour", 0, 23, expression=expression)
        dom = parse_field(
            dom_raw,
            "day-of-month",
            1,
            31,
            expression=expression,
            allow_question=allow_question,
        )
        month = parse_field(
            month_raw, "month", 1, 12, aliases=MONTH_ALIASES, expression=expression
        )
        dow = parse_field(
            dow_raw,
            "day-of-week",
            0,
            6,
            aliases=DOW_ALIASES,
            expression=expression,
            allow_question=allow_question,
        )

        return cls(
            expression=expression.strip(),
            minute=minute,
            hour=hour,
            dom=dom,
            month=month,
            dow=dow,
            second=seconds_spec,
            year=year_spec,
            day_semantics=semantics,
            dialect=dialect,
        )

    # ------------------------------------------------------------------
    # introspection
    # ------------------------------------------------------------------

    @property
    def has_seconds(self) -> bool:
        return self.second is not None

    @property
    def fields(self) -> List[Tuple[str, FieldSpec]]:
        """The fields of the expression, in source order."""
        ordered: List[Tuple[str, FieldSpec]] = []
        if self.second is not None:
            ordered.append(("second", self.second))
        ordered.append(("minute", self.minute))
        ordered.append(("hour", self.hour))
        ordered.append(("day-of-month", self.dom))
        ordered.append(("month", self.month))
        ordered.append(("day-of-week", self.dow))
        if self.year is not None:
            ordered.append(("year", self.year))
        return ordered

    def canonical(self) -> str:
        """The expression written back out in a normalised way."""
        pieces = [format_field(spec) for _, spec in self.fields]
        return " ".join(pieces)

    def to_dict(self) -> Dict[str, object]:
        return {
            "expression": self.expression,
            "canonical": self.canonical(),
            "dialect": self.dialect,
            "day_semantics": self.day_semantics.value,
            "fields": {name: spec.to_dict() for name, spec in self.fields},
        }

    # ------------------------------------------------------------------
    # matching
    # ------------------------------------------------------------------

    @property
    def _dom_constrained(self) -> bool:
        if self.day_semantics is DaySemantics.AND:
            return not self.dom.unconstrained
        return not self.dom.is_star

    @property
    def _dow_constrained(self) -> bool:
        if self.day_semantics is DaySemantics.AND:
            return not self.dow.unconstrained
        return not self.dow.is_star

    def _day_matches_values(self, day_of_month: int, cron_dow: int) -> bool:
        """Does the day rule match this (day of month, day of week) pair?"""
        dom_constrained = self._dom_constrained
        dow_constrained = self._dow_constrained
        if not dom_constrained and not dow_constrained:
            return True
        dom_ok = day_of_month in self.dom.values
        dow_ok = cron_dow in self.dow.values
        if self.day_semantics is DaySemantics.AND:
            return (not dom_constrained or dom_ok) and (not dow_constrained or dow_ok)
        if dom_constrained and dow_constrained:
            return dom_ok or dow_ok
        if dom_constrained:
            return dom_ok
        return dow_ok

    def _day_matches(self, when: datetime) -> bool:
        return self._day_matches_values(when.day, _cron_dow(when))

    def matches(self, when: datetime) -> bool:
        """Does the schedule fire at ``when``?

        ``when`` may be naive (interpreted as wall clock time) or aware (its
        own timezone decides which wall clock time is meant).
        """
        naive = when.replace(tzinfo=None)
        if self.second is not None and naive.second not in self.second.values:
            return False
        if naive.minute not in self.minute.values:
            return False
        if naive.hour not in self.hour.values:
            return False
        if naive.month not in self.month.values:
            return False
        if self.year is not None and naive.year not in self.year.values:
            return False
        return self._day_matches(naive)

    # ------------------------------------------------------------------
    # iteration
    # ------------------------------------------------------------------

    def _time_of_day_table(self) -> List[int]:
        """Every allowed second-of-day, ascending.

        Pre-computing this makes the iterator a simple bisect away from a
        correct answer, which keeps ``next`` fast even for schedules such as
        ``0 0 29 2 *`` that only fire once every four years.
        """
        seconds = self.second.sorted_values() if self.second is not None else [0]
        minutes = self.minute.sorted_values()
        hours = self.hour.sorted_values()
        table: List[int] = []
        for hour in hours:
            for minute in minutes:
                for second in seconds:
                    table.append(hour * 3600 + minute * 60 + second)
        table.sort()
        return table

    def _iter_naive(self, start: datetime) -> Iterator[datetime]:
        """Yield matching naive wall clock datetimes, ascending."""
        table = self._time_of_day_table()
        if not table:
            return
        step = timedelta(seconds=1) if self.has_seconds else timedelta(minutes=1)
        current = start.replace(microsecond=0)
        if self.has_seconds:
            if current.second == 0 and current.microsecond == 0:
                current = current.replace(second=0)
        else:
            current = current.replace(second=0, microsecond=0)
            if current < start:
                current += timedelta(minutes=1)

        horizon = current.year + 200
        while current.year <= horizon:
            if current.month not in self.month.values:
                current = _next_allowed_month(current, self.month.values)
                continue
            if not self._day_matches(current):
                current = _next_day(current)
                continue
            index = bisect.bisect_left(table, _time_of_day(current))
            if index == len(table):
                current = _next_day(current)
                continue
            moment = _from_time_of_day(current.date(), table[index])
            if moment < current:
                # The only remaining time of day today has already passed.
                current = _next_day(current)
                continue
            yield moment
            current = moment + step

    def _iter_naive_backwards(self, start: datetime) -> Iterator[datetime]:
        """Yield matching naive wall clock datetimes, descending."""
        table = self._time_of_day_table()
        if not table:
            return
        step = timedelta(seconds=1) if self.has_seconds else timedelta(minutes=1)
        current = start.replace(microsecond=0)
        if not self.has_seconds:
            current = current.replace(second=0, microsecond=0)
            if current > start:
                current -= timedelta(minutes=1)

        horizon = current.year - 200
        while current.year >= horizon:
            if current.month not in self.month.values:
                current = _previous_allowed_month(current, self.month.values)
                continue
            if not self._day_matches(current):
                current = _previous_day(current)
                continue
            index = bisect.bisect_right(table, _time_of_day(current)) - 1
            if index < 0:
                current = _previous_day(current)
                continue
            moment = _from_time_of_day(current.date(), table[index])
            yield moment
            current = moment - step

    # ------------------------------------------------------------------
    # public scheduling API
    # ------------------------------------------------------------------

    def next_window(
        self,
        count: int = 5,
        *,
        tz: Optional[tzinfo] = None,
        start: Optional[datetime] = None,
    ) -> ScheduleWindow:
        """The next ``count`` firings at or after ``start``."""
        zone = tz if tz is not None else local_timezone()
        reference = start or datetime.now(zone)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=zone)
        naive_start = reference.astimezone(zone).replace(tzinfo=None)
        if self.has_seconds:
            naive_start = naive_start.replace(microsecond=0)
            if naive_start < reference.astimezone(zone).replace(tzinfo=None):
                naive_start += timedelta(seconds=1)
        else:
            naive_start = naive_start.replace(second=0, microsecond=0)
            if naive_start < reference.astimezone(zone).replace(tzinfo=None):
                naive_start += timedelta(minutes=1)

        occurrences: List[Occurrence] = []
        skipped: List[Occurrence] = []
        for naive in self._iter_naive(naive_start):
            resolved = _resolve_local(naive, zone)
            if not resolved:
                skipped.append(
                    Occurrence(
                        local=naive.replace(tzinfo=zone),
                        utc=naive.replace(tzinfo=timezone.utc),
                        note="nonexistent",
                    )
                )
                continue
            for aware, note in resolved:
                occurrences.append(
                    Occurrence(
                        local=aware,
                        utc=aware.astimezone(timezone.utc),
                        note=note,
                    )
                )
                if len(occurrences) >= count:
                    return ScheduleWindow(occurrences=occurrences, skipped=skipped)
        raise NoOccurrenceError(
            "this schedule never fires within the next 200 years",
            "该调度在未来 200 年内不会触发",
            hint="the expression may describe an impossible date, "
            "for example the 30th of February",
            hint_zh="表达式可能描述了一个不存在的日期，例如 2 月 30 日",
        )

    def previous_window(
        self,
        count: int = 5,
        *,
        tz: Optional[tzinfo] = None,
        end: Optional[datetime] = None,
    ) -> ScheduleWindow:
        """The ``count`` firings before ``end``."""
        zone = tz if tz is not None else local_timezone()
        reference = end or datetime.now(zone)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=zone)
        naive_end = reference.astimezone(zone).replace(tzinfo=None)
        if not self.has_seconds:
            naive_end = naive_end.replace(second=0, microsecond=0)
            if naive_end > reference.astimezone(zone).replace(tzinfo=None):
                naive_end -= timedelta(minutes=1)

        occurrences: List[Occurrence] = []
        for naive in self._iter_naive_backwards(naive_end):
            resolved = _resolve_local(naive, zone)
            for aware, note in resolved or []:
                occurrences.append(
                    Occurrence(
                        local=aware,
                        utc=aware.astimezone(timezone.utc),
                        note=note,
                    )
                )
                if len(occurrences) >= count:
                    break
            if len(occurrences) >= count:
                break
        if not occurrences:
            raise NoOccurrenceError(
                "this schedule never fired in the past 200 years",
                "该调度在过去 200 年内没有触发过",
            )
        return ScheduleWindow(occurrences=occurrences)

    def next_runs(
        self,
        count: int = 5,
        *,
        tz: Optional[tzinfo] = None,
        start: Optional[datetime] = None,
    ) -> List[datetime]:
        """Convenience wrapper returning plain datetimes."""
        return self.next_window(count, tz=tz, start=start).datetimes

    def previous_runs(
        self,
        count: int = 5,
        *,
        tz: Optional[tzinfo] = None,
        end: Optional[datetime] = None,
    ) -> List[datetime]:
        """Convenience wrapper returning plain datetimes."""
        return self.previous_window(count, tz=tz, end=end).datetimes

    # ------------------------------------------------------------------
    # equivalence
    # ------------------------------------------------------------------

    def day_truth_table(self) -> int:
        """A bitmask of every (day of month, day of week) pair that fires.

        Two expressions fire on exactly the same days if and only if their
        truth tables are identical.  Using the table instead of comparing the
        raw fields is what makes ``0 9 * * 0-6`` and ``0 9 * * *`` correctly
        compare as equal.
        """
        bits = 0
        for day in range(1, 32):
            for dow in range(0, 7):
                if self._day_matches_values(day, dow):
                    bits |= 1 << ((day - 1) * 7 + dow)
        return bits

    def signature(self) -> Tuple[object, ...]:
        """A hashable fingerprint of *when* this schedule fires."""
        seconds = self.second.sorted_values() if self.second is not None else [0]
        return (
            tuple(seconds),
            tuple(self.minute.sorted_values()),
            tuple(self.hour.sorted_values()),
            tuple(self.month.sorted_values()),
            self.day_truth_table(),
        )

    def is_equivalent_to(self, other: "CronExpression") -> bool:
        """Do both schedules fire at exactly the same instants?"""
        return self.signature() == other.signature()


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _cron_dow(when: datetime) -> int:
    """Cron's day of week, where Sunday is 0."""
    return (when.weekday() + 1) % 7


def _time_of_day(when: datetime) -> int:
    return when.hour * 3600 + when.minute * 60 + when.second


def _from_time_of_day(day: date, seconds: int) -> datetime:
    return datetime(
        day.year,
        day.month,
        day.day,
        seconds // 3600,
        (seconds % 3600) // 60,
        seconds % 60,
    )


def _next_day(when: datetime) -> datetime:
    return (when + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def _previous_day(when: datetime) -> datetime:
    """The last instant of the day before ``when``."""
    return (when - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)


def _next_allowed_month(when: datetime, months: Iterable[int]) -> datetime:
    ordered = sorted(months)
    for month in ordered:
        if month > when.month:
            return datetime(when.year, month, 1)
    return datetime(when.year + 1, ordered[0], 1)


def _previous_allowed_month(when: datetime, months: Iterable[int]) -> datetime:
    ordered = sorted(months)
    for month in reversed(ordered):
        if month < when.month:
            return datetime(when.year, month, 1)
    return datetime(when.year - 1, ordered[-1], 1)


def local_timezone() -> tzinfo:
    """The timezone of the machine cronport runs on."""
    return datetime.now().astimezone().tzinfo or timezone.utc


def resolve_timezone(name: Optional[str]) -> tzinfo:
    """Turn a timezone name into a :class:`datetime.tzinfo`.

    Accepts IANA names (``Asia/Shanghai``), ``UTC`` and fixed offsets
    (``+08:00``, ``-0530``).
    """
    if not name:
        return local_timezone()
    cleaned = name.strip()
    if cleaned.upper() in ("UTC", "Z", "GMT"):
        return timezone.utc
    if cleaned.startswith(("+", "-")):
        return _parse_offset(cleaned)
    try:
        return ZoneInfo(cleaned)
    except ZoneInfoNotFoundError:
        raise CronportError(
            f"unknown timezone {name!r}",
            f"未知时区 {name!r}",
            hint="try an IANA name such as Asia/Shanghai or UTC",
            hint_zh="请使用 IANA 名称，例如 Asia/Shanghai 或 UTC",
        ) from None
    except Exception:  # pragma: no cover - defensive
        raise CronportError(
            f"could not load timezone {name!r}",
            f"无法加载时区 {name!r}",
        ) from None


def _parse_offset(text: str) -> timezone:
    sign = -1 if text[0] == "-" else 1
    body = text[1:].replace(":", "")
    if len(body) not in (2, 4) or not body.isdigit():
        raise CronSyntaxError(
            f"invalid UTC offset {text!r}",
            f"无效的 UTC 偏移量 {text!r}",
            hint="use +08:00 or -0530",
            hint_zh="请使用 +08:00 或 -0530 这样的写法",
        )
    if len(body) == 2:
        hours, minutes = int(body), 0
    else:
        hours, minutes = int(body[:2]), int(body[2:])
    delta = timedelta(hours=hours, minutes=minutes) * sign
    return timezone(delta)


def _resolve_local(naive: datetime, zone: tzinfo) -> List[Tuple[datetime, str]]:
    """Map a naive wall clock time onto real instants in ``zone``.

    Returns an empty list when the wall clock time does not exist (spring
    forward) and two entries when it exists twice (fall back).
    """
    first = naive.replace(tzinfo=zone, fold=0)
    roundtrip = first.astimezone(timezone.utc).astimezone(zone)
    if roundtrip.replace(tzinfo=None) != naive:
        # The wall clock time is skipped entirely by a DST transition.
        return []
    second = naive.replace(tzinfo=zone, fold=1)
    if first.utcoffset() != second.utcoffset():
        # The wall clock time happens twice; cron fires on both.
        return [(first, "ambiguous-first"), (second, "ambiguous-second")]
    return [(first, "")]


def days_in_month(year: int, month: int) -> int:
    """Number of days in ``year``/``month``."""
    return calendar.monthrange(year, month)[1]
