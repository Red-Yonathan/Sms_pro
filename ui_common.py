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
import math

from PySide6.QtCore import Qt, QEvent, QObject, Property, QPropertyAnimation, QEasingCurve, QUrl, Signal, QPointF, QRectF, QTimer, QSize
from PySide6.QtGui import QColor, QFont, QFontDatabase, QDesktopServices, QPainter, QPen, QBrush, QLinearGradient, QPainterPath, QTextCursor, QImage
from PySide6.QtWidgets import (
    QPushButton, QFrame, QPlainTextEdit, QTextEdit, QGraphicsDropShadowEffect,
    QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel,
)


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
    def __init__(self, text, checked=False, parent=None, checkable=True):
        super().__init__(text, parent)
        self.setObjectName("NavButton")
        self.setCheckable(checkable)
        self.setChecked(checked if checkable else False)
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
    """Clean, high-performance Unicode text editor for message and recipient boxes.
    Renders crisp text using styling from theme.py (message_text, message_bg, message_glow).
    Runs with zero background timers or CPU rasterization overhead to ensure zero interference when sending.
    """
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



class SwitchToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self._pos = 1.0 if self._checked else 0.0
        self.setFixedSize(68, 30)
        self.setCursor(Qt.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"position", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._update_glow()

    def get_position(self):
        return self._pos

    def set_position(self, pos):
        self._pos = float(pos)
        self.update()

    position = Property(float, get_position, set_position)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked != bool(checked):
            self._checked = bool(checked)
            self._anim.stop()
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(1.0 if self._checked else 0.0)
            self._anim.start()
            self._update_glow()
            self.toggled.emit(self._checked)

    def _update_glow(self):
        color = "#00E5FF" if self._checked else "#FF3366"
        apply_glow(self, color, blur_radius=14, offset=(0, 0))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        radius = h / 2.0

        # Background track: interpolate between Red (#FF3366) and Cyan (#00E5FF)
        c_off = QColor(255, 51, 102)
        c_on = QColor(0, 229, 255)
        r = int(c_off.red() * (1 - self._pos) + c_on.red() * self._pos)
        g = int(c_off.green() * (1 - self._pos) + c_on.green() * self._pos)
        b = int(c_off.blue() * (1 - self._pos) + c_on.blue() * self._pos)
        track_color = QColor(r, g, b, 230)

        painter.setPen(QPen(QColor(r, g, b), 1.5))
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        # Draw "ON" or "OFF" text inside the track
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        if self._pos > 0.5:
            painter.setPen(QColor(3, 7, 18))  # Dark text on glowing cyan
            painter.drawText(QRectF(6, 0, w - h, h), Qt.AlignCenter, "ON")
        else:
            painter.setPen(QColor(255, 255, 255))  # White text on red
            painter.drawText(QRectF(h - 6, 0, w - h, h), Qt.AlignCenter, "OFF")

        # Thumb (circle slider)
        thumb_size = h - 6
        thumb_x = 3 + (w - h) * self._pos
        thumb_y = 3
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_size, thumb_size))
        painter.end()


class ShiningBrandLogo(QWidget):
    """Brand badge displaying initials 'SB' with golden metallic gradient
    and an animated shining specular light sweep running periodically across it.
    """
    def __init__(self, text="SB", parent=None):
        super().__init__(parent)
        self.text = text
        self.setFixedSize(46, 42)
        self._shine_pos = -0.5

        self._anim = QPropertyAnimation(self, b"shinePosition", self)
        self._anim.setDuration(950)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

        self._sweep_timer = QTimer(self)
        self._sweep_timer.setInterval(3400)
        self._sweep_timer.timeout.connect(self._trigger_sweep)
        self._sweep_timer.start()

        apply_glow(self, "#FFB300", blur_radius=20, offset=(0, 0))

    def get_shine_position(self):
        return self._shine_pos

    def set_shine_position(self, pos):
        self._shine_pos = float(pos)
        self.update()

    shinePosition = Property(float, get_shine_position, set_shine_position)

    def _trigger_sweep(self):
        self._anim.stop()
        self._anim.setStartValue(-0.5)
        self._anim.setEndValue(1.5)
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(2, 2, w - 4, h - 4)
        radius = 9.0

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(path)

        # Metallic golden gradient background
        bg_grad = QLinearGradient(0, 0, w, h)
        bg_grad.setColorAt(0.0, QColor(255, 236, 179))
        bg_grad.setColorAt(0.35, QColor(255, 193, 7))
        bg_grad.setColorAt(0.70, QColor(255, 152, 0))
        bg_grad.setColorAt(1.0, QColor(230, 81, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg_grad))
        painter.drawRoundedRect(rect, radius, radius)

        # Inner border
        painter.setPen(QPen(QColor(255, 248, 225, 200), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(3, 3, w - 6, h - 6), radius - 1, radius - 1)

        # Draw "SB" text centered
        painter.setFont(QFont("Arial", 14, QFont.Black))
        painter.setPen(QColor(10, 14, 22))  # Deep obsidian
        painter.drawText(rect, Qt.AlignCenter, self.text)

        # Animated specular shine beam
        if -0.4 <= self._shine_pos <= 1.4:
            center_x = self._shine_pos * w
            beam_w = w * 0.45
            shine = QLinearGradient(center_x - beam_w, 0, center_x + beam_w, h)
            shine.setColorAt(0.0, QColor(255, 255, 255, 0))
            shine.setColorAt(0.40, QColor(255, 255, 255, 120))
            shine.setColorAt(0.50, QColor(255, 255, 255, 235))
            shine.setColorAt(0.60, QColor(255, 255, 255, 120))
            shine.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(QBrush(shine))
            painter.setPen(Qt.NoPen)
            painter.drawRect(self.rect())

        painter.end()


def paint_window_background(widget, painter, wallpaper_pixmap=None, dim_alpha=95):
    """Draws wallpaper scaled to fill if present, or solid theme background."""
    w, h = widget.width(), widget.height()
    if wallpaper_pixmap and not wallpaper_pixmap.isNull():
        scaled = wallpaper_pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = (scaled.width() - w) // 2
        y = (scaled.height() - h) // 2
        painter.drawPixmap(0, 0, scaled, x, y, w, h)
        painter.fillRect(widget.rect(), QColor(2, 4, 10, dim_alpha))
    else:
        painter.fillRect(widget.rect(), QColor(COLORS["bg"]))


class FileRowWidget(QFrame):
    """Custom file row widget representing a tracked file.
    When complete (100% sent / done), the file frame turns FULL glowing orange
    with vivid glowing neon borders and drop shadow aura.
    While in progress, it paints an advancing glowing orange fill in its area.
    Supports 'Select all' and 'Select unsent' mode toggles when checked with unsent numbers.
    """
    def __init__(self, display_name, meta_text, checked, tooltip, on_toggle, on_delete,
                 delete_tooltip=None, done=False, progress_pct=0.0,
                 has_unsent=False, send_mode="all", on_mode_change=None, parent=None):
        super().__init__(parent)
        self.setObjectName("FileRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.display_name = display_name
        self.meta_text = meta_text
        self.is_done = bool(done)
        self.progress_pct = float(progress_pct)
        self.has_unsent = bool(has_unsent)
        self.send_mode = send_mode or "all"
        self.on_mode_change = on_mode_change
        self.on_toggle_cb = on_toggle

        if self.is_done and self.progress_pct < 1.0:
            self.progress_pct = 1.0
        self.setProperty("done", "true" if (self.is_done or self.progress_pct >= 1.0) else "false")

        r = QHBoxLayout(self)
        r.setContentsMargins(10, 4, 10, 4)
        r.setSpacing(8)

        self.check = QCheckBox()
        self.check.setChecked(bool(checked))
        self.check.toggled.connect(self._handle_toggle)
        r.addWidget(self.check)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        self.filename = QLabel(display_name)
        self.filename.setObjectName("FileName")
        self.filename.setToolTip(tooltip)
        self.meta = QLabel(meta_text)
        self.meta.setObjectName("FileMeta")
        text_layout.addWidget(self.filename)
        text_layout.addWidget(self.meta)
        r.addLayout(text_layout, 1)

        # Mode buttons ("Select all" / "Select unsent")
        self.mode_container = QWidget()
        mc_layout = QHBoxLayout(self.mode_container)
        mc_layout.setContentsMargins(0, 0, 0, 0)
        mc_layout.setSpacing(4)

        self.btn_select_all = QPushButton("Select all")
        self.btn_select_all.setFixedHeight(24)
        self.btn_select_all.clicked.connect(lambda: self.set_send_mode("all"))

        self.btn_select_unsent = QPushButton("Select unsent")
        self.btn_select_unsent.setFixedHeight(24)
        self.btn_select_unsent.clicked.connect(lambda: self.set_send_mode("unsent"))

        mc_layout.addWidget(self.btn_select_all)
        mc_layout.addWidget(self.btn_select_unsent)
        r.addWidget(self.mode_container)

        self._update_mode_buttons()
        self._update_mode_visibility()

        self.delete_btn = QPushButton("X")
        self.delete_btn.setObjectName("DeleteButton")
        self.delete_btn.setFixedSize(28, 28)
        self.delete_btn.setToolTip(delete_tooltip or f"Remove {display_name}")
        self.delete_btn.clicked.connect(on_delete)
        r.addWidget(self.delete_btn)

        if self.is_done or self.progress_pct >= 1.0:
            self._apply_glowing_orange_effects(True)

    def _handle_toggle(self, state):
        self._update_mode_visibility()
        if self.on_toggle_cb:
            self.on_toggle_cb(state)

    def set_has_unsent(self, has_unsent):
        self.has_unsent = bool(has_unsent)
        self._update_mode_visibility()

    def _update_mode_visibility(self):
        show = self.check.isChecked() and self.has_unsent and not self.is_done
        self.mode_container.setVisible(show)

    def set_send_mode(self, mode):
        self.send_mode = mode
        self._update_mode_buttons()
        if self.on_mode_change:
            self.on_mode_change(self.send_mode)

    def _update_mode_buttons(self):
        filled_style_all = (
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00F0FF, stop:1 #00B0FF); "
            "color: #030712; font-weight: 750; border-radius: 5px; padding: 2px 10px; border: none; font-size: 11px;"
        )
        filled_style_unsent = (
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00FF9D, stop:1 #00D680); "
            "color: #030712; font-weight: 750; border-radius: 5px; padding: 2px 10px; border: none; font-size: 11px;"
        )
        ghost_style = (
            "background: rgba(16, 26, 44, 0.70); color: #8BA3B8; "
            "border: 1px solid rgba(0, 240, 255, 0.25); border-radius: 5px; padding: 2px 10px; font-size: 11px;"
        )
        if self.send_mode == "unsent":
            self.btn_select_unsent.setStyleSheet(filled_style_unsent)
            self.btn_select_all.setStyleSheet(ghost_style)
        else:
            self.btn_select_all.setStyleSheet(filled_style_all)
            self.btn_select_unsent.setStyleSheet(ghost_style)

    def _apply_glowing_orange_effects(self, enable):
        if enable:
            self.filename.setStyleSheet("color: #FFFFFF; font-weight: 750;")
            self.meta.setStyleSheet("color: #E8FFF4; font-weight: 600;")
            self.mode_container.hide()
        else:
            self.filename.setStyleSheet("")
            self.meta.setStyleSheet("")
            self._update_mode_visibility()

    def set_progress(self, pct, done=None):
        new_done = bool(done) if done is not None else (pct >= 1.0)
        self.progress_pct = max(0.0, min(1.0, float(pct)))
        if new_done:
            self.progress_pct = 1.0

        if new_done != getattr(self, "_last_done_state", None):
            self._last_done_state = new_done
            self.is_done = new_done
            self.setProperty("done", "true" if new_done else "false")
            self._apply_glowing_orange_effects(new_done)
            self.style().unpolish(self)
            self.style().polish(self)

        self.update()

    def set_done(self, done, pct=None):
        self.set_progress(pct if pct is not None else (1.0 if done else 0.0), done=done)

    def paintEvent(self, event):
        super().paintEvent(event)
        if 0.0 < self.progress_pct < 1.0 and not self.is_done:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            r = self.rect()
            fill_w = max(4, int((r.width() - 4) * self.progress_pct))
            grad = QLinearGradient(0, 0, fill_w, 0)
            grad.setColorAt(0.0, QColor(0, 180, 105, 140))
            grad.setColorAt(0.5, QColor(0, 255, 157, 180))
            grad.setColorAt(1.0, QColor(0, 210, 125, 160))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(2, 2, fill_w, r.height() - 4, 6, 6)
            painter.end()


def build_file_row(display_name, meta_text, checked, tooltip, on_toggle, on_delete,
                   delete_tooltip=None, done=False, progress_pct=0.0,
                   has_unsent=False, send_mode="all", on_mode_change=None):
    """Shared tracked file row widget used by both Batch page and Projects workspace."""
    return FileRowWidget(
        display_name=display_name,
        meta_text=meta_text,
        checked=checked,
        tooltip=tooltip,
        on_toggle=on_toggle,
        on_delete=on_delete,
        delete_tooltip=delete_tooltip,
        done=done,
        progress_pct=progress_pct,
        has_unsent=has_unsent,
        send_mode=send_mode,
        on_mode_change=on_mode_change,
    )


def set_row_done(row, done, pct=None):
    """Turns a file row full glowing emerald green (finished/100%) or back to normal, live."""
    if hasattr(row, "set_done"):
        row.set_done(done, pct)
    else:
        row.setProperty("done", "true" if done else "false")
        row.style().unpolish(row)
        row.style().polish(row)
        row.update()


def open_folder(path):
    """Opens a folder in the OS file manager (Explorer on Windows)."""
    import os
    os.makedirs(path, exist_ok=True)
    return QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))
