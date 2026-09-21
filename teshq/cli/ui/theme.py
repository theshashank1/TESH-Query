"""
TESH-Query — Cinematic CLI Design System.

A psychologically-tuned, award-calibre design language for terminal interfaces.
Every color, icon, and box style is chosen to deliver maximum developer delight
while remaining effortlessly legible for first-time users.

Design principles:
  1.  Layered depth — surface/card/overlay tones create spatial hierarchy.
  2.  Signal color — green = positive, rose = alert, amber = caution. Never ambiguous.
  3.  Gradient feel — consecutive lines use palette shifts to simulate motion.
  4.  Whitespace rhythm — generous padding turns data into storytelling.
  5.  Progressive disclosure — summaries first, details on demand.
"""

import sys
from typing import List, Tuple
from rich import box
from rich.console import Console
from rich.theme import Theme
from rich.text import Text


# ═══════════════════════════════════════════════════════════════════════════════
#  COLOR PALETTE  — "Midnight Aurora" Theme
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    """
    Psychologically-optimized color tokens.

    Research-backed: Sky-blue hues reduce cognitive strain during extended sessions;
    warm accents (amber, rose) trigger urgency only when semantically necessary.
    """

    # ── Brand Primaries ────────────────────────────────────────────────────
    PRIMARY       = "#38BDF8"   # Electric Sky — active, interactive, branded
    PRIMARY_LIGHT = "#7DD3FC"   # Soft Cyan — hover/highlight
    PRIMARY_DARK  = "#0284C7"   # Deep Cerulean — pressed/active state
    PRIMARY_GLOW  = "#BAE6FD"   # Glow ring — ultra-light halo effect

    # ── Accent & Companion ─────────────────────────────────────────────────
    SECONDARY     = "#A78BFA"   # Soft Violet — AI/intellect association
    SECONDARY_DIM = "#7C3AED"   # Deep Violet — secondary emphasis
    ACCENT        = "#F472B6"   # Rose Pink — playful accent, badges
    ACCENT_HOT    = "#EC4899"   # Hot Magenta — call-to-action
    TEAL          = "#2DD4BF"   # Teal — complementary to primary

    # ── Semantic State Colors ──────────────────────────────────────────────
    SUCCESS       = "#34D399"   # Emerald — confirmation, speed, positive
    SUCCESS_DARK  = "#059669"   # Forest — completed state
    WARNING       = "#FBBF24"   # Golden Amber — caution, attention
    WARNING_DARK  = "#D97706"   # Deep Amber
    ERROR         = "#FB7185"   # Rose — non-aggressive alert
    ERROR_DARK    = "#E11D48"   # Crimson Rose — critical
    INFO          = "#22D3EE"   # Crystal Cyan — educational, hint

    # ── Surfaces & Depth Layers ────────────────────────────────────────────
    BG_DEEP       = "#020617"   # Slate 950 — deepest background
    BG_BASE       = "#0F172A"   # Slate 900 — app background
    SURFACE       = "#1E293B"   # Slate 800 — card surface
    SURFACE_HOVER = "#273548"   # Slate 700+ — interactive hover
    OVERLAY       = "#334155"   # Slate 700 — overlay/modal
    BORDER        = "#475569"   # Slate 600 — visible borders
    BORDER_SUBTLE = "#334155"   # Slate 700 — subtle separators
    BORDER_GLOW   = "#38BDF8"   # Primary glow for active borders

    # ── Typography ─────────────────────────────────────────────────────────
    TEXT          = "#F8FAFC"   # Slate 50 — headline, primary text
    TEXT_BODY     = "#E2E8F0"   # Slate 200 — body text
    TEXT_MUTED    = "#CBD5E1"   # Slate 300 — secondary text
    MUTED         = "#94A3B8"   # Slate 400 — labels, meta
    DIM           = "#64748B"   # Slate 500 — timestamps, hints
    GHOST         = "#475569"   # Slate 600 — watermarks, ultra-dim

    # Backward compatibility aliases
    CARD_BG = SURFACE


# ── Gradient Presets (for line-by-line coloring) ──────────────────────────────

GRADIENT_OCEAN: List[str] = [
    "#22D3EE", "#38BDF8", "#60A5FA", "#818CF8", "#A78BFA", "#C084FC",
]

GRADIENT_AURORA: List[str] = [
    "#38BDF8", "#2DD4BF", "#34D399", "#A78BFA", "#F472B6", "#38BDF8",
]

GRADIENT_SUNSET: List[str] = [
    "#F472B6", "#FB923C", "#FBBF24", "#A78BFA", "#818CF8", "#38BDF8",
]

GRADIENT_NEON: List[str] = [
    "#22D3EE", "#2DD4BF", "#34D399", "#38BDF8", "#A78BFA", "#F472B6",
]


def gradient_text(text: str, gradient: List[str]) -> Text:
    """Apply a per-line color gradient to a multi-line string."""
    rich_text = Text()
    lines = text.split("\n")
    for i, line in enumerate(lines):
        color = gradient[i % len(gradient)]
        rich_text.append(f"{line}\n", style=f"bold {color}")
    return rich_text


# ═══════════════════════════════════════════════════════════════════════════════
#  BOX STYLES  — Layered Visual Depth
# ═══════════════════════════════════════════════════════════════════════════════

ROUNDED_BOX = box.ROUNDED
DOUBLE_BOX = box.DOUBLE
HEAVY_BOX = box.HEAVY
MINIMAL_BOX = box.SIMPLE_HEAVY
ASCII_BOX = box.ASCII


# ═══════════════════════════════════════════════════════════════════════════════
#  RICH THEME  — Token-to-Style Mapping
# ═══════════════════════════════════════════════════════════════════════════════

RICH_THEME = Theme({
    "primary":     Colors.PRIMARY,
    "secondary":   Colors.SECONDARY,
    "accent":      Colors.ACCENT,
    "success":     Colors.SUCCESS,
    "warning":     Colors.WARNING,
    "error":       Colors.ERROR,
    "info":        Colors.INFO,
    "muted":       Colors.MUTED,
    "dim":         Colors.DIM,
    "ghost":       Colors.GHOST,
    "card.border": Colors.BORDER,
    "body":        Colors.TEXT_BODY,
})


# ═══════════════════════════════════════════════════════════════════════════════
#  ICONS  — Cinematic Glyphs with Graceful Fallbacks
# ═══════════════════════════════════════════════════════════════════════════════

def _supports_unicode() -> bool:
    """Check if the terminal safely supports UTF-8 icons."""
    try:
        encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        if encoding.lower().startswith("utf"):
            return True
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    except Exception:
        return False


SUPPORTS_UNICODE = _supports_unicode()


class Icons:
    """
    Expressive iconography with automatic ASCII fallbacks.

    Each icon is a static method so callers use ``Icons.check()`` consistently.
    """

    # ── Symbol pairs: (Unicode, ASCII) ─────────────────────────────────────
    _SYMBOLS = {
        "check":       ("✔", "+"),
        "cross":       ("✘", "x"),
        "warn":        ("⚠", "!"),
        "info":        ("ℹ", "i"),
        "sparkle":     ("✦", "*"),
        "sparkles":    ("✧", "~"),
        "bolt":        ("⚡", ">"),
        "rocket":      ("🚀", ">>"),
        "search":      ("⌕", "?"),
        "database":    ("◉", "[DB]"),
        "table":       ("⊞", "[T]"),
        "key":         ("⚿", "[PK]"),
        "link":        ("⇢", "->"),
        "chevron":     ("❯", ">"),
        "chevron_d":   ("❱", ">>"),
        "bullet":      ("•", "*"),
        "dot_green":   ("●", "(o)"),
        "dot_yellow":  ("●", "(!)"),
        "dot_red":     ("●", "(x)"),
        "arrow_r":     ("→", "->"),
        "arrow_d":     ("↓", "v"),
        "clock":       ("◷", "[t]"),
        "token":       ("◈", "#"),
        "cost":        ("◇", "$"),
        "rows":        ("≡", "="),
        "brain":       ("◎", "@"),
        "pulse":       ("◌", "o"),
        "shield":      ("◆", "[S]"),
        "star":        ("★", "*"),
        "gear":        ("⚙", "[G]"),
        "wave":        ("〜", "~"),
    }

    @classmethod
    def _icon(cls, name: str) -> str:
        pair = cls._SYMBOLS.get(name, ("?", "?"))
        return pair[0] if SUPPORTS_UNICODE else pair[1]

    # Convenience accessors — each returns the right glyph for the terminal
    @classmethod
    def check(cls) -> str: return cls._icon("check")
    @classmethod
    def cross(cls) -> str: return cls._icon("cross")
    @classmethod
    def warn(cls) -> str: return cls._icon("warn")
    @classmethod
    def info(cls) -> str: return cls._icon("info")
    @classmethod
    def sparkle(cls) -> str: return cls._icon("sparkle")
    @classmethod
    def sparkles(cls) -> str: return cls._icon("sparkles")
    @classmethod
    def bolt(cls) -> str: return cls._icon("bolt")
    @classmethod
    def rocket(cls) -> str: return cls._icon("rocket")
    @classmethod
    def search(cls) -> str: return cls._icon("search")
    @classmethod
    def database(cls) -> str: return cls._icon("database")
    @classmethod
    def table(cls) -> str: return cls._icon("table")
    @classmethod
    def key(cls) -> str: return cls._icon("key")
    @classmethod
    def link(cls) -> str: return cls._icon("link")
    @classmethod
    def chevron(cls) -> str: return cls._icon("chevron")
    @classmethod
    def chevron_d(cls) -> str: return cls._icon("chevron_d")
    @classmethod
    def bullet(cls) -> str: return cls._icon("bullet")
    @classmethod
    def dot_green(cls) -> str: return cls._icon("dot_green")
    @classmethod
    def dot_yellow(cls) -> str: return cls._icon("dot_yellow")
    @classmethod
    def dot_red(cls) -> str: return cls._icon("dot_red")
    @classmethod
    def arrow_r(cls) -> str: return cls._icon("arrow_r")
    @classmethod
    def arrow_d(cls) -> str: return cls._icon("arrow_d")
    @classmethod
    def clock(cls) -> str: return cls._icon("clock")
    @classmethod
    def token(cls) -> str: return cls._icon("token")
    @classmethod
    def cost(cls) -> str: return cls._icon("cost")
    @classmethod
    def rows(cls) -> str: return cls._icon("rows")
    @classmethod
    def brain(cls) -> str: return cls._icon("brain")
    @classmethod
    def pulse(cls) -> str: return cls._icon("pulse")
    @classmethod
    def shield(cls) -> str: return cls._icon("shield")
    @classmethod
    def star(cls) -> str: return cls._icon("star")
    @classmethod
    def gear(cls) -> str: return cls._icon("gear")
    @classmethod
    def wave(cls) -> str: return cls._icon("wave")


# ═══════════════════════════════════════════════════════════════════════════════
#  VISUAL PRIMITIVES — Reusable micro-components
# ═══════════════════════════════════════════════════════════════════════════════

def badge(label: str, color: str = Colors.PRIMARY) -> str:
    """Inline colored badge/pill for tags."""
    return f"[bold {color} on {Colors.SURFACE}] {label} [/bold {color} on {Colors.SURFACE}]"


def dim_label(label: str, value: str, sep: str = ":") -> str:
    """A dim label followed by a bright value."""
    return f"[{Colors.MUTED}]{label}{sep}[/{Colors.MUTED}] [bold {Colors.TEXT}]{value}[/bold {Colors.TEXT}]"


def progress_bar(fraction: float, width: int = 20, fill_color: str = Colors.PRIMARY, empty_color: str = Colors.GHOST) -> str:
    """Render a single-line progress/percentage bar."""
    filled = int(fraction * width)
    empty = width - filled
    return f"[{fill_color}]{'━' * filled}[/{fill_color}][{empty_color}]{'━' * empty}[/{empty_color}]"


def status_dot(state: str = "ok") -> str:
    """Return a colored status dot based on state."""
    if state == "ok":
        return f"[bold {Colors.SUCCESS}]{Icons.dot_green()}[/bold {Colors.SUCCESS}]"
    elif state == "warn":
        return f"[bold {Colors.WARNING}]{Icons.dot_yellow()}[/bold {Colors.WARNING}]"
    else:
        return f"[bold {Colors.ERROR}]{Icons.dot_red()}[/bold {Colors.ERROR}]"


# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED CONSOLE SINGLETONS
# ═══════════════════════════════════════════════════════════════════════════════

console = Console(theme=RICH_THEME, safe_box=True)
err_console = Console(stderr=True, theme=RICH_THEME, safe_box=True)
