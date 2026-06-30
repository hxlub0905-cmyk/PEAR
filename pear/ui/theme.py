"""Design tokens and global QSS — Swiss International Typographic Style.

Objective, grid-driven, flat. Pure black/white with a single Swiss-red
signal colour, 0px radii, thick black borders, heavy grotesque type, and
uppercase tracked labels. The image stage stays dark (a SEM canvas needs
contrast); everything else is Swiss chrome.

Product exception: outlier markers remain AMBER, never red — the
"no verdict" principle forbids red ("bad") for markers (spec §10.6).
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

# --- colour tokens (strict Swiss palette) --------------------------------- #
INK = "#000000"          # foreground / text — absolute black
PANEL = "#FFFFFF"        # surfaces — pure white
CHROME = "#F2F2F2"       # muted secondary background
MUTED = "#5A5A5A"        # secondary text
FAINT = "#9A9A9A"        # placeholder / tertiary text
LINE = "#000000"         # structure is visible — black hairlines/borders
ACCENT = "#FF3000"       # Swiss red — the ONLY signal colour (CTA/active)
ACCENT_BRIGHT = "#FF3000"

STAGE = "#15191F"        # dark image canvas
FLAG = "#E0A52E"         # amber outlier markers — "look here", never red
OK = "#000000"           # neutral/good state reads as black in Swiss

GRID_RGBA = (150, 168, 178, 56)   # cell grid on the dark stage

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


_QSS = f"""
* {{
    font-family: {_SANS_FALLBACK};
    color: {INK};
    outline: none;
}}
QMainWindow, QWidget {{
    background: {CHROME};
}}
/* Labels must be transparent — otherwise the QWidget rule above paints a
   grey band behind every label and hides painted row backgrounds. */
QLabel {{
    background: transparent;
}}

/* ---- topbar ---- */
#TopBar {{
    background: {PANEL};
    border-bottom: 3px solid {INK};
}}
#BrandTitle {{
    font-family: {_SANS_FALLBACK};
    font-size: 22px;
    font-weight: 900;
    letter-spacing: -0.5px;
    color: {INK};
}}
#BrandSub {{
    color: {MUTED};
    font-size: 11px;
    font-weight: 700;
}}
#DatasetTag {{
    color: {PANEL};
    background: {INK};
    font-weight: 700;
    padding: 3px 8px;
    font-family: {_MONO_FALLBACK};
}}

/* ---- docks ---- */
QDockWidget {{
    font-family: {_SANS_FALLBACK};
    font-weight: 900;
    color: {INK};
}}
QDockWidget::title {{
    background: {INK};
    color: {PANEL};
    padding: 7px 12px;
    text-transform: uppercase;
}}

/* ---- cards ---- */
QFrame#Card {{
    background: {PANEL};
    border: 2px solid {INK};
    border-radius: 0px;
}}
QLabel#SectionTitle {{
    font-family: {_SANS_FALLBACK};
    font-weight: 900;
    font-size: 15px;
    color: {INK};
}}
QLabel#Eyebrow {{
    color: {ACCENT};
    font-weight: 700;
}}
QLabel#Hint {{
    color: {MUTED};
    font-size: 11px;
}}
QLabel#Caption {{
    color: {INK};
    font-size: 11px;
    font-weight: 700;
}}
QLabel#Mono, QLabel#MeasuredLine {{
    font-family: {_MONO_FALLBACK};
    color: {INK};
}}
QLabel#MeasuredLine {{
    background: {CHROME};
    border-left: 3px solid {ACCENT};
    padding: 6px 8px;
}}

/* ---- buttons ---- */
QPushButton {{
    background: {PANEL};
    border: 2px solid {INK};
    border-radius: 0px;
    padding: 7px 14px;
    font-weight: 700;
    color: {INK};
}}
QPushButton:hover {{
    background: {ACCENT};
    border-color: {ACCENT};
    color: {PANEL};
}}
QPushButton:pressed {{
    background: {INK};
    border-color: {INK};
    color: {PANEL};
}}
QPushButton#Primary {{
    background: {INK};
    border: 2px solid {INK};
    color: {PANEL};
    font-weight: 900;
}}
QPushButton#Primary:hover {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QPushButton:disabled {{
    background: {CHROME};
    color: {FAINT};
    border-color: {FAINT};
}}

/* ---- inputs ---- */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {PANEL};
    border: 2px solid {INK};
    border-radius: 0px;
    padding: 5px 8px;
    font-family: {_MONO_FALLBACK};
    selection-background-color: {ACCENT};
    selection-color: {PANEL};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {ACCENT};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 0px;
}}

/* ---- checkbox ---- */
QCheckBox {{
    font-weight: 700;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 2px solid {INK};
    background: {PANEL};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ---- lists ---- */
QListWidget {{
    background: {PANEL};
    border: 2px solid {INK};
    border-radius: 0px;
    outline: none;
}}
QListWidget::item {{
    padding: 7px 8px;
    border-bottom: 1px solid {CHROME};
}}
QListWidget::item:selected {{
    background: {INK};
    color: {PANEL};
}}

/* ---- tabs ---- */
QTabWidget::pane {{
    border: 2px solid {INK};
    border-radius: 0px;
    top: -2px;
    background: {CHROME};
}}
QTabBar::tab {{
    background: {PANEL};
    border: 2px solid {INK};
    border-right-width: 0px;
    padding: 8px 18px;
    font-weight: 900;
    text-transform: uppercase;
    color: {INK};
}}
QTabBar::tab:last {{
    border-right-width: 2px;
}}
QTabBar::tab:selected {{
    background: {INK};
    color: {PANEL};
}}
QTabBar::tab:hover:!selected {{
    background: {ACCENT};
    color: {PANEL};
}}

/* ---- scroll areas ---- */
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {CHROME};
    width: 12px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {INK};
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QToolTip {{
    background: {INK};
    color: {PANEL};
    border: none;
    padding: 4px 6px;
}}
"""


def apply_theme(app) -> None:
    """Apply the global Swiss stylesheet to a QApplication."""
    app.setStyleSheet(_QSS)
    fam = _pick([BODY_FAMILY, "Helvetica Neue", "Arial"], "Arial")
    app.setFont(QFont(fam, 10))
