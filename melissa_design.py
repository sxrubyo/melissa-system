"""melissa_design.py — Single source of truth for all visual elements."""
from __future__ import annotations

COLORS = {
    "primary": "#b48ead",
    "secondary": "#81a1c1",
    "success": "#a3be8c",
    "warning": "#ebcb8b",
    "error": "#bf616a",
    "dim": "#4c566a",
    "text": "#d8dee9",
}

LOGO_FULL = """\
[#b48ead]  ███╗   ███╗███████╗██╗     ██╗███████╗███████╗ █████╗
  ████╗ ████║██╔════╝██║     ██║██╔════╝██╔════╝██╔══██╗
  ██╔████╔██║█████╗  ██║     ██║███████╗███████╗███████║
  ██║╚██╔╝██║██╔══╝  ██║     ██║╚════██║╚════██║██╔══██║
  ██║ ╚═╝ ██║███████╗███████╗██║███████║███████║██║  ██║
  ╚═╝     ╚═╝╚══════╝╚══════╝╚═╝╚══════╝╚══════╝╚═╝  ╚═╝[/#b48ead]"""

WORM_RESTING = """\
[#b48ead]◉[/#b48ead][#9b7ea8]█▓▒░[/#9b7ea8]╮
       ╰─╯"""

WORM_INLINE = "[#b48ead]◉[/#b48ead][dim]▓▒░[/dim]"

SEP = "[dim]─────────────────────────────────────────────────────[/dim]"

ICON_ONLINE = "[#a3be8c]●[/#a3be8c]"
ICON_OFFLINE = "[#bf616a]○[/#bf616a]"
ICON_WARN = "[#ebcb8b]◐[/#ebcb8b]"
ICON_OK = "[#a3be8c]✓[/#a3be8c]"
ICON_ERR = "[#bf616a]✗[/#bf616a]"
ICON_BRAND = "[#b48ead]✦[/#b48ead]"
