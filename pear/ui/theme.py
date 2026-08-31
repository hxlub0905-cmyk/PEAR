"""Design tokens and global QSS — a single light instrument theme.

Palette and type are adopted from the sibling project's design system
(PixelOpt): a calm light ground with a single amber brand accent, black
image stage, and system-safe fonts (no exotic webfont to miss on a fab PC).
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

# --- palette -------------------------------------------------------------- #
WINDOW = "#F5F6F8"      # app ground
PANEL = "#FFFFFF"       # panels
CARD = "#FBFCFE"        # cards / insets
SUBTLE = "#F3F4F6"      # subtle fills, tracks

INK = "#1F2937"         # primary text
INK2 = "#4B5563"        # secondary text
INK3 = "#9CA3AF"        # muted text

LINE = "#E5E7EB"        # borders
LINE2 = "#EEF1F4"       # hairlines

AMBER = "#F59E0B"       # brand accent
AMBER_HOVER = "#FBBF24"
AMBER_PRESS = "#D97706"
AMBER_SOFT = "#FEF3C7"
ON_AMBER = "#3D2C05"    # ink on amber fills

STAGE = "#000000"       # image stage

SUCCESS = "#16A34A"
WARNING = "#DC2626"
INFO = "#2563EB"
CYAN = "#0891B2"

# Target / reference accents (mirror the core defaults).
TARGET = "#DC2626"
REFERENCE = "#0891B2"

GRID_RGBA = (150, 168, 178, 46)     # cell grid on the black stage

# --- fonts ---------------------------------------------------------------- #
_SANS = "'Segoe UI', 'Liberation Sans', Arial, 'Helvetica Neue', sans-serif"
_MONO = "'Liberation Mono', 'SFMono-Regular', Consolas, Menlo, monospace"


def color(token: str) -> QColor:
    return QColor(token)


def _pick(families, default: str) -> str:
    available = set(QFontDatabase.families())
    return next((f for f in families if f in available), default)


def _weight(value) -> QFont.Weight:
    return value if isinstance(value, QFont.Weight) else QFont.Weight(int(value))


def mono_font(size: int = 10, weight=QFont.Medium) -> QFont:
    fam = _pick(["Liberation Mono", "Consolas", "Menlo", "Courier New"],
                "Courier New")
    f = QFont(fam, size)
    f.setStyleHint(QFont.Monospace)
    f.setWeight(_weight(weight))
    return f


def display_font(size: int = 13, weight=QFont.DemiBold) -> QFont:
    fam = _pick(["Segoe UI", "Liberation Sans", "Helvetica Neue", "Arial"],
                "Arial")
    f = QFont(fam, size)
    f.setWeight(_weight(weight))
    return f


def eyebrow_font(size: int = 9) -> QFont:
    fam = _pick(["Segoe UI", "Liberation Sans", "Arial"], "Arial")
    f = QFont(fam, size)
    f.setWeight(QFont.Bold)
    f.setCapitalization(QFont.AllUppercase)
    f.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
    return f


def build_qss() -> str:
    return f"""
* {{ font-family: {_SANS}; color: {INK}; outline: none; }}
QMainWindow, QWidget {{ background: {WINDOW}; }}
QLabel {{ background: transparent; }}

/* topbar */
#TopBar {{ background: {PANEL}; border-bottom: 1px solid {LINE}; }}
#BrandTitle {{ font-size: 19px; font-weight: 700; letter-spacing: -0.4px; color: {INK}; }}
#BrandAccent {{ font-size: 19px; font-weight: 700; letter-spacing: -0.4px; color: {AMBER}; }}
#BrandSub {{ color: {INK3}; font-size: 11px; font-weight: 600; }}
#DatasetTag {{
    color: {INK2}; background: {SUBTLE}; border: 1px solid {LINE};
    border-radius: 8px; padding: 4px 10px; font-family: {_MONO}; font-size: 11px;
}}

/* dock */
QDockWidget {{ font-weight: 600; color: {INK}; titlebar-close-icon: none; }}
QDockWidget::title {{
    background: {SUBTLE}; color: {INK2}; padding: 7px 12px; font-weight: 700;
    border-bottom: 1px solid {LINE};
}}
QDockWidget::float-button, QDockWidget::close-button {{
    background: {PANEL}; border: 1px solid {LINE}; border-radius: 4px;
}}

/* stage bar — the overlay controls, docked over the image */
QWidget#StageBar {{ background: {PANEL}; border-bottom: 1px solid {LINE}; }}

/* cards */
QFrame#Card {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 14px; }}
QLabel#SectionTitle {{ font-weight: 700; font-size: 13px; color: {INK}; }}
QLabel#Eyebrow {{ color: {INK3}; font-weight: 700; }}
QLabel#Hint {{ color: {INK3}; font-size: 11px; }}
QLabel#Mono {{ font-family: {_MONO}; color: {INK2}; }}
QLabel#Measured {{
    font-family: {_MONO}; color: {INK}; background: {SUBTLE};
    border-left: 3px solid {INFO}; padding: 7px 10px; border-radius: 0 6px 6px 0;
}}

/* buttons */
QPushButton {{
    background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px;
    padding: 7px 13px; font-weight: 600; color: {INK};
}}
QPushButton:hover {{ border-color: {AMBER}; color: {AMBER_PRESS}; }}
QPushButton:pressed {{ background: {SUBTLE}; }}
QPushButton#Primary {{ background: {AMBER}; border: 1px solid {AMBER}; color: #FFFFFF; }}
QPushButton#Primary:hover {{ background: {AMBER_HOVER}; border-color: {AMBER_HOVER}; color: {ON_AMBER}; }}
QPushButton#Primary:disabled {{ background: {SUBTLE}; border-color: {LINE}; color: {INK3}; }}
QPushButton:checked {{ background: {AMBER}; border-color: {AMBER}; color: {ON_AMBER}; }}
QPushButton:disabled {{ background: {SUBTLE}; color: {INK3}; border-color: {LINE}; }}

/* inputs */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {PANEL}; border: 1px solid {LINE}; border-radius: 8px;
    padding: 5px 8px; font-family: {_MONO};
    selection-background-color: {AMBER}; selection-color: #FFFFFF;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {AMBER}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0px; }}
QComboBox {{
    background: {PANEL}; border: 1px solid {LINE}; border-radius: 8px;
    padding: 5px 8px; color: {INK};
}}
QComboBox:focus {{ border-color: {AMBER}; }}
QComboBox QAbstractItemView {{
    background: {PANEL}; border: 1px solid {LINE}; selection-background-color: {AMBER_SOFT};
    selection-color: {INK}; outline: none;
}}

/* checkbox */
QCheckBox {{ font-weight: 600; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {LINE};
    border-radius: 5px; background: {PANEL}; }}
QCheckBox::indicator:checked {{ background: {AMBER}; border-color: {AMBER}; }}

/* lists */
QListWidget {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px; outline: none; }}
QListWidget::item {{ padding: 6px 8px; border-radius: 7px; }}
QListWidget::item:selected {{ background: {AMBER_SOFT}; color: {INK}; }}

/* tabs (workspace) */
QTabWidget::pane {{ border: none; background: transparent; }}
QTabBar::tab {{ background: {SUBTLE}; border: 1px solid {LINE}; border-bottom: none;
    padding: 7px 16px; font-weight: 600; color: {INK2}; border-radius: 8px 8px 0 0; }}
QTabBar::tab:selected {{ background: {PANEL}; color: {INK}; }}

/* scroll + status + tooltip */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {LINE}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {LINE}; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QStatusBar {{ background: {PANEL}; color: {INK2}; border-top: 1px solid {LINE}; }}
QStatusBar::item {{ border: none; }}
QToolTip {{ background: {INK}; color: #FFFFFF; border: none; padding: 5px 8px; border-radius: 6px; }}
"""


def apply_theme(app, *_ignored) -> None:
    """Apply the light theme to a QApplication (single theme; args ignored)."""
    app.setStyleSheet(build_qss())
    fam = _pick(["Segoe UI", "Liberation Sans", "Helvetica Neue", "Arial"], "Arial")
    app.setFont(QFont(fam, 10))
