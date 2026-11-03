#!/usr/bin/env python3
"""Render the README demo animation.

The frames are generated from *real* command output: every frame is produced
by running cronport with colour enabled and rendering the result exactly as a
terminal would.  Nothing in the demo is hand written, so it cannot drift away
from what the tool actually does.

Usage::

    python scripts/make_demo.py [--output assets/demo.gif]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# ----------------------------------------------------------------------
# palette
# ------------------------------------------------------------------------

BACKGROUND = (22, 23, 31)
FOREGROUND = (203, 208, 220)

COLORS: Dict[int, Tuple[int, int, int]] = {
    31: (255, 106, 106),  # red
    32: (108, 220, 140),  # green
    33: (240, 200, 100),  # yellow
    34: (120, 160, 255),  # blue
    35: (214, 130, 240),  # magenta
    36: (96, 214, 224),  # cyan
    37: (235, 238, 245),  # white
    90: (118, 126, 145),  # grey
    97: (255, 255, 255),
}

BOLD_BRIGHT = {
    31: (255, 140, 140),
    32: (140, 235, 160),
    33: (250, 215, 130),
    34: (150, 180, 255),
    35: (230, 160, 250),
    36: (130, 230, 240),
    37: (255, 255, 255),
    90: (150, 158, 175),
    97: (255, 255, 255),
}

SGR = re.compile(r"\033\[([0-9;]*)m")


# ----------------------------------------------------------------------
# running the real command
# ----------------------------------------------------------------------


def run_cronport(arguments: Sequence[str]) -> str:
    """Run cronport with colour forced on and return the raw output."""
    environment = dict(os.environ)
    environment["FORCE_COLOR"] = "1"
    environment["PYTHONPATH"] = str(SRC) + os.pathsep + environment.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "cronport", *arguments],
        capture_output=True,
        text=True,
        env=environment,
        cwd=str(ROOT),
    )
    return result.stdout


def build_script() -> List[Tuple[str, str]]:
    """The commands the animation shows, and their real output."""
    return [
        ("cronport explain \"0 9 * * 1-5\"", run_cronport(["explain", "0 9 * * 1-5"])),
        ("cronport convert \"0 9 * * 1-5\"", run_cronport(["convert", "0 9 * * 1-5"])),
        (
            "cronport lint \"0 0 13 * 5\" --target github-actions",
            run_cronport(["lint", "0 0 13 * 5", "--target", "github-actions"]),
        ),
    ]


# ----------------------------------------------------------------------
# ANSI parsing
# ----------------------------------------------------------------------


class Style:
    """The current terminal style."""

    def __init__(self) -> None:
        self.color: Optional[int] = None
        self.bold = False
        self.dim = False

    def copy(self) -> "Style":
        other = Style()
        other.color = self.color
        other.bold = self.bold
        other.dim = self.dim
        return other

    def apply(self, codes: Sequence[int]) -> None:
        for code in codes:
            if code == 0:
                self.color = None
                self.bold = False
                self.dim = False
            elif code == 1:
                self.bold = True
            elif code == 2:
                self.dim = True
            elif code in COLORS:
                self.color = code
            elif code == 39:
                self.color = None

    def rgb(self) -> Tuple[int, int, int]:
        if self.color is None:
            return FOREGROUND
        if self.bold and self.color in BOLD_BRIGHT:
            return BOLD_BRIGHT[self.color]
        return COLORS[self.color]


def parse_line(line: str) -> List[Tuple[str, Style]]:
    """Split one line into ``(text, style)`` segments."""
    segments: List[Tuple[str, Style]] = []
    style = Style()
    position = 0
    for match in SGR.finditer(line):
        if match.start() > position:
            segments.append((line[position : match.start()], style.copy()))
        codes = [int(part) for part in match.group(1).split(";") if part != ""] or [0]
        style.apply(codes)
        position = match.end()
    if position < len(line):
        segments.append((line[position:], style.copy()))
    return segments


def safe_prefix(text: str, length: int) -> str:
    """A prefix of ``text`` that never cuts an escape sequence in half."""
    if length >= len(text):
        return text
    cut = length
    while cut > 0 and "\033" in text[max(0, cut - 20) : cut]:
        start = text.rfind("\033", 0, cut)
        if start == -1:
            break
        end = text.find("m", start)
        if end == -1 or end >= cut:
            cut = start
            continue
        break
    return text[:cut]


# ----------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------


def load_font(size: int):
    from PIL import ImageFont

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        "/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def char_width(character: str, font) -> int:
    """How many cells a character occupies."""
    import unicodedata

    if unicodedata.east_asian_width(character) in ("W", "F"):
        return 2
    return 1


def render_frame(text: str, font, cell_width: int, cell_height: int, padding: int):
    """Render one frame of terminal output into a PIL image."""
    from PIL import Image, ImageDraw

    lines = text.split("\n")
    columns = max((len(_visible(line)) for line in lines), default=1)
    columns = max(columns, 40)
    rows = max(len(lines), 1)

    width = columns * cell_width + padding * 2
    height = rows * cell_height + padding * 2

    image = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)

    for row, line in enumerate(lines):
        column = 0
        for content, style in parse_line(line):
            color = style.rgb()
            if style.dim:
                color = tuple(int(channel * 0.65) for channel in color)
            for character in content:
                if character == "\t":
                    column += 4
                    continue
                x = padding + column * cell_width
                y = padding + row * cell_height
                draw.text((x, y), character, font=font, fill=color)
                column += char_width(character, font)
    return image


def _visible(line: str) -> str:
    return SGR.sub("", line)


# ----------------------------------------------------------------------
# the animation
# ----------------------------------------------------------------------


def build_frames(script: Sequence[Tuple[str, str]], font, cell_width: int, cell_height: int,
                 padding: int) -> List:
    """Every frame of the animation."""
    from PIL import Image

    frames = []
    prompt = "\033[1;35m$\033[0m \033[97m{command}\033[0m\n"

    # A short pause on an empty screen before anything happens.
    blank = Image.new("RGB", (10, 10), BACKGROUND)
    for _ in range(8):
        frames.append((blank, 120))

    for command, output in script:
        command_text = prompt.format(command=command)
        # Type the command out.
        for length in range(0, len(command_text) + 1, 3):
            frames.append(
                (
                    render_frame(
                        safe_prefix(command_text, length),
                        font,
                        cell_width,
                        cell_height,
                        padding,
                    ),
                    28,
                )
            )
        # Then reveal the output line by line.
        full = command_text + output
        for index, line in enumerate(output.split("\n")):
            visible = command_text + "\n".join(output.split("\n")[: index + 1])
            frames.append(
                (
                    render_frame(visible, font, cell_width, cell_height, padding),
                    320 if index == len(output.split("\n")) - 1 else 40,
                )
            )
        del full

    return frames


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(ROOT / "assets" / "demo.gif"),
        help="where to write the animation",
    )
    parser.add_argument("--font-size", type=int, default=17)
    parser.add_argument("--columns", type=int, default=96)
    arguments = parser.parse_args()

    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        print("Pillow is needed to render the demo: pip install pillow", file=sys.stderr)
        return 1

    font = load_font(arguments.font_size)
    cell_width = int(round(font.getlength("M")))
    cell_height = int(round(font.getlength("M") * 1.55))

    script = build_script()
    frames = build_frames(script, font, cell_width, cell_height, padding=16)

    # Every frame is the same size, so pad the short ones.
    width = max(frame.width for frame, _ in frames)
    height = max(frame.height for frame, _ in frames)
    padded = []
    for frame, duration in frames:
        if frame.size != (width, height):
            canvas = Image.new("RGB", (width, height), BACKGROUND)
            canvas.paste(frame, (0, 0))
            frame = canvas
        padded.append((frame, duration))

    output_path = Path(arguments.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    padded[0][0].save(
        output_path,
        save_all=True,
        append_images=[frame for frame, _ in padded[1:]],
        duration=[duration for _, duration in padded],
        loop=0,
        optimize=True,
    )
    size_kb = output_path.stat().st_size / 1024
    print(f"wrote {output_path} ({len(padded)} frames, {size_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
