"""Terminal rendering.

Two details here are worth more than they look:

* **East Asian characters are twice as wide.**  A table that pads by
  ``len()`` falls apart the moment a Chinese label goes into it, so every
  width calculation goes through :func:`display_width`.
* **Not every terminal is a terminal.**  Colour is switched off automatically
  when the output is piped or ``NO_COLOR`` is set, and the box drawing
  characters fall back to ASCII when the encoding cannot carry them.
"""

from __future__ import annotations

import os
import sys
import unicodedata
from typing import Iterable, List, Optional, Sequence, Tuple

RESET = "\033[0m"

STYLES = {
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "grey": "\033[90m",
    "white": "\033[97m",
}

#: Symbols with an ASCII fallback for terminals that cannot show them.
#: Every fancy glyph here is present in the common monospace fonts; U+2139
#: (INFORMATION SOURCE) is deliberately avoided because DejaVu Sans Mono and
#: several other terminal fonts do not carry it.
SYMBOLS = {
    "clock": ("⏱", "@"),
    "warning": ("⚠", "!"),
    "error": ("✗", "x"),
    "ok": ("✓", "+"),
    "bullet": ("•", "-"),
    "arrow": ("→", "->"),
    "info": ("▪", "i"),
    "dot": ("●", "*"),
}


def display_width(text: str) -> int:
    """How many terminal columns ``text`` occupies.

    >>> display_width("abc")
    3
    >>> display_width("中文")
    4
    """
    width = 0
    for character in text:
        if unicodedata.combining(character):
            continue
        if unicodedata.east_asian_width(character) in ("W", "F"):
            width += 2
        else:
            width += 1
    return width


def truncate(text: str, limit: int) -> str:
    """Shorten ``text`` to ``limit`` columns, adding an ellipsis."""
    if display_width(text) <= limit:
        return text
    if limit <= 1:
        return "…"
    result = ""
    used = 0
    for character in text:
        step = display_width(character)
        if used + step > limit - 1:
            break
        result += character
        used += step
    return result + "…"


def pad(text: str, width: int, align: str = "left") -> str:
    """Pad ``text`` to ``width`` terminal columns."""
    filler = " " * max(0, width - display_width(text))
    if align == "right":
        return filler + text
    if align == "center":
        left = len(filler) // 2
        return " " * left + text + " " * (len(filler) - left)
    return text + filler


class Theme:
    """Colour and glyph handling for one output stream."""

    def __init__(self, color: Optional[bool] = None, ascii_only: Optional[bool] = None) -> None:
        self.color = self._detect_color() if color is None else color
        self.ascii_only = self._detect_ascii() if ascii_only is None else ascii_only

    # -- detection ----------------------------------------------------

    @staticmethod
    def _detect_color() -> bool:
        if os.environ.get("NO_COLOR") is not None:
            return False
        if os.environ.get("FORCE_COLOR"):
            return True
        if os.environ.get("TERM", "") == "dumb":
            return False
        try:
            return sys.stdout.isatty()
        except Exception:  # pragma: no cover - defensive
            return False

    @staticmethod
    def _detect_ascii() -> bool:
        encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
        if not encoding:
            return True
        return "utf" not in encoding

    # -- painting -----------------------------------------------------

    def paint(self, text: str, *styles: str) -> str:
        """Wrap ``text`` in the given ANSI styles."""
        if not self.color or not styles:
            return text
        prefix = "".join(STYLES[style] for style in styles if style in STYLES)
        return f"{prefix}{text}{RESET}"

    def title(self, text: str) -> str:
        return self.paint(text, "bold", "cyan")

    def key(self, text: str) -> str:
        return self.paint(text, "bold")

    def bold(self, text: str) -> str:
        return self.paint(text, "bold")

    def value(self, text: str) -> str:
        return self.paint(text, "green")

    def dim(self, text: str) -> str:
        return self.paint(text, "grey")

    def warn(self, text: str) -> str:
        return self.paint(text, "yellow")

    def error(self, text: str) -> str:
        return self.paint(text, "red")

    def ok(self, text: str) -> str:
        return self.paint(text, "green")

    def accent(self, text: str) -> str:
        return self.paint(text, "magenta")

    def symbol(self, name: str) -> str:
        """The themed symbol for ``name``."""
        fancy, plain = SYMBOLS.get(name, ("*", "*"))
        return plain if self.ascii_only else fancy

    # -- layout -------------------------------------------------------

    def heading(self, text: str, subtitle: str = "") -> str:
        """A section heading with an optional dim subtitle."""
        line = self.title(text)
        if subtitle:
            line = f"{line} {self.dim(subtitle)}"
        return line

    def rule(self, width: int = 60) -> str:
        character = "-" if self.ascii_only else "─"
        return self.dim(character * width)

    def bullets(self, items: Iterable[str], indent: str = "  ") -> List[str]:
        """A bulleted list."""
        marker = self.symbol("bullet")
        return [f"{indent}{self.dim(marker)} {item}" for item in items]

    def table(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[str]],
        aligns: Optional[Sequence[str]] = None,
        indent: str = "",
        max_width: Optional[int] = None,
    ) -> str:
        """Render a table with box drawing characters.

        ``aligns`` accepts ``left``, ``right`` and ``center`` per column.
        """
        if not rows and not headers:
            return ""
        column_count = max(len(headers), *(len(row) for row in rows)) if rows else len(headers)
        if not column_count:
            return ""

        if aligns is None:
            aligns = ["left"] * column_count
        aligns = list(aligns) + ["left"] * (column_count - len(aligns))

        cells: List[List[str]] = []
        for row in rows:
            padded = list(row) + [""] * (column_count - len(row))
            cells.append([str(value) for value in padded])
        head = [str(value) for value in headers] + [""] * (column_count - len(headers))

        widths: List[int] = []
        for index in range(column_count):
            candidates = [display_width(head[index])] + [
                display_width(row[index]) for row in cells
            ]
            widths.append(max(candidates))

        if max_width is not None:
            total = sum(widths) + 3 * column_count + 1
            if total > max_width and column_count > 1:
                overflow = total - max_width
                widest = widths.index(max(widths))
                widths[widest] = max(8, widths[widest] - overflow)

        if self.ascii_only:
            top = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
            mid = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
            bot = top
            tee = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
            left, right, fill = "|", "|", "-"
            tleft, tright, tmid = "+", "+", "+"
        else:
            top = "┌" + "┬".join("─" * (width + 2) for width in widths) + "┐"
            mid = "├" + "┼".join("─" * (width + 2) for width in widths) + "┤"
            bot = "└" + "┴".join("─" * (width + 2) for width in widths) + "┘"
            tee = "├" + "┼".join("─" * (width + 2) for width in widths) + "┤"
            left, right, fill = "│", "│", "─"
            tleft, tright, tmid = "┌", "┐", "┬"

        lines: List[str] = []
        lines.append(indent + top)
        if any(head):
            rendered = [
                f" {pad(head[index], widths[index], aligns[index])} "
                for index in range(column_count)
            ]
            lines.append(indent + left + left.join(rendered) + right)
            lines.append(indent + tee)
        for row in cells:
            rendered = [
                f" {pad(truncate(row[index], widths[index]), widths[index], aligns[index])} "
                for index in range(column_count)
            ]
            lines.append(indent + left + left.join(rendered) + right)
        lines.append(indent + bot)
        return "\n".join(lines)

    def key_values(
        self,
        pairs: Sequence[Tuple[str, str]],
        indent: str = "",
        max_width: Optional[int] = None,
    ) -> str:
        """Render an aligned key/value block."""
        if not pairs:
            return ""
        key_width = max(display_width(key) for key, _ in pairs)
        lines: List[str] = []
        for key, value in pairs:
            lines.append(
                f"{indent}{self.dim(pad(key, key_width))}  {value}"
            )
        return "\n".join(lines)

    def header(self, name: str, expression: str = "") -> str:
        """The small banner at the top of a command's output."""
        text = self.paint(name, "bold", "magenta")
        if expression:
            text = f"{text} {self.dim('·')} {self.value(expression)}"
        return text
