"""Exception hierarchy for :mod:`cronport`.

Every error carries both an English and a Chinese message so that the CLI can
answer in whichever language the user asked for, without the translation
being scattered across the code base.
"""

from __future__ import annotations

from typing import List


class CronportError(Exception):
    """Base class for every error raised by cronport."""

    def __init__(self, message: str, zh: str = "", hint: str = "", hint_zh: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.zh = zh or message
        self.hint = hint
        self.hint_zh = hint_zh or hint

    def localized(self, lang: str = "en") -> str:
        """Return the message in ``lang`` (``en`` or ``zh``)."""
        if lang.startswith("zh"):
            text = self.zh
            hint = self.hint_zh
        else:
            text = self.message
            hint = self.hint
        if hint:
            return f"{text}\n  hint: {hint}"
        return text


class CronSyntaxError(CronportError):
    """Raised when an expression cannot be parsed."""

    def __init__(
        self,
        message: str,
        zh: str = "",
        *,
        expression: str = "",
        field: str = "",
        hint: str = "",
        hint_zh: str = "",
    ) -> None:
        super().__init__(message, zh, hint, hint_zh)
        self.expression = expression
        self.field = field

    def localized(self, lang: str = "en") -> str:
        parts: List[str] = []
        if self.expression:
            parts.append(f'"{self.expression}"')
        if self.field:
            parts.append(f"field: {self.field}")
        head = " ".join(parts)
        body = super().localized(lang)
        return f"{head}\n  {body}" if head else body


class UnsupportedExpressionError(CronportError):
    """Raised when an expression is valid but cannot be represented in a target."""


class NoOccurrenceError(CronportError):
    """Raised when a schedule never fires within the supported horizon."""


class UnknownDialectError(CronportError):
    """Raised when a dialect name is not recognised."""


class ConversionError(CronportError):
    """Raised when a conversion between two dialects is not possible."""
