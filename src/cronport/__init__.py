"""cronport -- one schedule, every runtime.

cronport parses a schedule once and then speaks every dialect you need:
plain cron, systemd timers, Kubernetes CronJobs, GitHub Actions, AWS
EventBridge, Quartz and Google Cloud Scheduler.

The library API mirrors the command line::

    >>> from cronport import CronExpression, convert
    >>> schedule = CronExpression.parse("0 9 * * 1-5")
    >>> schedule.next_runs(1, tz="Asia/Shanghai")  # doctest: +SKIP
    [datetime.datetime(2026, 11, 4, 9, 0, tzinfo=...)]
    >>> convert(schedule, "systemd").expression
    'Mon..Fri *-*-* 09:00:00'
"""

from __future__ import annotations

from .dialects import (
    DIALECTS,
    Conversion,
    Dialect,
    convert,
    get_dialect,
    list_dialects,
    parse_in,
)
from .errors import (
    ConversionError,
    CronportError,
    CronSyntaxError,
    NoOccurrenceError,
    UnknownDialectError,
    UnsupportedExpressionError,
)
from .explain import Explanation, explain
from .expr import (
    CronExpression,
    DaySemantics,
    Occurrence,
    ScheduleWindow,
    resolve_timezone,
)
from .lint import Issue, LintContext, Rule, lint
from .notes import LEVEL_ERROR, LEVEL_INFO, LEVEL_WARNING, Note
from .presets import Preset, get_preset, list_presets

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "CronExpression",
    "DaySemantics",
    "Occurrence",
    "ScheduleWindow",
    "Explanation",
    "explain",
    "Conversion",
    "Dialect",
    "DIALECTS",
    "convert",
    "get_dialect",
    "list_dialects",
    "parse_in",
    "Issue",
    "LintContext",
    "Rule",
    "lint",
    "Note",
    "LEVEL_ERROR",
    "LEVEL_WARNING",
    "LEVEL_INFO",
    "Preset",
    "get_preset",
    "list_presets",
    "CronportError",
    "CronSyntaxError",
    "ConversionError",
    "NoOccurrenceError",
    "UnknownDialectError",
    "UnsupportedExpressionError",
    "resolve_timezone",
]
