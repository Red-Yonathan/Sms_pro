"""
ui_common.py
==============
Small reusable Qt building blocks (glow effects, the glass "Card"
frame, animated nav buttons, dark title bars, Unicode-safe text
inputs) shared between main.py and project_ui.py so neither has to
import the other.
"""
import ctypes
import sys

from PySide6.QtCore import Qt, QEvent, QObject, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QPushButton, QFrame, QPlainTextEdit, QGraphicsDropShadowEffect

from theme import COLORS


def enable_dark_titlebar(hwnd):
    if sys.platform != "win32":
        return
    try:
        dwmapi = ctypes.windll.dwmapi
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark_mode = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode))
    except Exception:
        pass


def apply_glow(widget, color_hex=None, blur_radius=16, offset=(0, 2)):
    color_hex = color_hex or COLORS["accent"]
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur_radius)
    c = QColor(color_hex) if isinstance(color_hex, str) else color_hex
    if c.alpha() == 255:
        c.setAlpha(60)
    shadow.setColor(c)
    shadow.setOffset(offset[0], offset[1])
    widget.setGraphicsEffect(shadow)
    return shadow


class FocusGlowFilter(QObject):
    def __init__(self, color_hex=None, blur_radius=20, parent=None):
        super().__init__(parent)
        self.color_hex = color_hex or COLORS["accent"]
        self.blur_radius = blur_radius

    def eventFilter(self, watched, event):
        if event.type() == QEvent.FocusIn:
            glow = QGraphicsDropShadowEffect(watched)
            glow.setBlurRadius(self.blur_radius)
            c = QColor(self.color_hex)
            c.setAlpha(120)
            glow.setColor(c)
            glow.setOffset(0, 0)
            watched.setGraphicsEffect(glow)
        elif event.type() == QEvent.FocusOut:
            watched.setGraphicsEffect(None)
        return super().eventFilter(watched, event)


def attach_focus_glow(widget, color_hex=None, blur_radius=20):
    filt = FocusGlowFilter(color_hex or COLORS["accent"], blur_radius, widget)
    widget.installEventFilter(filt)
    widget._focus_glow_filter = filt
    return filt


class AnimatedNavButton(QPushButton):
    def __init__(self, text, checked=False, parent=None):
        super().__init__(text, parent)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setChecked(checked)
        self._padding = 14
        self._hover = False
        self._anim = QPropertyAnimation(self, b"navPadding")
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(lambda _: self._refresh_style())
        self._refresh_style()

    def get_navPadding(self):
        return self._padding

    def set_navPadding(self, val):
        self._padding = val
        self._refresh_style()

    navPadding = Property(int, get_navPadding, set_navPadding)

    def _refresh_style(self):
        bg = COLORS["accent_soft"] if self.isChecked() else (COLORS["surface2"] if self._hover else "transparent")
        fg = COLORS["accent"] if self.isChecked() else (COLORS["text"] if self._hover else COLORS["muted"])
        border = f"border-left: 3px solid {COLORS['accent']};" if self.isChecked() else "border: 0;"
        self.setStyleSheet(
            f"QPushButton#NavButton {{ background: {bg}; color: {fg}; text-align: left; "
            f"padding: 11px {self._padding}px; border-radius: 8px; font-weight: 600; {border} }}"
        )

    def enterEvent(self, event):
        self._hover = True
        self._anim.stop(); self._anim.setEndValue(22); self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._anim.stop(); self._anim.setEndValue(14); self._anim.start()
        super().leaveEvent(event)


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("Card")
        apply_glow(self, COLORS["accent"], blur_radius=18, offset=(0, 3))


def get_font_families():
    available = set(QFontDatabase.families())
    preferred = ["Segoe UI", "Nyala", "Ebrima", "Abyssinica SIL", "Noto Sans Ethiopic", "Ethiopic WashRa", "Arial", "sans-serif"]
    return [f for f in preferred if f in available or f == "sans-serif"]


def choose_font():
    families = set(QFontDatabase.families())
    for family in ("Segoe UI", "Nyala", "Ebrima", "Abyssinica SIL", "Noto Sans Ethiopic"):
        if family in families:
            return family
    return "Segoe UI"


class UnicodeTextEdit(QPlainTextEdit):
    """Used for message/recipient boxes. objectName MessageInput
    switches on the glowing neon text color defined in theme.py, and
    attach_focus_glow gives the whole box a soft outer glow while it
    has focus (a real per-character text glow isn't something Qt style
    sheets can do -- QSS has no text-shadow -- so the box's own glow
    plus the neon fill color is the closest faithful approximation)."""
    def __init__(self, parent=None, glow_color=None):
        super().__init__(parent)
        self.setObjectName("MessageInput")
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.setLayoutDirection(Qt.LeftToRight)
        self.setAcceptDrops(True)
        f = QFont()
        families = get_font_families()
        if families:
            f.setFamilies(families)
        f.setPointSize(11)
        self.setFont(f)
        attach_focus_glow(self, glow_color or COLORS["message_glow"])
