"""
Application-wide dark theme for CAD2URDF.

Palette is based on Catppuccin Mocha so the widgets blend with the
PyVista viewer background (#1e1e2e).

Usage (in main.py, right after QApplication is created):

    from gui.theme import apply_theme
    apply_theme(app)

Icons: use `icon('fa5s.folder-open')` — returns a themed qtawesome icon,
or a null QIcon if qtawesome is not installed (app still works).
"""
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtCore import Qt

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

BASE       = '#1e1e2e'   # window / viewer background
MANTLE     = '#181825'   # darker: menubar, statusbar, headers
SURFACE0   = '#313244'   # cards, inputs
SURFACE1   = '#45475a'   # hover, borders
SURFACE2   = '#585b70'   # strong borders, scrollbar hover
TEXT       = '#cdd6f4'
SUBTEXT    = '#a6adc8'
OVERLAY    = '#6c7086'   # disabled text
ACCENT     = '#89b4fa'   # blue — selection, focus, progress
ACCENT_DIM = '#3b5379'   # muted accent for subtle selection backgrounds
GREEN      = '#a6e3a1'
YELLOW     = '#f9e2af'
RED        = '#f38ba8'
TEAL       = '#94e2d5'


def icon(name: str, color: str = TEXT) -> QIcon:
    """Themed qtawesome icon; falls back to an empty icon if unavailable."""
    try:
        import qtawesome as qta
        return qta.icon(name, color=color)
    except Exception:
        return QIcon()


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

_QSS = f"""
/* ---------- Base ---------- */
QWidget {{
    background: {BASE};
    color: {TEXT};
    font-size: 9pt;
}}
QMainWindow, QDialog {{
    background: {BASE};
}}
QLabel {{
    background: transparent;
}}
QToolTip {{
    background: {MANTLE};
    color: {TEXT};
    border: 1px solid {SURFACE2};
    padding: 4px 8px;
}}

/* ---------- Menu bar & menus ---------- */
QMenuBar {{
    background: {MANTLE};
    padding: 2px;
    border-bottom: 1px solid {SURFACE0};
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: {SURFACE0};
}}
QMenu {{
    background: {MANTLE};
    border: 1px solid {SURFACE1};
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 24px 5px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {ACCENT_DIM};
}}
QMenu::separator {{
    height: 1px;
    background: {SURFACE1};
    margin: 4px 8px;
}}

/* ---------- Toolbar ---------- */
QToolBar {{
    background: {MANTLE};
    border: none;
    border-bottom: 1px solid {SURFACE0};
    padding: 3px;
    spacing: 2px;
}}
QToolButton {{
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 5px 8px;
}}
QToolButton:hover {{
    background: {SURFACE0};
}}
QToolButton:pressed {{
    background: {SURFACE1};
}}

/* ---------- Tree / list views ---------- */
QTreeWidget, QTreeView, QListWidget {{
    background: {MANTLE};
    alternate-background-color: #1c1c2b;
    border: 1px solid {SURFACE0};
    border-radius: 6px;
    padding: 2px;
}}
QTreeWidget::item, QTreeView::item {{
    padding: 3px 2px;
    border-radius: 4px;
}}
QTreeWidget::item:hover, QTreeView::item:hover {{
    background: {SURFACE0};
}}
QTreeWidget::item:selected, QTreeView::item:selected {{
    background: {ACCENT_DIM};
    color: {TEXT};
}}
QHeaderView::section {{
    background: {MANTLE};
    color: {SUBTEXT};
    border: none;
    border-bottom: 1px solid {SURFACE1};
    padding: 5px 6px;
    font-weight: 600;
}}

/* ---------- Tabs ---------- */
QTabWidget::pane {{
    border: 1px solid {SURFACE0};
    border-radius: 6px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {SUBTEXT};
    padding: 6px 16px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{
    color: {TEXT};
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}

/* ---------- Cards (group boxes) ---------- */
QGroupBox {{
    background: {SURFACE0};
    border: 1px solid {SURFACE1};
    border-radius: 8px;
    margin-top: 10px;
    padding: 8px 6px 6px 6px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: {ACCENT};
}}
QGroupBox QLabel {{
    background: transparent;
    font-weight: normal;
}}

/* ---------- Inputs ---------- */
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {MANTLE};
    border: 1px solid {SURFACE1};
    border-radius: 5px;
    padding: 4px 6px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus,
QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {OVERLAY};
    border-color: {SURFACE0};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {SUBTEXT};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: {MANTLE};
    border: 1px solid {SURFACE1};
    selection-background-color: {ACCENT_DIM};
    outline: none;
}}
QDoubleSpinBox::up-button, QSpinBox::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    background: {SURFACE0};
    border: none;
    width: 16px;
}}
QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
    background: {SURFACE1};
}}
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 4px solid {SUBTEXT};
}}
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid {SUBTEXT};
}}

/* ---------- Buttons ---------- */
QPushButton {{
    background: {SURFACE0};
    border: 1px solid {SURFACE1};
    border-radius: 5px;
    padding: 5px 16px;
}}
QPushButton:hover {{
    background: {SURFACE1};
    border-color: {SURFACE2};
}}
QPushButton:pressed {{
    background: {ACCENT_DIM};
}}
QPushButton:default {{
    background: {ACCENT};
    color: {MANTLE};
    border: none;
    font-weight: 600;
}}
QPushButton:default:hover {{
    background: #a5c8ff;
}}
QPushButton:disabled {{
    color: {OVERLAY};
    background: {MANTLE};
    border-color: {SURFACE0};
}}
QCheckBox {{
    background: transparent;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {SURFACE2};
    border-radius: 4px;
    background: {MANTLE};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {SURFACE1};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {SURFACE2};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {SURFACE1};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {SURFACE2};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0; width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}

/* ---------- Status bar & progress ---------- */
QStatusBar {{
    background: {MANTLE};
    border-top: 1px solid {SURFACE0};
    color: {SUBTEXT};
}}
QStatusBar::item {{
    border: none;
}}
QProgressBar {{
    background: {SURFACE0};
    border: none;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: {TEXT};
    font-size: 8pt;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 6px;
}}

/* ---------- Splitter ---------- */
QSplitter::handle {{
    background: {BASE};
}}
QSplitter::handle:hover {{
    background: {ACCENT_DIM};
}}
QSplitter::handle:horizontal {{
    width: 4px;
}}
QSplitter::handle:vertical {{
    height: 4px;
}}

/* ---------- Message boxes ---------- */
QMessageBox {{
    background: {BASE};
}}
"""


def apply_theme(app):
    """Apply the CAD2URDF dark theme to the whole application."""
    app.setStyle('Fusion')

    # Palette for widgets QSS doesn't reach (native dialogs, item views)
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(BASE))
    pal.setColor(QPalette.WindowText,      QColor(TEXT))
    pal.setColor(QPalette.Base,            QColor(MANTLE))
    pal.setColor(QPalette.AlternateBase,   QColor('#1c1c2b'))
    pal.setColor(QPalette.Text,            QColor(TEXT))
    pal.setColor(QPalette.Button,          QColor(SURFACE0))
    pal.setColor(QPalette.ButtonText,      QColor(TEXT))
    pal.setColor(QPalette.Highlight,       QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor(MANTLE))
    pal.setColor(QPalette.ToolTipBase,     QColor(MANTLE))
    pal.setColor(QPalette.ToolTipText,     QColor(TEXT))
    pal.setColor(QPalette.PlaceholderText, QColor(OVERLAY))
    pal.setColor(QPalette.Link,            QColor(ACCENT))
    pal.setColor(QPalette.Disabled, QPalette.Text,       QColor(OVERLAY))
    pal.setColor(QPalette.Disabled, QPalette.WindowText, QColor(OVERLAY))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(OVERLAY))
    app.setPalette(pal)

    app.setStyleSheet(_QSS)
