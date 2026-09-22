"""
TESH-Query — "Obsidian Instrument" Design System.

A precision-focused design language for terminal interfaces.
Every color, symbol, and spacing decision communicates state —
nothing is decorative.

Design tenets:
  1.  Information first, decoration never
  2.  4-layer surface depth for spatial hierarchy
  3.  5-tier text hierarchy for scanability
  4.  Semantic color only — green/red/amber/cyan mean one thing each
  5.  Symbols carry meaning; color reinforces but never replaces
  6.  Progressive disclosure — summaries first, details on demand
"""

import os
import sys
from typing import List
from rich import box
from rich.console import Console
from rich.theme import Theme
from rich.text import Text


# ═══════════════════════════════════════════════════════════════════════════════
#  COLOR PALETTE — "Obsidian Instrument"
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    """
    Precision color tokens.

    Muted, restrained palette designed for extended sessions.
    Indigo primary conveys intelligence and precision.
    Semantic colors are unambiguous.
    """

    # ── Surfaces (4-layer depth) ──────────────────────────────────────────
    BG_VOID      = "#0A0A0F"   # Deepest — behind everything
    BG_BASE      = "#12121A"   # App canvas
    SURFACE_1    = "#1A1A25"   # Card / panel surface
    SURFACE_2    = "#222230"   # Elevated (hover, active)
    SURFACE_3    = "#2A2A38"   # Overlay, modal

    # ── Borders (3-tier) ──────────────────────────────────────────────────
    BORDER_NONE    = "#1A1A25"   # Invisible (same as surface)
    BORDER_SUBTLE  = "#2A2A38"   # Subtle separator
    BORDER_DEFAULT = "#3A3A48"   # Standard visible border
    BORDER_FOCUS   = "#6366F1"   # Focused / active element

    # ── Brand — Indigo (intelligence, precision) ──────────────────────────
    PRIMARY        = "#6366F1"   # Indigo 500 — interactive
    PRIMARY_HOVER  = "#818CF8"   # Indigo 400 — hover / highlight
    PRIMARY_MUTED  = "#4338CA"   # Indigo 700 — subtle emphasis
    PRIMARY_GLOW   = "#A5B4FC"   # Indigo 300 — glow ring (rare)

    # ── Semantic State ────────────────────────────────────────────────────
    SUCCESS     = "#10B981"   # Emerald 500 — confirmed, fast, positive
    SUCCESS_DIM = "#059669"   # Emerald 600 — completed state
    WARNING     = "#F59E0B"   # Amber 500 — caution, attention
    WARNING_DIM = "#D97706"   # Amber 600 — deep caution
    ERROR       = "#EF4444"   # Red 500 — failure, alert
    ERROR_DIM   = "#DC2626"   # Red 600 — critical
    INFO        = "#06B6D4"   # Cyan 500 — educational, hint

    # ── Special Accents ───────────────────────────────────────────────────
    AI_ACCENT   = "#A78BFA"   # Violet 400 — AI responses
    DB_ACCENT   = "#2DD4BF"   # Teal 400 — database context
    SQL_ACCENT  = "#38BDF8"   # Sky 400 — SQL syntax emphasis

    # ── Text (5-tier hierarchy) ───────────────────────────────────────────
    TEXT_PRIMARY   = "#F1F1F6"   # Headlines, important content
    TEXT_SECONDARY = "#C8C8D4"   # Body text
    TEXT_TERTIARY  = "#8888A0"   # Descriptions, labels
    TEXT_MUTED     = "#5E5E78"   # Timestamps, metadata
    TEXT_GHOST     = "#3A3A50"   # Watermarks, disabled, ultra-dim

    # ── Backward-compatibility aliases ────────────────────────────────────
    # These map old token names to new palette values so existing code
    # that hasn't been migrated yet keeps working.
    PRIMARY_LIGHT = PRIMARY_HOVER
    PRIMARY_DARK  = PRIMARY_MUTED
    SECONDARY     = AI_ACCENT
    SECONDARY_DIM = "#7C3AED"
    ACCENT        = "#F472B6"
    ACCENT_HOT    = "#EC4899"
    TEAL          = DB_ACCENT
    SUCCESS_DARK  = SUCCESS_DIM
    WARNING_DARK  = WARNING_DIM
    ERROR_DARK    = ERROR_DIM
    BG_DEEP       = BG_VOID
    BG_BASE_OLD   = BG_BASE
    SURFACE       = SURFACE_1
    SURFACE_HOVER = SURFACE_2
    OVERLAY       = SURFACE_3
    BORDER        = BORDER_DEFAULT
    BORDER_GLOW   = BORDER_FOCUS
    TEXT          = TEXT_PRIMARY
    TEXT_BODY     = TEXT_SECONDARY
    TEXT_MUTED_OLD = TEXT_TERTIARY
    MUTED         = TEXT_TERTIARY
    DIM           = TEXT_MUTED
    GHOST         = TEXT_GHOST
    CARD_BG       = SURFACE_1


# ═══════════════════════════════════════════════════════════════════════════════
#  TYPOGRAPHY SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class Typography:
    """Semantic typography tokens for Rich markup."""
    HEADLINE  = "bold"            # Panel titles, prompts
    BODY      = ""                # Primary content
    CAPTION   = "dim"             # Metadata, timestamps
    OVERLINE  = "dim bold"        # Section labels (DATABASE, AI ENGINE)
    CODE      = "bold"            # SQL keywords, commands
    EMPHASIS  = "italic"          # Subtle emphasis


# ═══════════════════════════════════════════════════════════════════════════════
#  SPACING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class Spacing:
    """Padding tuples (vertical, horizontal) for Rich panels."""
    NONE     = (0, 0)
    COMPACT  = (0, 1)
    NORMAL   = (0, 2)
    RELAXED  = (1, 2)
    GENEROUS = (1, 3)


# ═══════════════════════════════════════════════════════════════════════════════
#  ICONS — Functional Symbols with Graceful Fallbacks
# ═══════════════════════════════════════════════════════════════════════════════

def _supports_unicode() -> bool:
    """Check if the terminal safely supports UTF-8 symbols."""
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
    Functional iconography — every symbol communicates state.

    No decorative emoji. Each icon has a semantic purpose and an
    ASCII fallback for compatibility.
    """

    _SYMBOLS = {
        # ── Prompt & Navigation ───────────────────────────────────────
        "prompt":     ("›", ">"),
        "arrow":      ("→", "->"),
        "arrow_d":    ("↓", "v"),
        "expand":     ("▸", ">"),
        "collapse":   ("▾", "v"),
        "chevron":    ("›", ">"),
        "chevron_d":  ("»", ">>"),
        "bullet":     ("·", "*"),

        # ── Status ────────────────────────────────────────────────────
        "check":      ("✓", "+"),
        "cross":      ("✗", "x"),
        "warn":       ("!", "!"),
        "info":       ("i", "i"),
        "dot_filled": ("●", "(*)"),
        "dot_empty":  ("○", "( )"),
        "dot_pulse":  ("◦", "( )"),
        "dot_ai":     ("◎", "(@)"),

        # ── Block & Structure ─────────────────────────────────────────
        "block":      ("▌", "|"),
        "block_err":  ("▌", "|"),
        "block_ai":   ("▌", "|"),
        "separator":  ("·", "."),

        # ── Domain ────────────────────────────────────────────────────
        "database":   ("⊙", "[DB]"),
        "table":      ("⊞", "[T]"),
        "key":        ("⚿", "[PK]"),
        "link":       ("⇢", "->"),
        "search":     ("/", "/"),
        "time":       ("◷", "[t]"),
        "rows":       ("≡", "="),
        "token":      ("◈", "#"),
        "cost":       ("◇", "$"),
        "copy":       ("⊞", "[C]"),
        "ai":         ("◎", "[@]"),
        "gear":       ("⚙", "[G]"),
        "bolt":       ("⚡", ">"),
        "sparkle":    ("✦", "*"),
        "shield":     ("◆", "[S]"),
        "brain":      ("◎", "@"),
        "pulse":      ("◌", "o"),
        "star":       ("★", "*"),
        "wave":       ("~", "~"),
        "rocket":     ("»", ">>"),
        "sparkles":   ("✧", "~"),
    }

    @classmethod
    def _icon(cls, name: str) -> str:
        pair = cls._SYMBOLS.get(name, ("?", "?"))
        return pair[0] if SUPPORTS_UNICODE else pair[1]

    # ── Prompt & Navigation ───────────────────────────────────────────
    @classmethod
    def prompt(cls) -> str: return cls._icon("prompt")
    @classmethod
    def arrow(cls) -> str: return cls._icon("arrow")
    @classmethod
    def arrow_r(cls) -> str: return cls._icon("arrow")
    @classmethod
    def arrow_d(cls) -> str: return cls._icon("arrow_d")
    @classmethod
    def expand(cls) -> str: return cls._icon("expand")
    @classmethod
    def collapse(cls) -> str: return cls._icon("collapse")
    @classmethod
    def chevron(cls) -> str: return cls._icon("chevron")
    @classmethod
    def chevron_d(cls) -> str: return cls._icon("chevron_d")
    @classmethod
    def bullet(cls) -> str: return cls._icon("bullet")

    # ── Status ────────────────────────────────────────────────────────
    @classmethod
    def check(cls) -> str: return cls._icon("check")
    @classmethod
    def cross(cls) -> str: return cls._icon("cross")
    @classmethod
    def warn(cls) -> str: return cls._icon("warn")
    @classmethod
    def info(cls) -> str: return cls._icon("info")
    @classmethod
    def dot_filled(cls) -> str: return cls._icon("dot_filled")
    @classmethod
    def dot_empty(cls) -> str: return cls._icon("dot_empty")
    @classmethod
    def dot_pulse(cls) -> str: return cls._icon("dot_pulse")
    @classmethod
    def dot_green(cls) -> str: return cls._icon("dot_filled")
    @classmethod
    def dot_yellow(cls) -> str: return cls._icon("dot_filled")
    @classmethod
    def dot_red(cls) -> str: return cls._icon("dot_filled")

    # ── Block & Structure ─────────────────────────────────────────────
    @classmethod
    def block(cls) -> str: return cls._icon("block")
    @classmethod
    def block_err(cls) -> str: return cls._icon("block_err")
    @classmethod
    def block_ai(cls) -> str: return cls._icon("block_ai")
    @classmethod
    def separator(cls) -> str: return cls._icon("separator")

    # ── Domain ────────────────────────────────────────────────────────
    @classmethod
    def database(cls) -> str: return cls._icon("database")
    @classmethod
    def table(cls) -> str: return cls._icon("table")
    @classmethod
    def key(cls) -> str: return cls._icon("key")
    @classmethod
    def link(cls) -> str: return cls._icon("link")
    @classmethod
    def search(cls) -> str: return cls._icon("search")
    @classmethod
    def time(cls) -> str: return cls._icon("time")
    @classmethod
    def clock(cls) -> str: return cls._icon("time")
    @classmethod
    def rows(cls) -> str: return cls._icon("rows")
    @classmethod
    def token(cls) -> str: return cls._icon("token")
    @classmethod
    def cost(cls) -> str: return cls._icon("cost")
    @classmethod
    def copy(cls) -> str: return cls._icon("copy")
    @classmethod
    def ai(cls) -> str: return cls._icon("ai")
    @classmethod
    def gear(cls) -> str: return cls._icon("gear")
    @classmethod
    def bolt(cls) -> str: return cls._icon("bolt")
    @classmethod
    def sparkle(cls) -> str: return cls._icon("sparkle")
    @classmethod
    def sparkles(cls) -> str: return cls._icon("sparkles")
    @classmethod
    def shield(cls) -> str: return cls._icon("shield")
    @classmethod
    def brain(cls) -> str: return cls._icon("brain")
    @classmethod
    def pulse(cls) -> str: return cls._icon("pulse")
    @classmethod
    def star(cls) -> str: return cls._icon("star")
    @classmethod
    def wave(cls) -> str: return cls._icon("wave")
    @classmethod
    def rocket(cls) -> str: return cls._icon("rocket")


# ═══════════════════════════════════════════════════════════════════════════════
#  BOX STYLES — Minimal
# ═══════════════════════════════════════════════════════════════════════════════

ROUNDED_BOX  = box.ROUNDED
SIMPLE_BOX   = box.SIMPLE
MINIMAL_BOX  = box.SIMPLE_HEAVY
ASCII_BOX    = box.ASCII

# Backward compat
HEAVY_BOX    = box.ROUNDED     # Map heavy -> rounded (softer)
DOUBLE_BOX   = box.ROUNDED


# ═══════════════════════════════════════════════════════════════════════════════
#  GRADIENT PRESETS — Retained for backward compat, simplified
# ═══════════════════════════════════════════════════════════════════════════════

GRADIENT_AURORA: List[str] = [
    "#6366F1", "#818CF8", "#A78BFA", "#6366F1", "#818CF8", "#A78BFA",
]

GRADIENT_OCEAN: List[str] = [
    "#06B6D4", "#38BDF8", "#6366F1", "#818CF8", "#A78BFA", "#06B6D4",
]

GRADIENT_SUNSET: List[str] = [
    "#F59E0B", "#EF4444", "#A78BFA", "#6366F1", "#818CF8", "#38BDF8",
]

GRADIENT_NEON: List[str] = [
    "#06B6D4", "#2DD4BF", "#10B981", "#38BDF8", "#6366F1", "#A78BFA",
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
#  RICH THEME — Token-to-Style Mapping
# ═══════════════════════════════════════════════════════════════════════════════

RICH_THEME = Theme({
    "primary":     Colors.PRIMARY,
    "secondary":   Colors.AI_ACCENT,
    "accent":      Colors.AI_ACCENT,
    "success":     Colors.SUCCESS,
    "warning":     Colors.WARNING,
    "error":       Colors.ERROR,
    "info":        Colors.INFO,
    "muted":       Colors.TEXT_TERTIARY,
    "dim":         Colors.TEXT_MUTED,
    "ghost":       Colors.TEXT_GHOST,
    "card.border": Colors.BORDER_DEFAULT,
    "body":        Colors.TEXT_SECONDARY,
})


# ═══════════════════════════════════════════════════════════════════════════════
#  VISUAL PRIMITIVES — Functional micro-components
# ═══════════════════════════════════════════════════════════════════════════════

def badge(label: str, color: str = Colors.PRIMARY) -> str:
    """Inline colored badge/pill for tags."""
    return f"[bold {color} on {Colors.SURFACE_1}] {label} [/bold {color} on {Colors.SURFACE_1}]"


def dim_label(label: str, value: str, sep: str = ":") -> str:
    """A dim label followed by a bright value."""
    return (
        f"[{Colors.TEXT_TERTIARY}]{label}{sep}[/{Colors.TEXT_TERTIARY}] "
        f"[bold {Colors.TEXT_PRIMARY}]{value}[/bold {Colors.TEXT_PRIMARY}]"
    )


def progress_bar(
    fraction: float,
    width: int = 20,
    fill_color: str = Colors.PRIMARY,
    empty_color: str = Colors.TEXT_GHOST,
) -> str:
    """Render a single-line progress/percentage bar."""
    filled = int(fraction * width)
    empty = width - filled
    return (
        f"[{fill_color}]{'━' * filled}[/{fill_color}]"
        f"[{empty_color}]{'━' * empty}[/{empty_color}]"
    )


def status_dot(state: str = "ok") -> str:
    """Return a colored status dot based on state."""
    if state == "ok":
        return f"[bold {Colors.SUCCESS}]{Icons.dot_filled()}[/bold {Colors.SUCCESS}]"
    elif state == "warn":
        return f"[bold {Colors.WARNING}]{Icons.dot_filled()}[/bold {Colors.WARNING}]"
    elif state == "ai":
        return f"[bold {Colors.AI_ACCENT}]{Icons.dot_pulse()}[/bold {Colors.AI_ACCENT}]"
    else:
        return f"[bold {Colors.ERROR}]{Icons.dot_filled()}[/bold {Colors.ERROR}]"


def latency_color(ms: int) -> str:
    """Return appropriate color for a latency value."""
    if ms < 500:
        return Colors.SUCCESS
    elif ms < 2000:
        return Colors.WARNING
    return Colors.ERROR


# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED CONSOLE SINGLETONS
# ═══════════════════════════════════════════════════════════════════════════════

console = Console(theme=RICH_THEME, safe_box=True)
err_console = Console(stderr=True, theme=RICH_THEME, safe_box=True)
