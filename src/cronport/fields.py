"""Parsing of a single cron field.

A cron field is a comma separated list of *terms*.  Each term is one of:

===========================  ==============================================
``*``                        every value in the field's range
``*/S``                      every value in the range, stepping by ``S``
``N``                        the single value ``N``
``N-M``                      the inclusive range ``N``..``M``
``N-M/S``                    the range ``N``..``M``, stepping by ``S``
``N/S``                      ``N``..end of range, stepping by ``S``
===========================  ==============================================

Month and weekday fields additionally accept three letter names
(``jan``..``dec``, ``sun``..``sat``) in place of numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Tuple

from .errors import CronSyntaxError

MONTH_ALIASES: Dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

DOW_ALIASES: Dict[str, int] = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}

_NAME_TOKEN = re.compile(r"[A-Za-z]+")


@dataclass(frozen=True)
class FieldSpec:
    """A parsed cron field."""

    name: str
    raw: str
    values: FrozenSet[int]
    min_value: int
    max_value: int
    is_question: bool = False

    @property
    def is_star(self) -> bool:
        """``True`` when the field was written as a literal ``*``.

        This distinction matters: Vixie cron decides between "day-of-month OR
        day-of-week" and "day-of-month AND day-of-week" purely on whether one
        of the two fields is a literal ``*``.
        """
        return self.raw.strip() == "*"

    @property
    def unconstrained(self) -> bool:
        """``True`` when the field places no constraint at all.

        ``*`` and Quartz' ``?`` are both unconstrained.
        """
        return self.is_star or self.is_question

    @property
    def covers_entire_range(self) -> bool:
        """``True`` when every value of the field's range is present."""
        return len(self.values) == self.max_value - self.min_value + 1

    @property
    def is_single(self) -> bool:
        return len(self.values) == 1

    def sorted_values(self) -> List[int]:
        return sorted(self.values)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "raw": self.raw,
            "values": self.sorted_values(),
            "min": self.min_value,
            "max": self.max_value,
        }


def _replace_names(term: str, aliases: Dict[str, int], field: str) -> str:
    """Replace three letter month/day names with their numeric value."""

    def _sub(match: re.Match[str]) -> str:
        token = match.group(0)
        if len(token) != 3:
            raise CronSyntaxError(
                f"invalid {field} name {token!r}: names must be exactly three letters",
                f"{field} 字段的名称 {token!r} 无效：名称必须恰好是三个字母",
                field=field,
                hint="try " + ", ".join(sorted(aliases)),
                hint_zh="例如 " + ", ".join(sorted(aliases)),
            )
        key = token.lower()
        if key not in aliases:
            raise CronSyntaxError(
                f"unknown {field} name {token!r}",
                f"未知的 {field} 名称 {token!r}",
                field=field,
                hint="valid names: " + ", ".join(sorted(aliases)),
                hint_zh="可用名称：" + "、".join(sorted(aliases)),
            )
        return str(aliases[key])

    return _NAME_TOKEN.sub(_sub, term)


def _parse_term(
    term: str,
    field: str,
    low: int,
    high: int,
    aliases: Optional[Dict[str, int]],
    expression: str,
) -> FrozenSet[int]:
    """Expand one comma separated term into the set of values it selects."""
    if aliases:
        term = _replace_names(term, aliases, field)

    if not term:
        raise CronSyntaxError(
            f"empty term in {field} field",
            f"{field} 字段中存在空项",
            expression=expression,
            field=field,
        )

    step = 1
    has_step = False
    base = term
    if "/" in term:
        base, _, step_text = term.partition("/")
        has_step = True
        if not step_text.isdigit():
            raise CronSyntaxError(
                f"invalid step {step_text!r} in {field} field: step must be a positive integer",
                f"{field} 字段中的步长 {step_text!r} 无效：步长必须是正整数",
                expression=expression,
                field=field,
            )
        step = int(step_text)
        if step == 0:
            raise CronSyntaxError(
                f"step value must be greater than 0 in {field} field",
                f"{field} 字段中的步长必须大于 0",
                expression=expression,
                field=field,
            )

    if base == "*":
        start, end = low, high
    elif "-" in base:
        start_text, _, end_text = base.partition("-")
        if not (start_text.isdigit() and end_text.isdigit()):
            raise CronSyntaxError(
                f"invalid range {base!r} in {field} field",
                f"{field} 字段中的范围 {base!r} 无效",
                expression=expression,
                field=field,
            )
        start, end = int(start_text), int(end_text)
        if end < start:
            raise CronSyntaxError(
                f"range end {end} is before range start {start} in {field} field",
                f"{field} 字段中范围的结束值 {end} 小于起始值 {start}",
                expression=expression,
                field=field,
                hint="cron ranges never wrap around",
                hint_zh="cron 的范围不支持首尾相接",
            )
    elif base.isdigit():
        start = end = int(base)
        if has_step:
            # Vixie extension: ``5/15`` means 5, 20, 35, 50 (up to the end).
            end = high
    else:
        raise CronSyntaxError(
            f"invalid value {base!r} in {field} field",
            f"{field} 字段中的值 {base!r} 无效",
            expression=expression,
            field=field,
        )

    for value in (start, end):
        if not (low <= value <= high):
            raise CronSyntaxError(
                f"value {value} out of range ({low}-{high}) in {field} field",
                f"{field} 字段中的值 {value} 超出范围（{low}-{high}）",
                expression=expression,
                field=field,
            )

    values = set()
    current = start
    while current <= end:
        values.add(current)
        current += step
    return frozenset(values)


def parse_field(
    raw: str,
    name: str,
    low: int,
    high: int,
    aliases: Optional[Dict[str, int]] = None,
    *,
    allow_question: bool = False,
    expression: str = "",
) -> FieldSpec:
    """Parse one cron field into a :class:`FieldSpec`.

    Parameters
    ----------
    raw:
        The textual field, for example ``"1-5"`` or ``"*/15"``.
    name:
        Human readable field name used in error messages (``"minute"`` ...).
    low, high:
        Inclusive bounds of the field.
    aliases:
        Optional mapping of three letter names to numbers.
    allow_question:
        Whether Quartz' ``?`` placeholder is accepted.
    """
    text = raw.strip()
    if allow_question and text == "?":
        return FieldSpec(
            name=name,
            raw=text,
            values=frozenset(),
            min_value=low,
            max_value=high,
            is_question=True,
        )

    if not text:
        raise CronSyntaxError(
            f"{name} field is empty",
            f"{name} 字段为空",
            expression=expression,
            field=name,
        )

    values: set = set()
    for term in text.split(","):
        values |= _parse_term(term, name, low, high, aliases, expression)

    return FieldSpec(
        name=name,
        raw=text,
        values=frozenset(values),
        min_value=low,
        max_value=high,
    )


def compress(values: Iterable[int]) -> str:
    """Render a set of values back into the shortest comma separated form.

    >>> compress({0, 15, 30, 45})
    '0,15,30,45'
    >>> compress({1, 2, 3, 4, 5, 6, 7})
    '1-7'
    """
    ordered = sorted(values)
    if not ordered:
        return ""
    parts: List[str] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value == previous + 1:
            previous = value
            continue
        parts.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = value
    parts.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(parts)


def format_field(spec: FieldSpec) -> str:
    """Render a field the way cron itself would write it.

    Only a field that was *written* as ``*`` is rendered back as ``*``.  A
    field written as ``1-31`` keeps its explicit form, because Vixie cron
    decides between "day-of-month OR day-of-week" and "day-of-month AND
    day-of-week" on exactly that distinction.
    """
    if spec.is_question:
        return "?"
    if spec.is_star:
        return "*"
    return compress(spec.values)


def split_terms(raw: str) -> Tuple[str, ...]:
    """Split a field into its comma separated terms."""
    return tuple(part for part in raw.split(","))
