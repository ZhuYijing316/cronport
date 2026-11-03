"""The Quartz dialect.

Quartz is the dialect behind Java schedulers (Spring's ``@Scheduled``,
Quartz itself) and it differs from POSIX cron in three ways that matter:

* it has a **seconds** field,
* it has an optional **year** field,
* it combines day-of-month and day-of-week with **AND** and uses ``?`` for
  "this field does not matter".
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from ..errors import CronSyntaxError
from ..expr import CronExpression, DaySemantics
from ..fields import FieldSpec, format_field
from ..notes import LEVEL_INFO, LEVEL_WARNING, Note
from .base import Conversion, Dialect

class QuartzDialect(Dialect):
    """Quartz cron (6 or 7 fields)."""

    name = "quartz"
    label = "Quartz (Java / Spring)"
    aliases = ("spring", "java", "quartz-cron")
    supports_seconds = True

    def render(self, expr: CronExpression, *, tz: Optional[str] = None) -> Conversion:
        notes: List[Note] = []
        seconds = expr.second.values if expr.second is not None else {0}

        dom_constrained = expr._dom_constrained
        dow_constrained = expr._dow_constrained

        if dom_constrained and dow_constrained:
            # Quartz can only express one of the two, and it ANDs them.
            dom_text = format_field(expr.dom)
            dow_text = format_field(expr.dow)
            notes.append(
                Note(
                    LEVEL_WARNING,
                    "cron fires when day-of-month OR day-of-week matches, but Quartz "
                    "ANDs the two fields. This Quartz expression therefore fires less "
                    f"often than the cron one. To keep the original behaviour, use two "
                    f"triggers: '0 0 {dom_text} * ?' and '0 0 ? * {dow_text}'.",
                    "cron 在「日」或「星期」任一匹配时触发，而 Quartz 要求两者同时满足，"
                    "因此这个 Quartz 表达式的触发次数会少于原 cron。要保持原行为，"
                    f"请使用两个触发器：'0 0 {dom_text} * ?' 与 '0 0 ? * {dow_text}'。",
                )
            )
            dom_out = format_field(expr.dom)
            dow_out = "?"
        elif dow_constrained:
            dom_out = "?"
            dow_out = format_field(expr.dow)
        elif dom_constrained:
            dom_out = format_field(expr.dom)
            dow_out = "?"
        else:
            dom_out = "?"
            dow_out = "?"

        expression = (
            f"{format_field(_spec(seconds))} {format_field(expr.minute)} "
            f"{format_field(expr.hour)} {dom_out} {format_field(expr.month)} {dow_out} *"
        )
        if tz:
            notes.append(
                Note(
                    LEVEL_INFO,
                    f"Quartz uses the timezone of the JVM, so {tz} has to be configured "
                    "on the scheduler itself (for example with TimeZone.setDefault)",
                    f"Quartz 使用 JVM 的时区，{tz} 需要在调度器上单独配置"
                    "（例如调用 TimeZone.setDefault）",
                )
            )
        return Conversion(self.name, expression, notes)

    def parse(self, text: str) -> CronExpression:
        raw = text.strip()
        if not raw:
            raise CronSyntaxError("expression is empty", "表达式为空")
        parts = raw.split()
        if len(parts) not in (6, 7):
            raise CronSyntaxError(
                f"a Quartz expression has 6 or 7 fields, got {len(parts)}",
                f"Quartz 表达式需要 6 或 7 个字段，实际得到 {len(parts)} 个",
                expression=text,
                hint="format: second minute hour day-of-month month day-of-week [year]",
                hint_zh="格式：秒 分 时 日 月 星期 [年]",
            )
        return CronExpression.parse(
            raw,
            dialect="quartz",
            allow_seconds=True,
            day_semantics=DaySemantics.AND,
        )


def _spec(values: Iterable[int]) -> FieldSpec:
    """Build a throwaway FieldSpec so ``format_field`` can be reused."""
    ordered = sorted(values)
    return FieldSpec(
        name="second",
        raw=",".join(str(value) for value in ordered),
        values=frozenset(ordered),
        min_value=0,
        max_value=59,
    )
