"""Notes attached to a conversion or a parse.

A *note* is something the user should know that is not fatal: a field that
had to be dropped, a timezone the target cannot express, a schedule that has
to be split across two rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

LEVEL_ERROR = "error"
LEVEL_WARNING = "warning"
LEVEL_INFO = "info"


@dataclass(frozen=True)
class Note:
    """Something the user should know about a conversion."""

    level: str
    message: str
    message_zh: str = ""

    def localized(self, lang: str = "en") -> str:
        """The note in the requested language."""
        if lang.startswith("zh") and self.message_zh:
            return self.message_zh
        return self.message

    def to_dict(self) -> Dict[str, str]:
        return {
            "level": self.level,
            "message": self.message,
            "message_zh": self.message_zh,
        }
