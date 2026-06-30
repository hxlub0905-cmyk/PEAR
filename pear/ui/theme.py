"""Design tokens and global QSS — the instrument aesthetic.

Cool neutral chrome, a dark image stage, a single teal signal accent, and
monospaced numerics. Deliberately not the cream/serif or black/acid-green
"AI default" looks.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

# --- color tokens --------------------------------------------------------- #
INK = "#151A21"
MUTED = "#6F7A86"
FAINT = "#9AA4AE"
LINE = "#E1E5EA"
CHROME = "#EDF0F3"
PANEL = "#FFFFFF"
STAGE = "#0E1116"
ACCENT = "#0E8C8C"
ACCENT_BRIGHT = "#23B7B7"
FLAG = "#E0A52E"
OK = "#2E9E7B"

GRID_RGBA = (150, 168, 178, 56)   # rgba(150,168,178,.22) on the stage

# --- font families -------------------------------------------------------- #
DISPLAY_FAMILY = "Space Grotesk"
BODY_FAMILY = "Inter"
MONO_FAMILY = "IBM Plex Mono"

# Fallbacks if the brand fonts are not installed on the machine.
_DISPLAY_FALLBACK = "Space Grotesk, Segoe UI, Arial, sans-serif"
_BODY_FALLBACK = "Inter, Segoe UI, Arial, sans-serif"
_MONO_FALLBACK = "IBM Plex Mono, Consolas, Menlo, monospace"


def color(token: str) -> QColor:
    """Convenience: QColor from a hex token string."""
    return QColor(token)


def mono_font(size: int = 10, weight: int = QFont.Normal) -> QFont:
    """A monospaced font for every measured value (instrument feel)."""
    families = [MONO_FAMILY] + ["Consolas", "Menlo", "Courier New"]
    available = set(QFontDatabase.families())
    fam = next((f for f in families if f in available), MONO_FAMILY)
    f = QFont(fam, size)
    f.setStyleHint(QFont.Monospace)
    f.setWeight(weight)
    return f


def display_font(size: int = 12, weight: int = QFont.DemiBold) -> QFont:
    """Display / eyebrow font."""
    available = set(QFontDatabase.families())
    fam = DISPLAY_FAMILY if DISPLAY_FAMILY in available else "Segoe UI"
    f = QFont(fam, size)
    f.setWeight(weight)
    return f


_QSS = f"""
* {{
    font-family: {_BODY_FALLBACK};
    color: {INK};
}}
QMainWindow, QWidget {{
    background: {CHROME};
}}
QDockWidget {{
    titlebar-close-icon: none;
    font-family: {_DISPLAY_FALLBACK};
    color: {INK};
}}
QDockWidget::title {{
    background: {CHROME};
    padding: 6px 10px;
    border-bottom: 1px solid {LINE};
    font-weight: 600;
}}
#TopBar {{
    background: {PANEL};
    border-bottom: 1px solid {LINE};
}}
#BrandTitle {{
    font-family: {_DISPLAY_FALLBACK};
    font-size: 15px;
    font-weight: 600;
    color: {INK};
}}
#BrandSub {{
    color: {MUTED};
    font-size: 11px;
}}
QFrame#Card {{
    background: {PANEL};
    border: 1px solid {LINE};
    border-radius: 10px;
}}
QLabel#SectionTitle {{
    font-family: {_DISPLAY_FALLBACK};
    font-weight: 600;
    color: {INK};
}}
QLabel#Eyebrow {{
    font-family: {_DISPLAY_FALLBACK};
    color: {MUTED};
    font-size: 10px;
    letter-spacing: 1px;
}}
QLabel#Hint, QLabel#Caption {{
    color: {MUTED};
    font-size: 11px;
}}
QLabel#Mono, QLabel#MeasuredLine {{
    font-family: {_MONO_FALLBACK};
    color: {INK};
}}
QPushButton {{
    background: {PANEL};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 6px 12px;
    color: {INK};
}}
QPushButton:hover {{
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background: {CHROME};
}}
QPushButton#Primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #FFFFFF;
    font-weight: 600;
}}
QPushButton#Primary:hover {{
    background: {ACCENT_BRIGHT};
    border-color: {ACCENT_BRIGHT};
}}
QPushButton:disabled {{
    color: {FAINT};
    border-color: {LINE};
}}
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {PANEL};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 4px 8px;
    font-family: {_MONO_FALLBACK};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}
QListWidget {{
    background: {PANEL};
    border: 1px solid {LINE};
    border-radius: 8px;
    outline: none;
}}
QListWidget::item {{
    padding: 4px 6px;
    border-radius: 6px;
}}
QListWidget::item:selected {{
    background: {CHROME};
    color: {INK};
    border: 1px solid {ACCENT};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QToolTip {{
    background: {INK};
    color: #FFFFFF;
    border: none;
    padding: 4px 6px;
}}
"""


def apply_theme(app) -> None:
    """Apply the global stylesheet to a QApplication."""
    app.setStyleSheet(_QSS)
    base = QFont(_BODY_FALLBACK.split(",")[0].strip(), 10)
    app.setFont(base)
