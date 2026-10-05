import sys
import os
import re
import math
import time
from datetime import datetime

# ---- import-order fix (Windows / Python 3.12) --------------------------------
# shiboken6 (pulled in by PySide6) inspects every module imported after it.
# python-dateutil (imported by pandas) uses six.moves, and that inspection dies
# with: AttributeError: '_SixMetaPathImporter' object has no attribute '_path'.
# Two-part fix: (1) import pandas BEFORE PySide6 so six/dateutil are already
# loaded, and (2) give six's importer the attribute shiboken looks for.
import pandas  # noqa: F401  (must stay ABOVE every PySide6 import)
try:
    import six
    if not hasattr(six._SixMetaPathImporter, "_path"):
        six._SixMetaPathImporter._path = []
except Exception:
    pass

from dotenv import load_dotenv
from PySide6.QtCore import (
    Qt, QThread, Signal, QSize, QTimer, QAbstractAnimation, QPointF,
    QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QFont, QColor, QPainter, QBrush, QPen, QPixmap, QIcon,
    QRadialGradient, QLinearGradient,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QListWidget, QListWidgetItem,
    QCheckBox, QProgressBar, QMessageBox, QFrame, QScrollArea,
    QPlainTextEdit, QLineEdit, QStackedWidget, QDialog, QFormLayout,
    QToolButton, QSpinBox, QAbstractItemView, QGraphicsDropShadowEffect,
    QStatusBar, QSizeGrip, QSizePolicy,
)

from theme import COLORS, STYLESHEET
from sender import SendingWorker
from phone_utils import SUPPORTED_EXTENSIONS, parse_manual_phones, parse_phone_file
from file_loader import FileLoadWorker
from excel_dialog import resolve_excel_columns
from ui_common import (
    Card, apply_glow, attach_focus_glow, enable_dark_titlebar,
    AnimatedNavButton, UnicodeTextEdit, get_font_families, choose_font,
    build_file_row, set_row_done, SwitchToggle, ShiningBrandLogo, paint_window_background,
    open_folder,
)
from progress_panel import LiveProgressPanel
from projects import ProjectManager
from project_ui import ProjectsPage
from wallpaper import WallpaperManager
import mica
from mica import apply_mica, native_blur_wanted
from error_logger import setup_error_logger, get_error_logger

# ==============================================================================
# GLOBAL CRASH PROTECTION
# ==============================================================================
def global_exception_handler(exctype, value, traceback):
    if issubclass(exctype, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(exctype, value, traceback)
        return
    error_msg = f"Application Error:\n{exctype.__name__}: {value}"
    print(error_msg, file=sys.stderr)
    try:
        get_error_logger().error("Uncaught exception: %s: %s", exctype.__name__, value, exc_info=(exctype, value, traceback))
    except Exception:
        pass
    app = QApplication.instance()
    if app:
        QMessageBox.critical(None, "Fatal Error", error_msg)

sys.excepthook = global_exception_handler

# Darkening laid over a chosen wallpaper so text stays readable (0 = none, 255 = solid black).
WALLPAPER_DIM_ALPHA = 95
WINDOW_TINT_ALPHA = 230  # 0-255; 230 = ~90% opaque. Lower = more blur visible.
APP_NAME = "SmsBlast Pro"
APP_VERSION = "4.0"

if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE_DIR = getattr(sys, "_MEIPASS", SCRIPT_DIR)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = SCRIPT_DIR

ENV_PATH = os.path.join(SCRIPT_DIR, ".env")

# Seed default .env if not found in SCRIPT_DIR
if not os.path.exists(ENV_PATH):
    bundled_env = os.path.join(BUNDLE_DIR, ".env")
    if os.path.exists(bundled_env):
        try:
            import shutil
            shutil.copyfile(bundled_env, ENV_PATH)
        except Exception:
            pass
    if not os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write('SMS_API_URL="http://197.156.127.150:8020/send-sms"\nSMS_API_KEY=""\nMANUAL_CONCURRENCY="5"\nBATCH_CONCURRENCY="30"\nTEST_ON_STARTUP="False"\n')
        except Exception:
            pass

load_dotenv(ENV_PATH, override=True)

# Seed default Wallpapers if folder is empty
try:
    wp_target = os.path.join(SCRIPT_DIR, "Wallpaper")
    wp_bundled = os.path.join(BUNDLE_DIR, "Wallpaper")
    if os.path.exists(wp_bundled) and os.path.abspath(wp_target) != os.path.abspath(wp_bundled):
        os.makedirs(wp_target, exist_ok=True)
        for wp_item in os.listdir(wp_bundled):
            src_wp = os.path.join(wp_bundled, wp_item)
            dst_wp = os.path.join(wp_target, wp_item)
            if os.path.isfile(src_wp) and not os.path.exists(dst_wp):
                import shutil
                try:
                    shutil.copyfile(src_wp, dst_wp)
                except Exception:
                    pass
except Exception:
    pass

ERROR_LOGGER, ERROR_LOG_PATH = setup_error_logger(SCRIPT_DIR)


def get_app_icon():
    """Returns application QIcon from ico or png file, or empty QIcon."""
    candidates = [
        os.path.join(SCRIPT_DIR, "app_icon.ico"),
        os.path.join(BUNDLE_DIR, "app_icon.ico"),
        os.path.join(SCRIPT_DIR, "app_icon.png"),
        os.path.join(BUNDLE_DIR, "app_icon.png"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return QIcon(p)
    return QIcon()



# ==============================================================================
# FILE LOADER WORKER
# ==============================================================================
# FileLoadWorker now lives in file_loader.py (shared with project_ui.py)


# ==============================================================================
# SETTINGS DIALOG (API + performance + wallpaper)
# ==============================================================================
# ==============================================================================
# SETTINGS DIALOG (API + performance + wallpaper)
# ==============================================================================
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        icon = get_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)
        self.setWindowTitle("⚙️ Settings & Configuration - SmsBlast Pro")
        self.setModal(True)
        self.resize(760, 840)
        self.setStyleSheet(parent.styleSheet() if parent else "")
        enable_dark_titlebar(int(self.winId()))

        self.wallpaper_manager = getattr(parent, "wallpaper_manager", None) or WallpaperManager(SCRIPT_DIR)
        self._wallpaper_pixmap = None
        self.reload_wallpaper()
        self.wallpaper_manager.add_listener(self.reload_wallpaper)

        self.build()

    def reload_wallpaper(self):
        if self.wallpaper_manager:
            path = self.wallpaper_manager.get_current()
            self._wallpaper_pixmap = QPixmap(path) if path else None
        else:
            self._wallpaper_pixmap = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        paint_window_background(self, painter, self._wallpaper_pixmap, 105)
        painter.end()
        super().paintEvent(event)

    def closeEvent(self, event):
        if self.wallpaper_manager:
            self.wallpaper_manager.remove_listener(self.reload_wallpaper)
        super().closeEvent(event)

    def build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.setSpacing(16)

        title = QLabel("⚙️ Settings & Configuration")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("SettingsBody")
        body.setAttribute(Qt.WA_StyledBackground, True)
        blay = QVBoxLayout(body)
        blay.setContentsMargins(0, 0, 0, 0)
        blay.setSpacing(16)

        # -- API ---------------------------------------------------- #
        api_group = QFrame()
        api_group.setObjectName("Card")
        api_layout = QFormLayout(api_group)
        api_layout.setContentsMargins(20, 20, 20, 20)
        api_layout.setVerticalSpacing(16)

        self.url = QLineEdit()
        self.url.setPlaceholderText("http://example.com/send-sms")
        attach_focus_glow(self.url)
        api_layout.addRow("SMS API URL", self.url)

        key_row = QWidget()
        row = QHBoxLayout(key_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("SMS API key")
        attach_focus_glow(self.key)
        show = QToolButton()
        show.setText("Show")
        show.clicked.connect(lambda: self.toggle_key(show))
        row.addWidget(self.key, 1)
        row.addWidget(show)
        api_layout.addRow("API key", key_row)

        test_btn = QPushButton("⚡ Test API Connection")
        test_btn.setObjectName("SecondaryButton")
        test_btn.clicked.connect(self.run_test_api)
        api_layout.addRow("", test_btn)

        # Test on opening App toggle row
        startup_test_row = QHBoxLayout()
        startup_text_col = QVBoxLayout()
        st_title = QLabel("Test on opening the App")
        st_title.setObjectName("SectionTitle")
        st_sub = QLabel("Run API test automatically when opening the app")
        st_sub.setObjectName("TinyMuted")
        startup_text_col.addWidget(st_title)
        startup_text_col.addWidget(st_sub)
        startup_test_row.addLayout(startup_text_col, 1)

        cur_startup = os.getenv("TEST_ON_STARTUP", "False").strip().lower() in ("1", "true", "yes")
        self.test_on_startup_toggle = SwitchToggle(checked=cur_startup)
        startup_test_row.addWidget(self.test_on_startup_toggle)
        api_layout.addRow("", startup_test_row)

        blay.addWidget(api_group)

        # -- Wallpaper (Prominently placed with live thumbnail preview) -- #
        wall_group = QFrame()
        wall_group.setObjectName("Card")
        wall_layout = QVBoxLayout(wall_group)
        wall_layout.setContentsMargins(20, 20, 20, 20)
        wall_layout.setSpacing(12)

        wall_header = QHBoxLayout()
        wall_title = QLabel("🖼️ Background Wallpaper")
        wall_title.setObjectName("SectionTitle")
        wall_header.addWidget(wall_title)
        wall_header.addStretch()
        wall_layout.addLayout(wall_header)

        wall_desc = QLabel(
            "Select an image from your computer to use as wallpaper. It will be copied into the "
            "Wallpaper folder and applied across the entire app interface."
        )
        wall_desc.setObjectName("Muted")
        wall_desc.setWordWrap(True)
        wall_layout.addWidget(wall_desc)

        # Preview and status details
        wall_preview_row = QHBoxLayout()
        wall_preview_row.setSpacing(16)

        self.wallpaper_preview = QLabel()
        self.wallpaper_preview.setFixedSize(160, 96)
        self.wallpaper_preview.setStyleSheet(
            "background: rgba(8, 14, 26, 0.70); border: 1.5px solid rgba(0, 240, 255, 0.40); "
            "border-radius: 8px; color: #8BA3B8; font-size: 11px;"
        )
        self.wallpaper_preview.setAlignment(Qt.AlignCenter)
        wall_preview_row.addWidget(self.wallpaper_preview)

        wall_info_col = QVBoxLayout()
        wall_info_col.setSpacing(6)
        self.wallpaper_status = QLabel()
        self.wallpaper_status.setStyleSheet("font-weight: 750; color: #F0F9FF; font-size: 13px;")
        self.wallpaper_status.setWordWrap(True)
        wall_info_col.addWidget(self.wallpaper_status)

        self.wallpaper_path_lbl = QLabel()
        self.wallpaper_path_lbl.setObjectName("TinyMuted")
        self.wallpaper_path_lbl.setWordWrap(True)
        wall_info_col.addWidget(self.wallpaper_path_lbl)
        wall_info_col.addStretch()

        wall_btns = QHBoxLayout()
        wall_btns.setSpacing(8)
        choose_wall_btn = QPushButton("📁 Choose Wallpaper...")
        choose_wall_btn.setObjectName("PrimaryButton")
        apply_glow(choose_wall_btn, COLORS["accent"], blur_radius=12, offset=(0, 1))
        choose_wall_btn.clicked.connect(self.choose_wallpaper)

        open_wall_folder_btn = QPushButton("📂 Open Folder")
        open_wall_folder_btn.setToolTip("Open the Wallpaper folder in Windows Explorer")
        open_wall_folder_btn.clicked.connect(lambda: open_folder(self.wallpaper_manager.folder))

        reset_wall_btn = QPushButton("Reset to Default")
        reset_wall_btn.setObjectName("DangerButton")
        reset_wall_btn.clicked.connect(self.reset_wallpaper)

        wall_btns.addWidget(choose_wall_btn)
        wall_btns.addWidget(open_wall_folder_btn)
        wall_btns.addWidget(reset_wall_btn)
        wall_btns.addStretch()
        wall_info_col.addLayout(wall_btns)

        wall_preview_row.addLayout(wall_info_col, 1)
        wall_layout.addLayout(wall_preview_row)

        blay.addWidget(wall_group)
        self._refresh_wallpaper_status()

        # -- Performance (concurrency lives HERE only) --------------- #
        perf_group = QFrame()
        perf_group.setObjectName("Card")
        perf_layout = QFormLayout(perf_group)
        perf_layout.setContentsMargins(20, 20, 20, 20)
        perf_layout.setVerticalSpacing(16)

        perf_title = QLabel("Performance (Concurrency)")
        perf_title.setObjectName("SectionTitle")
        perf_layout.addRow(perf_title)

        self.manual_concurrency = QSpinBox()
        self.manual_concurrency.setRange(1, 50)
        self.manual_concurrency.setValue(int(os.getenv("MANUAL_CONCURRENCY", "5")))
        attach_focus_glow(self.manual_concurrency)
        perf_layout.addRow("Manual Send Concurrency", self.manual_concurrency)

        self.batch_concurrency = QSpinBox()
        self.batch_concurrency.setRange(1, 100)
        self.batch_concurrency.setValue(int(os.getenv("BATCH_CONCURRENCY", "30")))
        attach_focus_glow(self.batch_concurrency)
        perf_layout.addRow("Batch / Project Send Concurrency", self.batch_concurrency)
        blay.addWidget(perf_group)

        note = QLabel('Header: prepaid-api-key | JSON body: {"to": "+251...", "message": "..."}')
        note.setObjectName("CodeNote")
        blay.addWidget(note)
        blay.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        grip = QSizeGrip(self)
        buttons.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignLeft)
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save settings")
        save.setObjectName("PrimaryButton")
        apply_glow(save, COLORS["accent"], blur_radius=14, offset=(0, 2))
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _refresh_wallpaper_status(self):
        current = self.wallpaper_manager.get_current() if self.wallpaper_manager else None
        if current and os.path.exists(current):
            name = os.path.basename(current)
            self.wallpaper_status.setText(f"Active Wallpaper: {name}")
            self.wallpaper_path_lbl.setText(current)
            pm = QPixmap(current)
            if not pm.isNull():
                thumb = pm.scaled(156, 92, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                self.wallpaper_preview.setPixmap(thumb)
            else:
                self.wallpaper_preview.setText("Image loaded")
        else:
            self.wallpaper_status.setText("No custom wallpaper set")
            self.wallpaper_path_lbl.setText("Using dynamic animated cyber blobs / native mica backdrop")
            self.wallpaper_preview.clear()
            self.wallpaper_preview.setText("✨ Animated\nBackdrop")

    def choose_wallpaper(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose wallpaper", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        try:
            self.wallpaper_manager.set_wallpaper(path)
            self.reload_wallpaper()
            self._refresh_wallpaper_status()
            QMessageBox.information(
                self, "Wallpaper Applied",
                f"Wallpaper was copied to the Wallpaper folder and applied everywhere:\n\n{os.path.basename(path)}"
            )
        except Exception as exc:
            ERROR_LOGGER.error("Failed setting wallpaper: %s", exc)
            QMessageBox.critical(self, "Wallpaper failed", str(exc))

    def reset_wallpaper(self):
        self.wallpaper_manager.reset()
        self.reload_wallpaper()
        self._refresh_wallpaper_status()


    def toggle_key(self, button):
        if self.key.echoMode() == QLineEdit.Password:
            self.key.setEchoMode(QLineEdit.Normal)
            button.setText("Hide")
        else:
            self.key.setEchoMode(QLineEdit.Password)
            button.setText("Show")

    def load_values(self, url, key):
        self.url.setText(url or "")
        self.key.setText(key or "")

    def run_test_api(self):
        from api_test_dialog import ApiTestDialog
        dialog = ApiTestDialog(self, url=self.url.text().strip(), key=self.key.text().strip())
        dialog.exec()

    def save(self):
        url = self.url.text().strip()
        key = self.key.text().strip()
        if not url or not key:
            QMessageBox.warning(self, "Missing settings", "Enter both the URL and API key.")
            return
        try:
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write(f'SMS_API_URL="{url.replace(chr(34), chr(92)+chr(34))}"\n')
                f.write(f'SMS_API_KEY="{key.replace(chr(34), chr(92)+chr(34))}"\n')
                f.write(f'MANUAL_CONCURRENCY="{self.manual_concurrency.value()}"\n')
                f.write(f'BATCH_CONCURRENCY="{self.batch_concurrency.value()}"\n')
                is_on = "True" if self.test_on_startup_toggle.isChecked() else "False"
                f.write(f'TEST_ON_STARTUP="{is_on}"\n')
            load_dotenv(ENV_PATH, override=True)
            self.accept()
        except Exception as exc:
            ERROR_LOGGER.error("Failed saving settings: %s", exc)
            QMessageBox.critical(self, "Save failed", str(exc))


# ==============================================================================
# MAIN WINDOW
# ==============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.segments = {}
        self.active_workers = []
        self.loader = None
        self.excel_for_all_column = None
        self._t = 0.0
        self._pulses = {}
        self._backdrop = None  # set by main() after apply_mica()
        self._batch_interrupted = False
        if native_blur_wanted():
            # Required for the OS blur to show through (see mica.py).
            self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.wallpaper_manager = WallpaperManager(SCRIPT_DIR)
        self.project_manager = ProjectManager(SCRIPT_DIR)
        self._wallpaper_pixmap = None
        self.reload_wallpaper()
        self.wallpaper_manager.add_listener(self.reload_wallpaper)

        self._bg_timer = QTimer(self)
        self._bg_timer.setInterval(40)
        self._bg_timer.timeout.connect(self._animate_backdrop)
        self._bg_timer.start()
        self._blobs = [
            (QColor(0, 240, 255, 34), 0.82, 0.10, 640, 70, 0.90),
            (QColor(37, 99, 255, 30), 0.08, 0.78, 600, 80, 0.60),
            (QColor(112, 0, 255, 26), 0.72, 0.95, 560, 60, 0.75),
            (QColor(0, 160, 255, 20), 0.35, 0.45, 720, 45, 0.45),
        ]
        app_icon = get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        self.setWindowTitle(f"⚡ {APP_NAME} - {APP_VERSION}")
        self.setMinimumSize(1180, 760)
        self.resize(1440, 900)

        self.build_ui()
        self.apply_style()
        self.refresh_api_status()
        self.update_file_list_height()

        # Check if "Test on opening the App" is enabled
        startup_test = os.getenv("TEST_ON_STARTUP", "False").strip().lower() in ("1", "true", "yes")
        if startup_test:
            QTimer.singleShot(700, lambda: self.open_test_api_dialog(auto_start=True))

    def set_backdrop(self, description):
        self._backdrop = description
        if hasattr(self, "backdrop_label"):
            self.backdrop_label.setText(f"Backdrop: {description or 'none (opaque)'}")
        self.update()

    def reload_wallpaper(self):
        path = self.wallpaper_manager.get_current()
        self._wallpaper_pixmap = QPixmap(path) if path else None
        self.update()

    # -- animated / painted background -------------------------------- #
    def _animate_backdrop(self):
        self._t += 0.045
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self._wallpaper_pixmap and not self._wallpaper_pixmap.isNull():
            scaled = self._wallpaper_pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (scaled.width() - w) // 2
            y = (scaled.height() - h) // 2
            painter.drawPixmap(0, 0, scaled, x, y, w, h)
            painter.fillRect(self.rect(), QColor(2, 4, 10, WALLPAPER_DIM_ALPHA))
        else:
            if self._backdrop:
                # Native blur is live: paint ONLY a translucent tint so the
                # blur shows through. Alpha 230/255 ~= 90% opaque. Lower
                # WINDOW_TINT_ALPHA for more visible blur.
                tint = QColor(2, 4, 10, WINDOW_TINT_ALPHA)
                painter.setCompositionMode(QPainter.CompositionMode_Source)
                painter.fillRect(self.rect(), tint)
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            else:
                painter.fillRect(self.rect(), QColor(COLORS["bg"]))

        max_r = max(w, h) * 0.55
        for i, (color, fx, fy, radius, amp, speed) in enumerate(self._blobs):
            x = w * fx + math.sin(self._t * speed + i * 1.7) * amp
            y = h * fy + math.cos(self._t * speed * 0.8 + i * 2.3) * amp
            r = min(radius, max_r)
            grad = QRadialGradient(QPointF(x, y), r)
            grad.setColorAt(0.0, color)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillRect(self.rect(), QBrush(grad))
        line_grad = QLinearGradient(QPointF(0, 0), QPointF(w, 0))
        line_grad.setColorAt(0.0, QColor(0, 240, 255, 0))
        line_grad.setColorAt(0.5, QColor(0, 240, 255, 70))
        line_grad.setColorAt(1.0, QColor(112, 0, 255, 0))
        painter.fillRect(0, 0, w, 1, QBrush(line_grad))
        painter.end()
        super().paintEvent(event)

    def start_pulse(self, widget, color_hex=None, min_blur=12, max_blur=36, duration=650):
        color_hex = color_hex or COLORS["accent"]
        self.stop_pulse(widget)
        effect = QGraphicsDropShadowEffect(widget)
        c = QColor(color_hex)
        c.setAlpha(170)
        effect.setColor(c)
        effect.setOffset(0, 0)
        effect.setBlurRadius(min_blur)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"blurRadius", self)
        anim.setDuration(duration)
        anim.setStartValue(min_blur)
        anim.setEndValue(max_blur)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.finished.connect(lambda a=anim: self._reverse_pulse(a))
        self._pulses[widget] = (anim, effect)
        anim.start()

    def _reverse_pulse(self, anim):
        if anim.direction() == QAbstractAnimation.Forward:
            anim.setDirection(QAbstractAnimation.Backward)
        else:
            anim.setDirection(QAbstractAnimation.Forward)
        anim.start()

    def stop_pulse(self, widget):
        entry = self._pulses.pop(widget, None)
        if entry:
            anim, _ = entry
            anim.stop()
            widget.setGraphicsEffect(None)

    def apply_style(self):
        styled_stylesheet = STYLESHEET.format(**COLORS)
        self.setStyleSheet(styled_stylesheet)

    # -- layout ---------------------------------------------------------#
    def build_ui(self):
        root = QWidget()
        root.setObjectName("CentralWidget")
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self.build_sidebar())
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.build_topbar())
        self.stack = QStackedWidget()
        self.stack.addWidget(self.build_manual_page())
        self.stack.addWidget(self.build_batch_page())
        self.projects_page = ProjectsPage(self.project_manager, self)
        self.stack.addWidget(self.projects_page)
        right_layout.addWidget(self.stack, 1)
        main.addWidget(right, 1)

        # Explicit, easy-to-grab resize handle in the bottom-right
        # corner -- the window is still edge/corner resizable natively,
        # but a visible grip is much easier to hit precisely.
        status = QStatusBar()
        status.setFixedHeight(18)
        status.setSizeGripEnabled(True)
        self.setStatusBar(status)

    def build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(248)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(5)
        brand = QWidget()
        brand_row = QHBoxLayout(brand)
        brand_row.setContentsMargins(2, 0, 2, 0)
        self.brand_logo = ShiningBrandLogo("SB")
        brand_text = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("BrandTitle")
        title.setStyleSheet("font-size: 19px; font-weight: 850; color: #FFE082; letter-spacing: -0.3px;")
        sub = QLabel("SMS delivery console")
        sub.setObjectName("BrandSub")
        sub.setStyleSheet("font-size: 11px; color: #FFB74D; font-weight: 600;")
        brand_text.addWidget(title)
        brand_text.addWidget(sub)
        brand_row.addWidget(self.brand_logo)
        brand_row.addSpacing(10)
        brand_row.addLayout(brand_text)
        layout.addWidget(brand)
        layout.addSpacing(28)
        self.manual_nav = self.nav_button("Manual Send", True)
        self.batch_nav = self.nav_button("Batch Send", False)
        self.projects_nav = self.nav_button("Projects", False)
        self.manual_nav.clicked.connect(lambda: self.switch_page(0))
        self.batch_nav.clicked.connect(lambda: self.switch_page(1))
        self.projects_nav.clicked.connect(lambda: self.switch_page(2))
        layout.addWidget(self.manual_nav)
        layout.addWidget(self.batch_nav)
        layout.addWidget(self.projects_nav)
        layout.addSpacing(12)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{COLORS['border']};")
        layout.addWidget(line)
        layout.addSpacing(10)
        settings = self.nav_button("Settings", False, checkable=False)
        settings.clicked.connect(self.open_settings)
        layout.addWidget(settings)
        layout.addSpacing(6)
        test_api = self.nav_button("⚡ Test API", False, checkable=False)
        test_api.clicked.connect(lambda: self.open_test_api_dialog(auto_start=False))
        layout.addWidget(test_api)
        layout.addStretch()
        self.api_status = QLabel("Checking API")
        self.api_status.setObjectName("Status")
        layout.addWidget(self.api_status)
        return sidebar

    def nav_button(self, text, checked, checkable=True):
        return AnimatedNavButton(text, checked, checkable=checkable)

    def build_topbar(self):
        top = QFrame()
        top.setObjectName("Topbar")
        top.setFixedHeight(68)
        row = QHBoxLayout(top)
        row.setContentsMargins(28, 0, 28, 0)
        self.breadcrumb = QLabel("Manual Send")
        self.breadcrumb.setObjectName("Muted")
        row.addWidget(self.breadcrumb)
        row.addStretch()
        self.backdrop_label = QLabel("Backdrop: none (opaque)")
        self.backdrop_label.setObjectName("TinyMuted")
        row.addWidget(self.backdrop_label)
        row.addSpacing(16)
        env = QLabel(f"ENV - {os.path.basename(ENV_PATH)}")
        env.setObjectName("TinyMuted")
        row.addWidget(env)
        return top

    def page(self, name):
        w = QWidget()
        w.setObjectName(name)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(30, 26, 30, 38)
        lay.setSpacing(18)
        return w, lay

    def scroll_page(self, w):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(w)
        return scroll

    def heading(self, title, subtitle):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        s = QLabel(subtitle)
        s.setObjectName("PageSubtitle")
        s.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(s)
        return w

    def stat_card(self, label):
        c = Card()
        c.setMinimumHeight(86)
        lay = QVBoxLayout(c)
        lay.setContentsMargins(16, 13, 16, 13)
        num = QLabel("0")
        num.setObjectName("StatNumber")
        text = QLabel(label)
        text.setObjectName("StatLabel")
        lay.addWidget(num)
        lay.addWidget(text)
        return c, num

    # -- Manual page ------------------------------------------------------#
    def build_manual_page(self):
        page, lay = self.page("ManualPage")
        lay.addWidget(self.heading("Manual SMS", "Write a message and send it to one or multiple recipients. Unicode and Amharic text are supported."))
        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.manual_recipient_card, self.manual_recipient_stat = self.stat_card("RECIPIENTS")
        self.manual_sent_card, self.manual_sent_stat = self.stat_card("SENT")
        self.manual_failed_card, self.manual_failed_stat = self.stat_card("FAILED")
        stats.addWidget(self.manual_recipient_card)
        stats.addWidget(self.manual_sent_card)
        stats.addWidget(self.manual_failed_card)
        lay.addLayout(stats)

        message = Card()
        ml = QVBoxLayout(message)
        ml.setContentsMargins(18, 18, 18, 18)
        ml.setSpacing(9)
        label = QLabel("Message")
        label.setObjectName("SectionTitle")
        ml.addWidget(label)
        self.manual_message = UnicodeTextEdit()
        self.manual_message.setPlaceholderText("Example: .....")
        self.manual_message.setMinimumHeight(120)
        self.manual_message.setMaximumHeight(180)
        self.manual_message.textChanged.connect(self.update_manual_message_count)
        ml.addWidget(self.manual_message)
        self.manual_char_count = QLabel("0 characters")
        self.manual_char_count.setObjectName("TinyMuted")
        self.manual_char_count.setAlignment(Qt.AlignRight)
        ml.addWidget(self.manual_char_count)
        lay.addWidget(message)

        recipients = Card()
        rl = QVBoxLayout(recipients)
        rl.setContentsMargins(18, 18, 18, 18)
        rl.setSpacing(9)
        rtitle = QLabel("Recipients")
        rtitle.setObjectName("SectionTitle")
        rl.addWidget(rtitle)
        self.manual_phones = UnicodeTextEdit()
        self.manual_phones.setPlaceholderText("0938296317\n0912345678, 0923456789\n+251938296317")
        self.manual_phones.setMinimumHeight(100)
        self.manual_phones.setMaximumHeight(150)
        self.manual_phones.textChanged.connect(self.update_manual_recipient_count)
        rl.addWidget(self.manual_phones)
        self.manual_phone_hint = QLabel("0 recipients detected")
        self.manual_phone_hint.setObjectName("TinyMuted")
        rl.addWidget(self.manual_phone_hint)
        lay.addWidget(recipients)

        controls = Card()
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(18, 14, 18, 14)
        self.manual_clear_btn = QPushButton("Clear Page")
        self.manual_clear_btn.setObjectName("DangerButton")
        self.manual_clear_btn.setMinimumHeight(44)
        self.manual_clear_btn.setMinimumWidth(120)
        self.manual_clear_btn.clicked.connect(self.clear_manual_page)
        cl.addWidget(self.manual_clear_btn)
        cl.addStretch()
        self.manual_send_btn = QPushButton("Send Messages ->")
        self.manual_send_btn.setObjectName("PrimaryButton")
        self.manual_send_btn.setMinimumHeight(44)
        self.manual_send_btn.setMinimumWidth(190)
        apply_glow(self.manual_send_btn, COLORS["accent"], blur_radius=14, offset=(0, 2))
        self.manual_send_btn.clicked.connect(self.start_manual_send)
        cl.addWidget(self.manual_send_btn)
        lay.addWidget(controls)

        self.manual_progress_panel = LiveProgressPanel()
        self.manual_progress_panel.interrupt_requested.connect(lambda name: self.interrupt_workers("manual", name))
        self.manual_progress_panel.interrupt_all_requested.connect(lambda: self.interrupt_workers("manual"))
        self.manual_progress_panel.pause_requested.connect(self._pause_manual)
        self.manual_progress_panel.resume_requested.connect(self._resume_manual)
        lay.addWidget(self.manual_progress_panel)

        activity = Card()
        al = QVBoxLayout(activity)
        al.setContentsMargins(18, 15, 18, 15)
        al.addWidget(QLabel("Activity"), 0)
        self.manual_log = QPlainTextEdit()
        self.manual_log.setObjectName("Log")
        self.manual_log.setReadOnly(True)
        self.manual_log.document().setMaximumBlockCount(3000)  # keep UI fast on huge sends
        self.manual_log.setMinimumHeight(180)
        al.addWidget(self.manual_log)
        lay.addWidget(activity)
        lay.addStretch()
        return self.scroll_page(page)

    # -- Batch page ---------------------------------------------------------#
    def build_batch_page(self):
        page, lay = self.page("BatchPage")
        lay.addWidget(self.heading("Batch SMS", "Load phone files, check the files you want to send, then confirm before any SMS request is made."))
        message = Card()
        ml = QVBoxLayout(message)
        ml.setContentsMargins(18, 18, 18, 18)
        ml.setSpacing(9)
        label = QLabel("Message")
        label.setObjectName("SectionTitle")
        ml.addWidget(label)
        self.batch_message = UnicodeTextEdit()
        self.batch_message.setPlaceholderText("Write the message for all checked files...")
        self.batch_message.setMinimumHeight(110)
        self.batch_message.setMaximumHeight(170)
        self.batch_message.textChanged.connect(self.update_batch_message_count)
        ml.addWidget(self.batch_message)
        self.batch_char_count = QLabel("0 characters")
        self.batch_char_count.setObjectName("TinyMuted")
        self.batch_char_count.setAlignment(Qt.AlignRight)
        ml.addWidget(self.batch_char_count)
        lay.addWidget(message)

        files = Card()
        files.setObjectName("TargetFilesCard")
        fl = QVBoxLayout(files)
        fl.setContentsMargins(18, 16, 18, 16)
        fl.setSpacing(8)
        header = QHBoxLayout()
        title = QLabel("Target files")
        title.setObjectName("TargetFilesTitle")
        header.addWidget(title)
        header.addStretch()
        self.add_files_btn = QPushButton("+ Add files")
        self.add_files_btn.clicked.connect(self.add_files)
        self.add_folder_btn = QPushButton("Add folder")
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.clear_files_btn = QPushButton("Clear")
        self.clear_files_btn.setObjectName("DangerButton")
        self.clear_files_btn.clicked.connect(self.clear_files)
        header.addWidget(self.add_files_btn)
        header.addWidget(self.add_folder_btn)
        header.addWidget(self.clear_files_btn)
        fl.addLayout(header)
        self.loading_label = QLabel("")
        self.loading_label.setObjectName("TargetFilesLoading")
        self.loading_label.hide()
        fl.addWidget(self.loading_label)
        self.file_list = QListWidget()
        self.file_list.setObjectName("BatchFileList")
        self.file_list.setSelectionMode(QAbstractItemView.NoSelection)
        fl.addWidget(self.file_list)

        self.checked_count_label = QLabel("0 files checked")
        self.checked_count_label.setObjectName("TinyMuted")
        fl.addWidget(self.checked_count_label)
        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.select_all_btn = QPushButton("Select all")
        self.uncheck_all_btn = QPushButton("Uncheck all")
        self.select_all_btn.setEnabled(False)
        self.uncheck_all_btn.setEnabled(False)
        self.select_all_btn.clicked.connect(lambda: self.set_all_checked(True))
        self.uncheck_all_btn.clicked.connect(lambda: self.set_all_checked(False))
        actions.addWidget(self.select_all_btn)
        actions.addWidget(self.uncheck_all_btn)
        actions.addStretch()
        fl.addLayout(actions)
        self.targets_summary = QLabel("No files loaded")
        self.targets_summary.setObjectName("TinyMuted")
        fl.addWidget(self.targets_summary)
        lay.addWidget(files)

        start = QPushButton("Start Batch Send")
        start.setObjectName("SmallPrimaryButton")
        start.setFixedHeight(40)
        start.setMinimumWidth(190)
        start.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        apply_glow(start, COLORS["accent"], blur_radius=14, offset=(0, 2))
        start.clicked.connect(self.start_batch_send)
        self.batch_start_btn = start
        start_row = QHBoxLayout()
        start_row.setSpacing(10)
        start_row.addWidget(start)

        self.batch_clear_btn = QPushButton("Clear Page")
        self.batch_clear_btn.setObjectName("DangerButton")
        self.batch_clear_btn.setFixedHeight(40)
        self.batch_clear_btn.setMinimumWidth(120)
        self.batch_clear_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.batch_clear_btn.clicked.connect(self.clear_batch_page)
        start_row.addWidget(self.batch_clear_btn)

        start_row.addStretch()
        lay.addLayout(start_row)

        self.batch_progress_panel = LiveProgressPanel()
        self.batch_progress_panel.interrupt_requested.connect(lambda name: self.interrupt_workers("batch", name))
        self.batch_progress_panel.interrupt_all_requested.connect(lambda: self.interrupt_workers("batch"))
        self.batch_progress_panel.pause_requested.connect(self._pause_batch)
        self.batch_progress_panel.resume_requested.connect(self._resume_batch)
        lay.addWidget(self.batch_progress_panel)

        activity = Card()
        al = QVBoxLayout(activity)
        al.setContentsMargins(18, 15, 18, 15)
        al.addWidget(QLabel("Activity"))
        self.batch_log = QPlainTextEdit()
        self.batch_log.setObjectName("Log")
        self.batch_log.setReadOnly(True)
        self.batch_log.document().setMaximumBlockCount(3000)  # keep UI fast on huge sends
        self.batch_log.setMinimumHeight(160)
        al.addWidget(self.batch_log)
        lay.addWidget(activity)
        lay.addStretch()
        return self.scroll_page(page)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        self.manual_nav.setChecked(index == 0)
        self.batch_nav.setChecked(index == 1)
        self.projects_nav.setChecked(index == 2)
        labels = {0: "Manual Send", 1: "Batch Send", 2: "Projects"}
        self.breadcrumb.setText(labels.get(index, ""))
        if index == 2:
            self.projects_page.refresh()

    def refresh_api_status(self):
        load_dotenv(ENV_PATH, override=True)
        ok = bool(os.getenv("SMS_API_URL", "").strip() and os.getenv("SMS_API_KEY", "").strip())
        self.api_status.setText("API configured" if ok else "API not configured")
        self.api_status.setStyleSheet(f"color:{COLORS['success'] if ok else COLORS['danger']}; font-size:11px; font-weight:700;")
        self.manual_send_btn.setEnabled(ok)
        self.batch_start_btn.setEnabled(ok)

    def open_settings(self):
        load_dotenv(ENV_PATH, override=True)
        dialog = SettingsDialog(self)
        dialog.load_values(os.getenv("SMS_API_URL", ""), os.getenv("SMS_API_KEY", ""))
        if dialog.exec() == QDialog.Accepted:
            self.refresh_api_status()

    def open_test_api_dialog(self, *args, **kwargs):
        auto_start = kwargs.get("auto_start", False)
        from api_test_dialog import ApiTestDialog
        dialog = ApiTestDialog(self, auto_start=bool(auto_start))
        dialog.exec()
        self.refresh_api_status()

    def choose_wallpaper_action(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose wallpaper", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not path:
            return
        try:
            self.wallpaper_manager.set_wallpaper(path)
            self.reload_wallpaper()
        except Exception as exc:
            ERROR_LOGGER.error("Failed setting wallpaper: %s", exc)
            QMessageBox.critical(self, "Wallpaper failed", str(exc))

    def clear_manual_page(self):
        self.interrupt_workers("manual")
        self.manual_progress_panel.reset()
        self.manual_message.clear()
        self.manual_phones.clear()
        self.manual_char_count.setText("0 characters")
        self.manual_phone_hint.setText("0 recipients detected")
        self.manual_recipient_stat.setText("0")
        self.manual_sent_stat.setText("0")
        self.manual_failed_stat.setText("0")
        self.manual_log.clear()
        self.manual_send_btn.setEnabled(True)
        self.log(self.manual_log, "info", "Manual page reset. Inputs and processes cleared.")

    def clear_batch_page(self):
        self.interrupt_workers("batch")
        self.batch_progress_panel.reset()
        self.batch_message.clear()
        self.batch_char_count.setText("0 characters")
        self.segments.clear()
        self.update_file_list()
        self.loading_label.setText("")
        self.batch_log.clear()
        self.batch_start_btn.setEnabled(True)
        self.log(self.batch_log, "info", "Batch page reset. Files, inputs, and processes cleared.")

    def update_manual_message_count(self):
        self.manual_char_count.setText(f"{len(self.manual_message.toPlainText()):,} characters")

    def update_manual_recipient_count(self):
        count = len(parse_manual_phones(self.manual_phones.toPlainText()))
        self.manual_phone_hint.setText(f"{count:,} recipient{'s' if count != 1 else ''} detected")
        self.manual_recipient_stat.setText(f"{count:,}")

    def update_batch_message_count(self):
        self.batch_char_count.setText(f"{len(self.batch_message.toPlainText()):,} characters")

    def log(self, widget, level, text):
        prefix = {"success": "[OK]", "error": "[ERR]", "info": "[*]"}.get(level, "[*]")
        widget.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {prefix} {text}")
        widget.verticalScrollBar().setValue(widget.verticalScrollBar().maximum())
        if level == "error":
            ERROR_LOGGER.error(text)

    # -- manual sending -------------------------------------------------- #
    def _pause_manual(self):
        for w in self.active_workers:
            if getattr(w, "mode", None) == "manual":
                w.pause()
        self.log(self.manual_log, "info", "Sending paused by user.")

    def _resume_manual(self):
        for w in self.active_workers:
            if getattr(w, "mode", None) == "manual":
                w.resume()
        self.log(self.manual_log, "info", "Sending resumed by user.")

    def _pause_batch(self):
        for w in self.active_workers:
            if getattr(w, "mode", None) == "batch":
                w.pause()
        self.log(self.batch_log, "info", "Batch send paused by user.")

    def _resume_batch(self):
        for w in self.active_workers:
            if getattr(w, "mode", None) == "batch":
                w.resume()
        self.log(self.batch_log, "info", "Batch send resumed by user.")

    def _on_batch_worker_progress(self, name, current, total, failed):
        self.batch_progress_panel.update_target(name, current, total, failed)
        row = getattr(self, "batch_rows", {}).get(name)
        if row is not None:
            pct = (current / total) if total else 0.0
            is_done = (current >= total and total > 0)
            set_row_done(row, is_done, pct)

    def _on_batch_network_lost(self, name, err, lost_time):
        self.batch_progress_panel.show_reconnecting(lost_time)
        self.log(self.batch_log, "error", f"Network connection lost ({name}): {err}. Trying to reconnect...")
        for w in self.active_workers:
            if getattr(w, "mode", None) == "batch" and w.segment_name != name:
                w.set_network_paused(True)

    def _on_batch_network_restored(self, name):
        self.batch_progress_panel.hide_reconnecting()
        self.log(self.batch_log, "success", f"API connection restored ({name}). Resuming...")
        for w in self.active_workers:
            if getattr(w, "mode", None) == "batch":
                w.set_network_paused(False)

    def start_manual_send(self):
        message = self.manual_message.toPlainText().strip()
        phones = parse_manual_phones(self.manual_phones.toPlainText())
        url = os.getenv("SMS_API_URL", "").strip()
        key = os.getenv("SMS_API_KEY", "").strip()
        if not message:
            QMessageBox.warning(self, "Message required", "Enter a message.")
            return
        if not phones:
            QMessageBox.warning(self, "Recipients required", "Enter at least one valid phone number.")
            return
        if not url or not key:
            QMessageBox.warning(self, "API not configured", "Open Settings and configure the URL and key.")
            return
        self.manual_send_btn.setEnabled(False)
        self.manual_send_btn.setText("Sending...")
        self.start_pulse(self.manual_send_btn, COLORS["accent"], 14, 40, 600)
        self.manual_progress_panel.reset()
        self.manual_progress_panel.add_target("Manual", len(phones))
        self.manual_sent_stat.setText("0")
        self.manual_failed_stat.setText("0")
        self.manual_log.clear()
        concurrency = int(os.getenv("MANUAL_CONCURRENCY", "5"))
        worker = SendingWorker("Manual", phones, message, url, key, "manual", concurrency, self)
        worker.progress.connect(self.update_manual_progress)
        worker.network_lost.connect(lambda name, err, t: self.manual_progress_panel.show_reconnecting(t))
        worker.network_restored.connect(lambda name: self.manual_progress_panel.hide_reconnecting())
        worker.log.connect(lambda level, text: self.log(self.manual_log, level, text))
        worker.finished.connect(self.handle_manual_finished)
        self.active_workers.append(worker)
        worker.start()

    def update_manual_progress(self, name, current, total, failed):
        self.manual_progress_panel.update_target(name, current, total, failed)
        self.manual_sent_stat.setText(f"{current - failed:,}")
        self.manual_failed_stat.setText(f"{failed:,}")

    def handle_manual_finished(self, name, report, mode):
        self.manual_progress_panel.hide_reconnecting()
        path = self.save_report(f"manual_Report_{datetime.now().strftime('%d-%m-%Y')}.json", report)
        s = report["summary"]
        self.stop_pulse(self.manual_send_btn)
        apply_glow(self.manual_send_btn, COLORS["accent"], blur_radius=14, offset=(0, 2))
        self.manual_send_btn.setEnabled(True)
        self.manual_send_btn.setText("Send Messages ->")
        interrupted = bool(s.get("interrupted"))
        if interrupted:
            self.manual_progress_panel.mark_interrupted(name, s["processed"], s["failed"])
        else:
            self.manual_progress_panel.complete_target(name, s["processed"], s["failed"])
        self.log(self.manual_log, "info" if interrupted else ("success" if s["failed"] == 0 else "error"),
                 f"{'Interrupted' if interrupted else 'Finished'}. Report saved to {path}")
        self.remove_finished_worker(name)
        QMessageBox.information(
            self, "Sending interrupted" if interrupted else "Sending complete",
            f"Sent: {s['processed']:,}\nFailed: {s['failed']:,}"
            + (f"\nNot attempted: {s.get('cancelled', 0):,}" if interrupted else "")
            + f"\n\nReport:\n{path}")

    # -- batch: file loading ------------------------------------------------#
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select phone files", "", "Supported (*.csv *.xlsx *.xls *.json *.txt)")
        if files:
            self.start_file_loading(files)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder")
        if not folder:
            return
        paths = []
        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                if os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS:
                    paths.append(os.path.join(root, filename))
        if not paths:
            QMessageBox.information(self, "No supported files", "No CSV, Excel, JSON or TXT files were found in that folder.")
            return
        self.start_file_loading(paths)

    def start_file_loading(self, paths):
        if self.loader and self.loader.isRunning():
            return
        paths, overrides, self.excel_for_all_column = resolve_excel_columns(
            paths, self, lambda level, text: self.log(self.batch_log, level, text), self.excel_for_all_column
        )
        if not paths:
            return
        self.set_file_controls_enabled(False)
        self.loading_label.setText(f"⏳ Loading 0 / {len(paths)} files...")
        self.loading_label.show()
        self.start_pulse(self.loading_label, "#00FF9D", 0, 16, 700)
        self.loader = FileLoadWorker(paths, overrides, self)
        self.loader.progress.connect(lambda current, total, name: self.loading_label.setText(f"⏳ Loading {current} / {total} - {name}"))
        self.loader.file_failed.connect(lambda path, error: self.log(self.batch_log, "error", f"{os.path.basename(path)}: {error}"))
        self.loader.finished.connect(self.finish_file_loading)
        self.loader.start()

    def finish_file_loading(self, results):
        added = 0
        for path, phones in results.items():
            base = os.path.basename(path)
            name = base
            counter = 2
            while name in self.segments:
                stem, ext = os.path.splitext(base)
                name = f"{stem}_{counter}{ext}"
                counter += 1
            self.segments[name] = {"path": path, "phones": phones, "checked": True}
            added += 1
        self.stop_pulse(self.loading_label)
        if added:
            self.loading_label.setText(f"✔ Finished loading - {added:,} file(s) added")
            self.loading_label.show()
        else:
            self.loading_label.hide()
        self.set_file_controls_enabled(True)
        self.update_file_list()
        self.log(self.batch_log, "success", f"Loaded {added:,} file(s). Checked files are the ones that will be sent.")

    def set_file_controls_enabled(self, enabled):
        self.add_files_btn.setEnabled(enabled)
        self.add_folder_btn.setEnabled(enabled)
        self.clear_files_btn.setEnabled(enabled)
        has_files = bool(self.segments)
        self.select_all_btn.setEnabled(enabled and has_files)
        self.uncheck_all_btn.setEnabled(enabled and has_files)

    def clear_files(self):
        if not self.segments:
            return
        self.segments.clear()
        self.update_file_list()
        self.loading_label.setText("")
        self.loading_label.hide()

    def remove_file(self, name):
        if name in self.segments:
            del self.segments[name]
            self.update_file_list()

    def update_file_list(self):
        self.file_list.clear()
        self.batch_rows = {}
        total_phones = 0
        for name, data in self.segments.items():
            total_phones += len(data["phones"])
            item = QListWidgetItem()
            item.setSizeHint(QSize(100, 50))
            row = build_file_row(
                display_name=name,
                meta_text=f"{len(data['phones']):,} phone numbers",
                checked=data["checked"],
                tooltip=data["path"],
                on_toggle=lambda state, n=name: self.set_segment_checked(n, state),
                on_delete=lambda checked, n=name: self.remove_file(n),
            )
            self.batch_rows[name] = row
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, row)
        checked = self.checked_segments()
        self.checked_count_label.setText(f"{len(checked):,} file{'s' if len(checked) != 1 else ''} checked")
        if self.segments:
            self.targets_summary.setText(f"{len(self.segments):,} file(s) - {total_phones:,} total phone numbers")
        else:
            self.targets_summary.setText("No files loaded")
        has_files = bool(self.segments)
        self.select_all_btn.setEnabled(has_files)
        self.uncheck_all_btn.setEnabled(has_files)
        self.update_file_list_height()

    def set_segment_checked(self, name, state):
        if name in self.segments:
            self.segments[name]["checked"] = bool(state)
        checked = len(self.checked_segments())
        self.checked_count_label.setText(f"{checked:,} file{'s' if checked != 1 else ''} checked")

    def checked_segments(self):
        return [name for name, data in self.segments.items() if data["checked"]]

    def set_all_checked(self, state):
        for data in self.segments.values():
            data["checked"] = state
        self.update_file_list()

    def update_file_list_height(self):
        count = len(self.segments)
        row_height = 52
        if count == 0:
            h = 160
        elif count <= 8:
            h = max(160, count * row_height + 16)
        else:
            h = 8 * row_height + 18  # Exactly 8 files visible, 9th onwards scrolls
        self.file_list.setFixedHeight(h)


    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "file_list"):
            self.update_file_list_height()

    # -- batch sending --------------------------------------------------- #
    def start_batch_send(self):
        url = os.getenv("SMS_API_URL", "").strip()
        key = os.getenv("SMS_API_KEY", "").strip()
        message = self.batch_message.toPlainText().strip()
        selected = self.checked_segments()
        if not url or not key:
            QMessageBox.warning(self, "API not configured", "Open Settings and configure the URL and key.")
            return
        if not message:
            QMessageBox.warning(self, "Message required", "Enter a message.")
            return
        if not selected:
            QMessageBox.warning(self, "Nothing selected", "Check at least one target file.")
            return
        total_phones = sum(len(self.segments[name]["phones"]) for name in selected)
        answer = QMessageBox.question(
            self, "Confirm batch send",
            f"You are about to send to {len(selected):,} checked file(s), containing {total_phones:,} phone number(s).\n\n"
            "Only the checked files will be sent.\n\nDo you want to continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.batch_start_btn.setEnabled(False)
        self.batch_start_btn.setText("Sending batch...")
        self.start_pulse(self.batch_start_btn, COLORS["accent"], 14, 40, 600)
        self.batch_log.clear()
        self._batch_interrupted = False
        self.batch_progress_panel.reset()
        concurrency = int(os.getenv("BATCH_CONCURRENCY", "30"))
        for name in selected:
            phones = self.segments[name]["phones"]
            self.batch_progress_panel.add_target(name, len(phones))
            worker = SendingWorker(name, phones, message, url, key, "batch", concurrency, self)
            worker.progress.connect(lambda n, cur, tot, fail: self._on_batch_worker_progress(n, cur, tot, fail))
            worker.network_lost.connect(self._on_batch_network_lost)
            worker.network_restored.connect(self._on_batch_network_restored)
            worker.log.connect(lambda level, text: self.log(self.batch_log, level, text))
            worker.finished.connect(self.handle_batch_finished)
            self.active_workers.append(worker)
            worker.start()

    def handle_batch_finished(self, name, report, mode):
        path = self.save_report(f"{self.safe_filename(name)}_report.json", report)
        s = report["summary"]
        if s.get("interrupted"):
            self._batch_interrupted = True
            self.batch_progress_panel.mark_interrupted(name, s["processed"], s["failed"])
            self.log(self.batch_log, "info", f"{name}: interrupted. Report saved to {path}")
        else:
            self.batch_progress_panel.complete_target(name, s["processed"], s["failed"])
            self.log(self.batch_log, "success" if s["failed"] == 0 else "error", f"{name}: complete. Report saved to {path}")
            row = getattr(self, "batch_rows", {}).get(name)
            if row is not None:
                set_row_done(row, True, 1.0)
        self.remove_finished_worker(name)
        if not any(getattr(w, "mode", None) == "batch" for w in self.active_workers):
            self.batch_progress_panel.hide_reconnecting()
            self.stop_pulse(self.batch_start_btn)
            apply_glow(self.batch_start_btn, COLORS["accent"], blur_radius=14, offset=(0, 2))
            self.batch_start_btn.setEnabled(True)
            self.batch_start_btn.setText("Start Batch Send")
            QMessageBox.information(
                self, "Batch interrupted" if self._batch_interrupted else "Batch complete",
                ("Sending was interrupted for at least one file. " if self._batch_interrupted
                 else "All checked files have finished processing. ")
                + "Reports were saved in the Reports folder.")

    def interrupt_workers(self, mode, name=None):
        """Asks running workers to stop (all of a mode, or just one by name)."""
        if mode == "manual":
            self.manual_progress_panel.hide_reconnecting()
        elif mode == "batch":
            self.batch_progress_panel.hide_reconnecting()
        for worker in self.active_workers:
            if getattr(worker, "mode", None) == mode and (name is None or worker.segment_name == name):
                worker.stop()

    def remove_finished_worker(self, segment):
        remaining = []
        for worker in self.active_workers:
            if worker.segment_name == segment:
                try:
                    worker.deleteLater()
                except RuntimeError:
                    pass
            else:
                remaining.append(worker)
        self.active_workers = remaining

    def safe_filename(self, name):
        return re.sub(r'[<>:"/\\|?*]', "_", name)

    def save_report(self, filename, report):
        # All manual/batch reports live under ONE folder: Reports/<dd-mm-yyyy>/
        # (project reports live inside each project: Projects/<name>/Reports/).
        folder = os.path.join(SCRIPT_DIR, "Reports", datetime.now().strftime("%d-%m-%Y"))
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, self.safe_filename(filename))
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        return path

    def closeEvent(self, event):
        self._bg_timer.stop()
        if self.loader and self.loader.isRunning():
            self.loader.cancel_requested = True
            self.loader.wait(2000)
        for worker in list(self.active_workers):
            worker.running = False
            worker.wait(2000)
        event.accept()


# Named Mutex to guarantee only one instance of SmsBlast Pro runs at a time
SINGLE_INSTANCE_MUTEX = None


def check_single_instance():
    """Ensures only one instance of SmsBlast Pro runs at a time.
    If already running, activates and brings existing window to front, then exits cleanly.
    """
    global SINGLE_INSTANCE_MUTEX
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        ERROR_ALREADY_EXISTS = 183
        mutex_name = "Local\\SmsBlastPro_v4_SingleInstance_Mutex"
        SINGLE_INSTANCE_MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            user32 = ctypes.windll.user32
            target_hwnd = None

            def enum_cb(hwnd, lparam):
                nonlocal target_hwnd
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        if "SmsBlast Pro" in buff.value:
                            target_hwnd = hwnd
                            return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            if target_hwnd:
                user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(target_hwnd)
            print("SmsBlast Pro is already running. Activated existing window.")
            return False
    except Exception as e:
        print(f"Single instance check note: {e}", file=sys.stderr)
    return True


def main():
    if not check_single_instance():
        sys.exit(0)
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("smsblast.pro.desktop.v4")
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon = get_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    app_font = QFont()
    families = get_font_families()
    if families:
        app_font.setFamilies(families)
    else:
        app_font.setFamily(choose_font())
    app_font.setPointSize(10)
    app.setFont(app_font)
    window = MainWindow()
    hwnd = int(window.winId())
    enable_dark_titlebar(hwnd)
    window.show()
    result = apply_mica(hwnd)  # see mica.py for ENABLE_NATIVE_BLUR / BACKDROP_MODE
    window.set_backdrop(result)
    sys.exit(app.exec())



if __name__ == "__main__":
    main()
