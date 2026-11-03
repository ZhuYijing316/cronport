"""The dialect registry.

Every scheduler cronport knows about is registered here, so that the CLI can
look them up by name and the Python API can convert between any two of them.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..errors import UnknownDialectError
from ..expr import CronExpression
from .aws_eventbridge import AwsEventBridgeDialect
from .base import (
    LEVEL_ERROR,
    LEVEL_INFO,
    LEVEL_WARNING,
    Conversion,
    Dialect,
    Note,
)
from .cron_like import (
    CronDialect,
    GcpSchedulerDialect,
    GitHubActionsDialect,
    KubernetesDialect,
)
from .quartz import QuartzDialect
from .systemd import SystemdDialect

#: Every dialect, keyed by its canonical name.
DIALECTS: Dict[str, Dialect] = {
    dialect.name: dialect
    for dialect in (
        CronDialect(),
        SystemdDialect(),
        KubernetesDialect(),
        GitHubActionsDialect(),
        AwsEventBridgeDialect(),
        QuartzDialect(),
        GcpSchedulerDialect(),
    )
}

#: Dialects that can be used as a conversion *source*.
SOURCE_DIALECTS: Dict[str, Dialect] = {
    "cron": DIALECTS["cron"],
    "systemd": DIALECTS["systemd"],
    "aws-eventbridge": DIALECTS["aws-eventbridge"],
    "quartz": DIALECTS["quartz"],
}

_ALIASES: Dict[str, str] = {}
for _dialect in DIALECTS.values():
    _ALIASES[_dialect.name] = _dialect.name
    for _alias in _dialect.aliases:
        _ALIASES[_alias] = _dialect.name


def canonical_name(name: str) -> str:
    """Resolve a user supplied dialect name.

    >>> canonical_name("k8s")
    'kubernetes'
    """
    key = name.strip().lower()
    if key in _ALIASES:
        return _ALIASES[key]
    raise UnknownDialectError(
        f"unknown dialect {name!r}",
        f"未知的方言 {name!r}",
        hint="known dialects: " + ", ".join(sorted(DIALECTS)),
        hint_zh="可用方言：" + "、".join(sorted(DIALECTS)),
    )


def get_dialect(name: str) -> Dialect:
    """Look up a dialect by name or alias."""
    return DIALECTS[canonical_name(name)]


def list_dialects() -> List[Dialect]:
    """Every known dialect, in a stable order."""
    return list(DIALECTS.values())


def convert(
    expr: CronExpression,
    target: str,
    *,
    tz: Optional[str] = None,
) -> Conversion:
    """Render ``expr`` for ``target``."""
    return get_dialect(target).render(expr, tz=tz)


def parse_in(dialect: str, text: str) -> CronExpression:
    """Parse ``text`` written in ``dialect``."""
    key = canonical_name(dialect)
    source = SOURCE_DIALECTS.get(key)
    if source is None:
        raise UnknownDialectError(
            f"{key!r} cannot be used as a source dialect",
            f"{key!r} 不能作为转换的源方言",
            hint="source dialects: " + ", ".join(sorted(SOURCE_DIALECTS)),
            hint_zh="可用的源方言：" + "、".join(sorted(SOURCE_DIALECTS)),
        )
    return source.parse(text)


__all__ = [
    "DIALECTS",
    "SOURCE_DIALECTS",
    "LEVEL_ERROR",
    "LEVEL_WARNING",
    "LEVEL_INFO",
    "Conversion",
    "Dialect",
    "Note",
    "canonical_name",
    "convert",
    "get_dialect",
    "list_dialects",
    "parse_in",
]
