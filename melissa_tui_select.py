"""melissa_tui_select.py — Arrow-key interactive selection menu (Nova-style)."""
from __future__ import annotations

import os
import sys
import shutil
import select as _select
from typing import List, Optional

IS_WINDOWS = sys.platform.startswith("win")
if not IS_WINDOWS:
    import termios
    import tty

# Brand colors
PURPLE = "\033[38;5;141m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[32m"


def is_tty() -> bool:
    try:
        return bool(sys.stdin.isatty()) and bool(sys.stdout.isatty())
    except Exception:
        return False


def _term_width() -> int:
    return shutil.get_terminal_size((80, 24)).columns


def select_menu(
    options: List[str],
    *,
    title: str = "",
    descriptions: Optional[List[str]] = None,
    default: int = 0,
) -> int:
    """Interactive menu with arrow key navigation. Returns selected index."""
    if not options:
        return 0
    if not is_tty():
        return _fallback(options, title=title, default=default)

    descriptions = descriptions or []
    current = max(0, min(default, len(options) - 1))
    line_count = 0

    def draw(first=False):
        nonlocal line_count
        out = []
        if not first and line_count:
            out.append(f"\033[{line_count}F")
            for _ in range(line_count):
                out.append("\033[2K\033[1E")
            out.append(f"\033[{line_count}F")

        lc = 0
        if title:
            out.append(f"\n  {PURPLE}{BOLD}{title}{RESET}\n")
            lc += 2

        for i, opt in enumerate(options):
            if i == current:
                out.append(f"  {PURPLE}▸ {opt}{RESET}\n")
            else:
                out.append(f"    {DIM}{opt}{RESET}\n")
            lc += 1
            if i < len(descriptions) and descriptions[i]:
                out.append(f"      {DIM}{descriptions[i][:60]}{RESET}\n")
                lc += 1

        out.append(f"\n  {DIM}↑/↓ mover · Enter confirmar{RESET}\n")
        lc += 2
        line_count = lc
        sys.stdout.write("".join(out))
        sys.stdout.flush()

    def read_key():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setraw(fd)
        try:
            ch = os.read(fd, 1)
            if ch in (b"\r", b"\n"):
                termios.tcflush(fd, termios.TCIFLUSH)
                return "ENTER"
            if ch == b"\x03":
                return "CTRL_C"
            if ch == b"\x1b":
                ready, _, _ = _select.select([fd], [], [], 0.05)
                if not ready:
                    return "ESC"
                ch2 = os.read(fd, 1)
                if ch2 == b"[":
                    ready2, _, _ = _select.select([fd], [], [], 0.05)
                    if not ready2:
                        return "["
                    ch3 = os.read(fd, 1)
                    if ch3 == b"A": return "UP"
                    if ch3 == b"B": return "DOWN"
                return ""
            return ch.decode(errors="ignore")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    draw(first=True)
    while True:
        key = read_key()
        if key == "ENTER":
            sys.stdout.write("\n")
            return current
        if key == "CTRL_C":
            sys.stdout.write("\n")
            raise KeyboardInterrupt
        if key == "UP" and current > 0:
            current -= 1; draw()
        elif key == "DOWN" and current < len(options) - 1:
            current += 1; draw()
        elif key.isdigit():
            idx = int(key) - 1
            if 0 <= idx < len(options):
                current = idx; draw()


def _fallback(options, title="", default=0):
    if title:
        print(f"\n  {title}")
    for i, opt in enumerate(options, 1):
        marker = "▸" if i - 1 == default else " "
        print(f"  {marker} {i}. {opt}")
    try:
        ans = input("\n  → ")
    except (EOFError, KeyboardInterrupt):
        return default
    if ans.isdigit() and 0 < int(ans) <= len(options):
        return int(ans) - 1
    return default


def confirm(text: str, default: bool = True) -> bool:
    """Y/N as arrow-key selector (never disappears)."""
    if not is_tty():
        try:
            ans = input(f"  {text} (y/n) ")
            return ans.lower() in ("y", "yes", "s", "si", "sí", "")
        except: return default

    options = ["Yes", "No"] if default else ["No", "Yes"]
    idx = select_menu(options, title=text, default=0)
    if default:
        return idx == 0
    else:
        return idx == 1


def text_input(label: str, default: str = "", required: bool = True) -> str:
    """Text input that stays visible."""
    suffix = f" {DIM}[{default}]{RESET}" if default else ""
    while True:
        try:
            sys.stdout.write(f"\n  {PURPLE}▸{RESET} {label}{suffix}: ")
            sys.stdout.flush()
            val = sys.stdin.readline().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return default
        if val:
            return val
        if default:
            return default
        if not required:
            return ""
        sys.stdout.write(f"    {DIM}(required){RESET}\n")
        sys.stdout.flush()
