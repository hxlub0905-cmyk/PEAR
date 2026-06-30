"""Design tokens and global QSS, with swappable palettes.

Two palettes are provided:

* ``"swiss"`` — Swiss International Typographic Style: pure black/white,
  a single Swiss-red signal colour, thick black borders, flat.
* ``"dark"`` — calm dark instrument: dark slate panels matching the image
  stage, one teal accent used sparingly, easy on the eyes for long
  sessions. Recommended default for a lab tool.

Product invariant across palettes: outlier markers stay AMBER, never red —
the "no verdict" principle forbids red ("bad") for markers (spec §10.6).
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

# --- palettes ------------------------------------------------------------- #
_PALETTES = {
    "swiss": {
        "BG": "#F2F2F2", "PANEL": "#FFFFFF", "INK": "#000000",
        "LINE": "#000000", "MUTED": "#5A5A5A", "FAINT": "#9A9A9A",
        "ACCENT": "#FF3000", "ACCENT_BRIGHT": "#FF3000", "ON_ACCENT": "#FFFFFF",
        "INVERT_BG": "#000000", "INVERT_FG": "#FFFFFF",
        "STAGE": "#15191F", "FLAG": "#E0A52E", "OK": "#000000", "BW": 2,
    },
    "dark": {
        "BG": "#11151B", "PANEL": "#1A2029", "INK": "#E7ECF1",
        "LINE": "#2B333E", "MUTED": "#93A0AC", "FAINT": "#5B6571",
        "ACCENT": "#2BB6B6", "ACCENT_BRIGHT": "#42D4D4", "ON_ACCENT": "#06222A",
        "INVERT_BG": "#2BB6B6", "INVERT_FG": "#06222A",
        "STAGE": "#0B0E13", "FLAG": "#E8B23E", "OK": "#37B088", "BW": 1,
    },
}
DEFAULT_PALETTE = "dark"

# Module-level tokens (legacy names kept). Initialized by set_palette().
INK = PANEL = CHROME = MUTED = FAINT = LINE = ""
ACCENT = ACCENT_BRIGHT = ON_ACCENT = INVERT_BG = INVERT_FG = ""
STAGE = FLAG = OK = ""
BORDER_W = 2
GRID_RGBA = (150, 168, 178, 56)   # cell grid on the dark stage
_active_palette = DEFAULT_PALETTE


def set_palette(name: str) -> None:
    """Set the active palette and update all module-level colour tokens."""
    global INK, PANEL, CHROME, MUTED, FAINT, LINE, ACCENT, ACCENT_BRIGHT
    global ON_ACCENT, INVERT_BG, INVERT_FG, STAGE, FLAG, OK, BORDER_W
    global _active_palette
    p = _PALETTES.get(name, _PALETTES[DEFAULT_PALETTE])
    _active_palette = name if name in _PALETTES else DEFAULT_PALETTE
    INK = p["INK"]
    PANEL = p["PANEL"]
    CHROME = p["BG"]
    MUTED = p["MUTED"]
    FAINT = p["FAINT"]
    LINE = p["LINE"]
    ACCENT = p["ACCENT"]
    ACCENT_BRIGHT = p["ACCENT_BRIGHT"]
    ON_ACCENT = p["ON_ACCENT"]
    INVERT_BG = p["INVERT_BG"]
    INVERT_FG = p["INVERT_FG"]
    STAGE = p["STAGE"]
    FLAG = p["FLAG"]
    OK = p["OK"]
    BORDER_W = p["BW"]


def active_palette() -> str:
    return _active_palette


set_palette(DEFAULT_PALETTE)

# --- font families -------------------------------------------------------- #
DISPLAY_FAMILY = "Inter"
BODY_FAMILY = "Inter"
MONO_FAMILY = "IBM Plex Mono"

_SANS_FALLBACK = "Inter, Helvetica Neue, Helvetica, Arial, sans-serif"
_MONO_FALLBACK = "IBM Plex Mono, Consolas, Menlo, monospace"


def color(token: str) -> QColor:
    return QColor(token)


def _pick(families: list[str], default: str) -> str:
    available = set(QFontDatabase.families())
    return next((f for f in families if f in available), default)


def _weight(value) -> QFont.Weight:
    """Coerce an int or QFont.Weight into a QFont.Weight (Qt6 requires it)."""
    return value if isinstance(value, QFont.Weight) else QFont.Weight(int(value))


def mono_font(size: int = 10, weight=QFont.Medium) -> QFont:
    """Monospace font for measured numeric values (tabular alignment)."""
    fam = _pick([MONO_FAMILY, "Consolas", "Menlo", "Courier New"], MONO_FAMILY)
    f = QFont(fam, size)
    f.setStyleHint(QFont.Monospace)
    f.setWeight(_weight(weight))
    return f


def display_font(size: int = 12, weight=QFont.Black) -> QFont:
    """Heavy grotesque display font for headings."""
    fam = _pick([DISPLAY_FAMILY, "Helvetica Neue", "Arial"], "Arial")
    f = QFont(fam, size)
    f.setWeight(_weight(weight))
    return f


def eyebrow_font(size: int = 9) -> QFont:
    """Small uppercase tracked label (Qt QSS cannot do letter-spacing)."""
    fam = _pick([DISPLAY_FAMILY, "Helvetica Neue", "Arial"], "Arial")
    f = QFont(fam, size)
    f.setWeight(QFont.Bold)
    f.setCapitalization(QFont.AllUppercase)
    f.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
    return f


def build_qss() -> str:
    """Build the global stylesheet from the active palette tokens."""
    bw = BORDER_W
    return f"""
* {{
    font-family: {_SANS_FALLBACK};
    color: {INK};
    outline: none;
}}
QMainWindow, QWidget {{ background: {CHROME}; }}
QLabel {{ background: transparent; }}

/* topbar */
#TopBar {{ background: {PANEL}; border-bottom: {bw + 1}px solid {LINE}; }}
#BrandTitle {{
    font-size: 22px; font-weight: 900; letter-spacing: -0.5px; color: {INK};
}}
#BrandSub {{ color: {MUTED}; font-size: 11px; font-weight: 700; }}
#DatasetTag {{
    color: {INVERT_FG}; background: {INVERT_BG}; font-weight: 700;
    padding: 3px 8px; font-family: {_MONO_FALLBACK};
}}

/* docks */
QDockWidget {{ font-weight: 900; color: {INK}; }}
QDockWidget::title {{
    background: {INVERT_BG}; color: {INVERT_FG}; padding: 7px 12px;
}}

/* cards */
QFrame#Card {{
    background: {PANEL}; border: {bw}px solid {LINE}; border-radius: 0px;
}}
QLabel#SectionTitle {{ font-weight: 900; font-size: 15px; color: {INK}; }}
QLabel#Eyebrow {{ color: {ACCENT}; font-weight: 700; }}
QLabel#Hint {{ color: {MUTED}; font-size: 11px; }}
QLabel#Caption {{ color: {INK}; font-size: 11px; font-weight: 700; }}
QLabel#Mono, QLabel#MeasuredLine {{
    font-family: {_MONO_FALLBACK}; color: {INK};
}}
QLabel#MeasuredLine {{
    background: {CHROME}; border-left: 3px solid {ACCENT}; padding: 6px 8px;
}}

/* buttons */
QPushButton {{
    background: {PANEL}; border: {bw}px solid {LINE}; border-radius: 0px;
    padding: 7px 14px; font-weight: 700; color: {INK};
}}
QPushButton:hover {{
    background: {ACCENT}; border-color: {ACCENT}; color: {ON_ACCENT};
}}
QPushButton:pressed {{
    background: {INVERT_BG}; border-color: {INVERT_BG}; color: {INVERT_FG};
}}
QPushButton#Primary {{
    background: {INVERT_BG}; border: {bw}px solid {INVERT_BG};
    color: {INVERT_FG}; font-weight: 900;
}}
QPushButton#Primary:hover {{ background: {ACCENT}; border-color: {ACCENT};
    color: {ON_ACCENT}; }}
QPushButton:checked {{
    background: {ACCENT}; border-color: {ACCENT}; color: {ON_ACCENT};
}}
QPushButton:disabled {{
    background: {CHROME}; color: {FAINT}; border-color: {FAINT};
}}

/* inputs */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {PANEL}; border: {bw}px solid {LINE}; border-radius: 0px;
    padding: 5px 8px; font-family: {_MONO_FALLBACK};
    selection-background-color: {ACCENT}; selection-color: {ON_ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: {bw}px solid {ACCENT};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0px; }}

/* checkbox */
QCheckBox {{ font-weight: 700; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: {bw}px solid {LINE}; background: {PANEL};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

/* lists */
QListWidget {{
    background: {PANEL}; border: {bw}px solid {LINE}; border-radius: 0px;
    outline: none;
}}
QListWidget::item {{ padding: 7px 8px; border-bottom: 1px solid {CHROME}; }}
QListWidget::item:selected {{ background: {INVERT_BG}; color: {INVERT_FG}; }}

/* tabs */
QTabWidget::pane {{
    border: {bw}px solid {LINE}; border-radius: 0px; top: -{bw}px;
    background: {CHROME};
}}
QTabBar::tab {{
    background: {PANEL}; border: {bw}px solid {LINE}; border-right-width: 0px;
    padding: 8px 18px; font-weight: 900; color: {INK};
}}
QTabBar::tab:last {{ border-right-width: {bw}px; }}
QTabBar::tab:selected {{ background: {INVERT_BG}; color: {INVERT_FG}; }}
QTabBar::tab:hover:!selected {{ background: {ACCENT}; color: {ON_ACCENT}; }}

/* scroll + status + tooltip */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: {CHROME}; width: 12px; margin: 0px; }}
QScrollBar::handle:vertical {{ background: {LINE}; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; border-top: 1px solid {LINE}; }}
QToolTip {{
    background: {INVERT_BG}; color: {INVERT_FG}; border: none; padding: 4px 6px;
}}
"""


def apply_theme(app, palette: str = DEFAULT_PALETTE) -> None:
    """Apply the given palette's stylesheet to a QApplication."""
    set_palette(palette)
    app.setStyleSheet(build_qss())
    fam = _pick([BODY_FAMILY, "Helvetica Neue", "Arial"], "Arial")
    app.setFont(QFont(fam, 10))
