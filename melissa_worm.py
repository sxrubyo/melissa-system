"""melissa_worm.py — Animated ASCII worm for terminal."""
from __future__ import annotations

import math
import sys
import time


SEGMENTS = ["◉", "█", "▓", "▒", "░", "·"]
PURPLE = "\033[38;5;141m"
DIM = "\033[2m"
R = "\033[0m"


def boot_sequence(duration: float = 2.0):
    """
    Animated worm crawls in, MELISSA appears letter by letter.
    Only runs on real TTY. Graceful skip otherwise.
    """
    if not sys.stdout.isatty():
        return

    frames = int(duration / 0.04)
    width = 60

    try:
        sys.stdout.write("\033[?25l")  # hide cursor
        for f in range(frames):
            t = f / frames
            sys.stdout.write("\033[H\033[J")  # clear

            # Worm position (sinusoidal crawl from right to left)
            worm_x = int((1.0 - t) * width * 0.7) + 2
            worm_y = int(2 + math.sin(t * math.pi * 3) * 1.2)

            # Canvas
            canvas = [[" "] * width for _ in range(7)]

            # Draw worm body
            for i, seg in enumerate(SEGMENTS[:5]):
                sx = worm_x + i * 2
                sy = min(6, max(0, worm_y + int(math.sin((t * 6) - i * 0.5) * 0.8)))
                if 0 <= sx < width and 0 <= sy < 7:
                    canvas[sy][sx] = seg

            # MELISSA text types in progressively
            word = "MELISSA"
            chars_shown = int(t * 2.5 * len(word))
            for i, ch in enumerate(word[:min(chars_shown, len(word))]):
                cx = 6 + i * 4
                if cx < width:
                    canvas[5][cx] = ch

            # Render
            sys.stdout.write("\n")
            for row in canvas:
                sys.stdout.write(f"  {PURPLE}{''.join(row)}{R}\n")
            sys.stdout.flush()
            time.sleep(0.04)

    except (KeyboardInterrupt, BrokenPipeError):
        pass
    finally:
        sys.stdout.write("\033[?25h")  # show cursor
        sys.stdout.write("\033[H\033[J")  # clear for real content


def crawl_spinner(text: str, duration: float = 1.5):
    """Single-line crawling worm spinner for loading states."""
    if not sys.stdout.isatty():
        sys.stdout.write(f"  {text}\n")
        return

    frames = int(duration / 0.06)
    try:
        sys.stdout.write("\033[?25l")
        for f in range(frames):
            t = f / frames
            x = int(abs(math.sin(t * math.pi * 2)) * 12)
            worm = "".join(SEGMENTS[:4])
            sys.stdout.write(f"\033[2K\r  {' ' * x}{PURPLE}{worm}{R} {DIM}{text}{R}")
            sys.stdout.flush()
            time.sleep(0.06)
        sys.stdout.write(f"\033[2K\r")
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    finally:
        sys.stdout.write("\033[?25h")
