"""Shared plumbing for the dialect implementations.

A *dialect* is one scheduler's flavour of schedule syntax.  Every dialect can

* render a :class:`~cronport.expr.CronExpression` into its own syntax, and
* parse its own syntax back into a :class:`~cronport.expr.CronExpression`.

Rendering always returns a :class:`Conversion`, which carries the rendered
expression *and* a list of notes explaining anything that changed on the way
-- a dropped seconds field, a timezone that the target cannot express, a
schedule that has to be split across two rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from ..expr import CronExpression, DaySemantics
from ..notes import LEVEL_ERROR, LEVEL_WARNING, Note

#: Cron day-of-week numbers, Sunday first.
DOW_NAMES = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

#: Month numbers to their English names.
MONTH_NAMES = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


@dataclass
class Conversion:
    """The result of rendering a schedule for one target."""

    target: str
    expression: str
    notes: List[Note] = field(default_factory=list)
    extras: Dict[str, str] = field(default_factory=dict)
    """Extra configuration the target needs, for example ``timeZone``."""

    @property
    def errors(self) -> List[Note]:
        return [note for note in self.notes if note.level == LEVEL_ERROR]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def to_dict(self) -> Dict[str, object]:
        return {
            "target": self.target,
            "expression": self.expression,
            "extras": dict(self.extras),
            "notes": [note.to_dict() for note in self.notes],
        }


class Dialect:
    """Base class for every dialect."""

    name: str = ""
    label: str = ""
    aliases: Tuple[str, ...] = ()
    #: Whether the dialect has a seconds field.
    supports_seconds: bool = False
    #: Whether the dialect can pin a timezone.
    supports_timezone: bool = False
    #: Whether the dialect understands ``@macro`` shorthands.
    supports_macros: bool = False

    def render(self, expr: CronExpression, *, tz: Optional[str] = None) -> Conversion:
        raise NotImplementedError

    def parse(self, text: str) -> CronExpression:
        raise NotImplementedError

    # -- helpers -----------------------------------------------------

    @staticmethod
    def _cron_fields(expr: CronExpression) -> str:
        """The five POSIX fields, written out."""
        from ..fields import format_field

        return " ".join(
            format_field(spec)
            for spec in (expr.minute, expr.hour, expr.dom, expr.month, expr.dow)
        )


def time_component(values: Iterable[int], low: int, high: int) -> str:
    """Render a set of values as one systemd time component.

    >>> time_component([0], 0, 59)
    '00'
    >>> time_component([0, 15, 30, 45], 0, 59)
    '0/15'
    >>> time_component(range(24), 0, 23)
    '*'
    """
    ordered = sorted(values)
    if not ordered:
        return "*"
    if len(ordered) == high - low + 1:
        return "*"
    if len(ordered) == 1:
        return f"{ordered[0]:02d}"
    if ordered == list(range(ordered[0], ordered[0] + len(ordered))):
        return f"{ordered[0]:02d}-{ordered[-1]:02d}"
    step = ordered[1] - ordered[0]
    if all(ordered[index + 1] - ordered[index] == step for index in range(len(ordered) - 1)):
        return f"{ordered[0]}/{step}"
    return ",".join(f"{value:02d}" for value in ordered)


def dow_component(values: Iterable[int]) -> str:
    """Render cron day-of-week numbers as systemd day names.

    >>> dow_component([1, 2, 3, 4, 5])
    'Mon..Fri'
    >>> dow_component([0, 6])
    'Sat,Sun'
    """
    ordered = sorted(values)
    if not ordered:
        return "*"
    if len(ordered) == 7:
        return "*"
    groups: List[List[int]] = []
    for value in ordered:
        if groups and value == groups[-1][-1] + 1:
            groups[-1].append(value)
        else:
            groups.append([value])
    parts: List[str] = []
    for group in groups:
        if len(group) == 1:
            parts.append(DOW_NAMES[group[0]])
        else:
            parts.append(f"{DOW_NAMES[group[0]]}..{DOW_NAMES[group[-1]]}")
    return ",".join(parts)


def month_component(values: Iterable[int]) -> str:
    """Render month numbers the way systemd wants them."""
    ordered = sorted(values)
    if len(ordered) == 12:
        return "*"
    return ",".join(f"{value:02d}" for value in ordered)


def dom_component(values: Iterable[int]) -> str:
    """Render day-of-month numbers the way systemd wants them."""
    ordered = sorted(values)
    if len(ordered) == 31:
        return "*"
    return ",".join(f"{value:02d}" for value in ordered)


def dom_dow_note(expr: CronExpression) -> Optional[Note]:
    """Warn when a schedule relies on the OR rule for the two day fields."""
    if expr.day_semantics is not DaySemantics.OR:
        return None
    if not (expr._dom_constrained and expr._dow_constrained):
        return None
    return Note(
        LEVEL_WARNING,
        "day-of-month and day-of-week are both restricted, so cron fires when "
        "EITHER matches (OR). Most people expect AND.",
        "「日」和「星期」同时被限定，cron 的语义是满足任意一个即可（OR），"
        "而多数人以为是要同时满足（AND）。",
    )
