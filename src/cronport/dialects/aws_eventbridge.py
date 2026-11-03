"""The AWS EventBridge dialect.

EventBridge rules and EventBridge Scheduler jobs take a Quartz style
``cron(...)`` expression with six fields::

    cron(0 9 ? * 1-5 *)

Two rules are worth remembering:

* one of the two day fields **must** be ``?`` -- AWS rejects an expression
  where both are given, and
* there is no seconds field.
"""

from __future__ import annotations

from typing import List, Optional

from ..errors import CronSyntaxError
from ..expr import CronExpression, DaySemantics
from ..fields import format_field
from .base import LEVEL_ERROR, LEVEL_INFO, LEVEL_WARNING, Conversion, Dialect, Note


class AwsEventBridgeDialect(Dialect):
    """AWS EventBridge / EventBridge Scheduler."""

    name = "aws-eventbridge"
    label = "AWS EventBridge rule"
    aliases = ("aws", "eventbridge", "event-bridge", "aws-scheduler")
    supports_timezone = True

    def render(self, expr: CronExpression, *, tz: Optional[str] = None) -> Conversion:
        notes: List[Note] = []
        dom_constrained = expr._dom_constrained
        dow_constrained = expr._dow_constrained

        if expr.has_seconds:
            notes.append(
                Note(
                    LEVEL_WARNING,
                    "EventBridge has no seconds field; the seconds part was dropped",
                    "EventBridge 没有秒字段，秒部分已被丢弃",
                )
            )

        if dom_constrained and dow_constrained:
            dom_text = format_field(expr.dom)
            dow_text = format_field(expr.dow)
            dom_out = dom_text
            dow_out = "?"
            notes.append(
                Note(
                    LEVEL_ERROR,
                    "cron fires when day-of-month OR day-of-week matches, but EventBridge "
                    "requires one of the two fields to be '?' and never ORs them. You need "
                    f"two rules to keep the original behaviour: 'cron({dom_text} ... ?)' "
                    f"and 'cron(... ? ... {dow_text})'.",
                    "cron 在「日」或「星期」任一匹配时触发，但 EventBridge 要求两个字段中"
                    f"必须有一个是 '?'，且不会按「或」合并。要保持原行为需要两条规则："
                    f"'cron({dom_text} ... ?)' 与 'cron(... ? ... {dow_text})'。",
                )
            )
        elif dow_constrained:
            dom_out = "?"
            dow_out = format_field(expr.dow)
        elif dom_constrained:
            dom_out = format_field(expr.dom)
            dow_out = "?"
        else:
            dom_out = "*"
            dow_out = "?"

        expression = (
            f"cron({format_field(expr.minute)} {format_field(expr.hour)} {dom_out} "
            f"{format_field(expr.month)} {dow_out} *)"
        )

        if tz:
            notes.append(
                Note(
                    LEVEL_INFO,
                    f"EventBridge Scheduler can pin the timezone with the scheduleExpressionTimezone "
                    f"field; EventBridge rules themselves always run in UTC ({tz} needs that field)",
                    f"EventBridge Scheduler 可以用 scheduleExpressionTimezone 字段指定时区；"
                    f"EventBridge 规则本身固定使用 UTC（{tz} 需要借助该字段）",
                )
            )
        return Conversion(self.name, expression, notes)

    def parse(self, text: str) -> CronExpression:
        raw = text.strip()
        if not raw:
            raise CronSyntaxError("expression is empty", "表达式为空")
        if raw.startswith("cron(") and raw.endswith(")"):
            raw = raw[5:-1].strip()
        parts = raw.split()
        if len(parts) == 6:
            minute_raw, hour_raw, dom_raw, month_raw, dow_raw, year_raw = parts
        elif len(parts) == 5:
            minute_raw, hour_raw, dom_raw, month_raw, dow_raw = parts
            year_raw = "*"
        else:
            raise CronSyntaxError(
                f"an EventBridge expression has 6 fields, got {len(parts)}",
                f"EventBridge 表达式需要 6 个字段，实际得到 {len(parts)} 个",
                expression=text,
                hint="format: cron(minute hour day-of-month month day-of-week year)",
                hint_zh="格式：cron(分 时 日 月 星期 年)",
            )
        if year_raw != "*":
            raise CronSyntaxError(
                "cronport cannot convert a pinned year into a portable schedule",
                "cronport 无法把固定年份转换成通用调度",
                expression=text,
            )
        # '?' means "no specific value"; in cron the closest equivalent is '*'.
        dom_text = "*" if dom_raw == "?" else dom_raw
        dow_text = "*" if dow_raw == "?" else dow_raw
        cron_text = f"{minute_raw} {hour_raw} {dom_text} {month_raw} {dow_text}"
        return CronExpression.parse(cron_text, dialect="cron")
