"""Dark graphite theme (matches the design flow): colours, Qt palette and stylesheet."""
import os
import tempfile

from PySide6.QtGui import QColor, QPalette

C = {
    "bg": "#16181B", "surface": "#1C1F23", "card": "#1F2226", "stage": "#1A1D21",
    "border": "#2C3036", "border2": "#353A41", "hover": "#23272C", "pressed": "#343A42",
    "text": "#E8EAED", "label": "#AEB4BD", "muted": "#9AA1AB",
    "accent": "#F2A93B", "accent_hover": "#FFC872", "on_accent": "#1A1305",
    "success": "#5CC48A", "warn_bg": "#241E14", "warn_border": "#8A6424",
}

FONT = '"Segoe UI", "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif'
MONO = '"Cascadia Mono", Consolas, "IBM Plex Mono", monospace'

_CHECK_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" '
              'stroke="#1A1305" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>')
_DOWN_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" '
             'stroke="#AEB4BD" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>')
_UP_SVG = _DOWN_SVG.replace('d="M6 9l6 6 6-6"', 'd="M6 15l6-6 6 6"')


def _asset_file(name, svg):
    d = os.path.join(tempfile.gettempdir(), "sw-visualize-texture-maker")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(svg)
    return p.replace("\\", "/")


def palette():
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: C["bg"], QPalette.ColorRole.WindowText: C["text"],
        QPalette.ColorRole.Base: C["bg"], QPalette.ColorRole.AlternateBase: C["surface"],
        QPalette.ColorRole.Text: C["text"], QPalette.ColorRole.Button: C["surface"],
        QPalette.ColorRole.ButtonText: C["text"], QPalette.ColorRole.Highlight: C["accent"],
        QPalette.ColorRole.HighlightedText: C["on_accent"], QPalette.ColorRole.ToolTipBase: C["card"],
        QPalette.ColorRole.ToolTipText: C["text"], QPalette.ColorRole.PlaceholderText: C["muted"],
        QPalette.ColorRole.Link: C["accent"],
    }
    for role, col in roles.items():
        p.setColor(role, QColor(col))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#6A7078"))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#6A7078"))
    return p


def stylesheet():
    check = _asset_file("check.svg", _CHECK_SVG)
    down = _asset_file("down.svg", _DOWN_SVG)
    up = _asset_file("up.svg", _UP_SVG)
    c = C
    return f"""
* {{ font-family: {FONT}; font-size: 14px; color: {c['text']}; }}
QMainWindow, QDialog, #Page {{ background: {c['bg']}; }}
QWidget#Transparent, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border2']}; padding: 6px 8px; }}

#Header {{ background: {c['surface']}; border-bottom: 1px solid {c['border']}; }}
#AppTitle {{ font-size: 15px; font-weight: 600; }}
#Footer {{ background: {c['surface']}; border-top: 1px solid {c['border']}; }}
#Panel {{ background: {c['surface']}; border-left: 1px solid {c['border']}; }}
#Stage {{ background: {c['stage']}; border: 1px solid {c['border']}; border-radius: 16px; }}
#Card {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 16px; }}
#Warn {{ background: {c['warn_bg']}; border: 1px solid {c['warn_border']}; border-radius: 10px; }}
#DropZone {{ background: {c['stage']}; border: 2px dashed #3E444C; border-radius: 16px; }}
#DropZone[hover="true"] {{ border-color: {c['accent']}; background: #1E1F1C; }}

#H1 {{ font-size: 24px; font-weight: 600; }}
#H2 {{ font-size: 20px; font-weight: 600; }}
#SectionCaps {{ font-size: 11px; font-weight: 600; letter-spacing: 1px; color: {c['muted']}; }}
#FieldLabel {{ font-size: 13px; font-weight: 600; color: {c['label']}; }}
#Hint {{ font-size: 12px; color: {c['muted']}; }}
#Muted {{ color: {c['muted']}; }}
#Mono {{ font-family: {MONO}; font-size: 13px; }}
#MonoMuted {{ font-family: {MONO}; font-size: 13px; color: {c['label']}; }}
#Success {{ color: {c['success']}; font-weight: 600; }}
#Busy {{ color: {c['accent']}; font-size: 12px; font-weight: 600; }}

QPushButton {{ background: transparent; border: 1px solid {c['border2']}; border-radius: 8px; padding: 0 16px;
  min-height: 40px; color: {c['text']}; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:pressed {{ background: {c['pressed']}; }}
QPushButton:disabled {{ color: #6A7078; border-color: {c['border']}; }}
QPushButton#Primary {{ background: {c['accent']}; color: {c['on_accent']}; border: none; font-weight: 600; padding: 0 24px; min-height: 44px; }}
QPushButton#Primary:hover {{ background: {c['accent_hover']}; }}
QPushButton#Primary:disabled {{ background: #5E4C2C; color: #2A2418; }}
QPushButton#IconButton {{ padding: 0; min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px; border-color: {c['border']}; }}
QPushButton#Swatch {{ padding: 0; min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px; border-radius: 8px; }}
QPushButton#Dot {{ padding: 0; min-width: 32px; max-width: 32px; min-height: 32px; max-height: 32px; border-radius: 16px; }}
QPushButton#Dot:checked {{ border: 3px solid {c['accent']}; }}
QPushButton#RecentCard {{ text-align: left; padding: 10px 12px; background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; min-height: 64px; }}
QPushButton#RecentCard:hover {{ border-color: {c['border2']}; background: #24282D; }}
QPushButton#Link {{ border: none; color: {c['accent']}; padding: 0 4px; min-height: 28px; text-decoration: underline; }}
QPushButton#Disclosure {{ border: none; text-align: left; padding: 0; min-height: 28px; font-weight: 600; }}

#Segmented {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 10px; }}
QPushButton#SegButton {{ border: none; border-radius: 7px; color: {c['label']}; min-height: 34px; padding: 0 14px; font-weight: 500; }}
QPushButton#SegButton:hover {{ background: {c['hover']}; color: {c['text']}; }}
QPushButton#SegButton:checked {{ background: {c['pressed']}; color: #FFFFFF; font-weight: 600; }}

QLineEdit, QSpinBox, QComboBox {{ background: {c['bg']}; border: 1px solid {c['border2']}; border-radius: 8px;
  padding: 0 10px; min-height: 40px; selection-background-color: {c['accent']}; selection-color: {c['on_accent']}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {c['accent']}; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 22px; border: none; background: transparent; }}
QSpinBox::up-arrow {{ image: url({up}); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url({down}); width: 10px; height: 10px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url({down}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['border2']}; selection-background-color: {c['pressed']}; selection-color: #FFFFFF; outline: none; }}

QSlider {{ min-height: 24px; }}
QSlider::groove:horizontal {{ height: 4px; background: {c['border']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {c['text']}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }}
QSlider::handle:horizontal:hover {{ background: #FFFFFF; }}

QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {c['border2']}; background: {c['bg']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; image: url({check}); }}

QProgressBar {{ background: {c['border']}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['border2']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QMessageBox {{ background: {c['surface']}; }}
QMessageBox QLabel {{ color: {c['text']}; }}
"""
