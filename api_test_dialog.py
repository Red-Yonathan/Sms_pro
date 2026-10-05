import os
import time
import json
import asyncio
import aiohttp
from PySide6.QtCore import Qt, QThread, Signal, QSettings, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QToolButton, QScrollArea, QWidget, QSizeGrip, QMessageBox,
)

from theme import COLORS
from sender import format_phone
from ui_common import Card, apply_glow, attach_focus_glow, enable_dark_titlebar, paint_window_background


class TestApiWorker(QThread):
    result = Signal(bool, int, str, float, str)  # success, status_code, body, elapsed, error_detail

    def __init__(self, url, key, phone, message, parent=None):
        super().__init__(parent)
        self.url = url.strip()
        self.key = key.strip()
        self.phone = phone.strip()
        self.message = message.strip()

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._do_send())
        finally:
            loop.close()

    async def _do_send(self):
        t0 = time.time()
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json; charset=utf-8",
            "prepaid-api-key": self.key,
        }
        payload = {
            "to": format_phone(self.phone),
            "message": self.message,
        }
        timeout = aiohttp.ClientTimeout(total=20, connect=6)
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.post(self.url, json=payload, allow_redirects=True) as resp:
                    body = (await resp.text()).strip()
                    elapsed = time.time() - t0
                    if 200 <= resp.status < 300:
                        try:
                            parsed = json.loads(body) if body else None
                        except json.JSONDecodeError:
                            parsed = None
                        if isinstance(parsed, dict) and (parsed.get("success") is False or str(parsed.get("status", "")).lower() in {"failed", "error"}):
                            self.result.emit(False, resp.status, body, elapsed, f"API rejected send: {body[:300]}")
                            return
                        self.result.emit(True, resp.status, body, elapsed, "")
                    else:
                        self.result.emit(False, resp.status, body, elapsed, f"HTTP {resp.status}: {body[:500] if body else 'No response body'}")
        except asyncio.TimeoutError:
            elapsed = time.time() - t0
            self.result.emit(False, 0, "", elapsed, "Connection timed out (server did not respond in 20s).")
        except (aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError) as exc:
            elapsed = time.time() - t0
            self.result.emit(False, 0, "", elapsed, f"Network Connection Error: {type(exc).__name__} - Could not connect to API server.")
        except Exception as exc:
            elapsed = time.time() - t0
            self.result.emit(False, 0, "", elapsed, f"{type(exc).__name__}: {exc}")


class ApiTestDialog(QDialog):
    def __init__(self, parent=None, url=None, key=None, auto_start=False):
        super().__init__(parent)
        self.parent_window = parent
        icon = getattr(parent, "windowIcon", lambda: None)() if parent else None
        if icon and not icon.isNull():
            self.setWindowIcon(icon)
        else:
            try:
                from main import get_app_icon
                ic = get_app_icon()
                if not ic.isNull():
                    self.setWindowIcon(ic)
            except Exception:
                pass
        self.setWindowTitle("⚡ Test SMS API Connection - SmsBlast Pro")
        self.setModal(True)
        self.resize(560, 520)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        enable_dark_titlebar(int(self.winId()))


        self.initial_url = (url or os.getenv("SMS_API_URL", "")).strip()
        self.initial_key = (key or os.getenv("SMS_API_KEY", "")).strip()
        self.worker = None

        self.wallpaper_manager = getattr(parent, "wallpaper_manager", None)
        self._wallpaper_pixmap = None
        self.reload_wallpaper()
        if self.wallpaper_manager:
            self.wallpaper_manager.add_listener(self.reload_wallpaper)

        self._build_ui()
        self._load_saved_test_data()

        if auto_start:
            QTimer.singleShot(400, self.start_test)

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

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        # Header
        head = QVBoxLayout()
        head.setSpacing(3)
        title = QLabel("⚡ Test SMS API Connection")
        title.setObjectName("DialogTitle")
        sub = QLabel("Send a simple single text message to test if your API credentials and server are working properly.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        head.addWidget(title)
        head.addWidget(sub)
        root.addLayout(head)

        # Config Card
        cfg_card = Card()
        cl = QVBoxLayout(cfg_card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(10)

        cl.addWidget(QLabel("Target SMS API URL:"))
        self.url_input = QLineEdit(self.initial_url)
        self.url_input.setPlaceholderText("https://example.com/api/send-sms")
        attach_focus_glow(self.url_input)
        cl.addWidget(self.url_input)

        cl.addWidget(QLabel("API Key:"))
        key_row = QHBoxLayout()
        self.key_input = QLineEdit(self.initial_key)
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("prepaid-api-key")
        attach_focus_glow(self.key_input)
        show_key_btn = QToolButton()
        show_key_btn.setText("Show")
        show_key_btn.clicked.connect(lambda: self._toggle_key(show_key_btn))
        key_row.addWidget(self.key_input, 1)
        key_row.addWidget(show_key_btn)
        cl.addLayout(key_row)
        root.addWidget(cfg_card)

        # Test message Card
        msg_card = Card()
        ml = QVBoxLayout(msg_card)
        ml.setContentsMargins(16, 14, 16, 14)
        ml.setSpacing(10)

        ml.addWidget(QLabel("Recipient Phone Number:"))
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("e.g. 0912345678 or +251912345678")
        attach_focus_glow(self.phone_input)
        ml.addWidget(self.phone_input)

        ml.addWidget(QLabel("Test Message Text:"))
        self.msg_input = QLineEdit("Hello! This is a test SMS from SmsBlast Pro.")
        attach_focus_glow(self.msg_input)
        ml.addWidget(self.msg_input)
        root.addWidget(msg_card)

        # Result Banner
        self.result_box = QFrame()
        self.result_box.setStyleSheet(
            f"background: {COLORS['surface2']}; border: 1px solid {COLORS['border']}; "
            "border-radius: 8px; padding: 10px 14px;"
        )
        rl = QVBoxLayout(self.result_box)
        rl.setContentsMargins(8, 6, 8, 6)
        rl.setSpacing(4)
        self.result_status = QLabel("Ready to test. Enter a phone number and click 'Send Test SMS'.")
        self.result_status.setObjectName("Muted")
        self.result_status.setWordWrap(True)
        self.result_detail = QLabel("")
        self.result_detail.setWordWrap(True)
        self.result_detail.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        self.result_detail.hide()
        rl.addWidget(self.result_status)
        rl.addWidget(self.result_detail)
        root.addWidget(self.result_box)

        # Bottom buttons
        bottom = QHBoxLayout()
        grip = QSizeGrip(self)
        bottom.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignLeft)
        bottom.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        bottom.addWidget(self.close_btn)

        self.send_test_btn = QPushButton("⚡ Send Test SMS")
        self.send_test_btn.setObjectName("PrimaryButton")
        self.send_test_btn.setMinimumWidth(150)
        apply_glow(self.send_test_btn, COLORS["accent"], blur_radius=14, offset=(0, 2))
        self.send_test_btn.clicked.connect(self.start_test)
        bottom.addWidget(self.send_test_btn)
        root.addLayout(bottom)

    def _toggle_key(self, btn):
        if self.key_input.echoMode() == QLineEdit.Password:
            self.key_input.setEchoMode(QLineEdit.Normal)
            btn.setText("Hide")
        else:
            self.key_input.setEchoMode(QLineEdit.Password)
            btn.setText("Show")

    def _load_saved_test_data(self):
        settings = QSettings("PhoneSenderPro", "ApiTest")
        saved_phone = settings.value("test_phone", "")
        if saved_phone:
            self.phone_input.setText(str(saved_phone))
        saved_msg = settings.value("test_msg", "")
        if saved_msg:
            self.msg_input.setText(str(saved_msg))

    def _save_test_data(self):
        settings = QSettings("PhoneSenderPro", "ApiTest")
        settings.setValue("test_phone", self.phone_input.text().strip())
        settings.setValue("test_msg", self.msg_input.text().strip())

    def start_test(self):
        url = self.url_input.text().strip()
        key = self.key_input.text().strip()
        phone = self.phone_input.text().strip()
        message = self.msg_input.text().strip()

        if not url:
            QMessageBox.warning(self, "API URL Missing", "Please enter the SMS API URL.")
            return
        if not key:
            QMessageBox.warning(self, "API Key Missing", "Please enter the SMS API Key.")
            return
        if not phone:
            QMessageBox.warning(self, "Phone Number Missing", "Please enter a test recipient phone number.")
            return
        if not message:
            QMessageBox.warning(self, "Message Missing", "Please enter a test message.")
            return

        self._save_test_data()
        self.send_test_btn.setEnabled(False)
        self.send_test_btn.setText("Sending...")
        self.result_detail.hide()

        self.result_box.setStyleSheet(
            f"background: rgba(0, 240, 255, 0.10); border: 1.5px solid {COLORS['accent']}; "
            "border-radius: 8px; padding: 10px 14px;"
        )
        self.result_status.setStyleSheet(f"color: {COLORS['accent']}; font-weight: 700;")
        self.result_status.setText(f"⏳ Connecting to {url} and sending to {format_phone(phone)}...")

        self.worker = TestApiWorker(url, key, phone, message, self)
        self.worker.result.connect(self.handle_test_result)
        self.worker.start()

    def handle_test_result(self, ok, status_code, body, elapsed, error_detail):
        self.send_test_btn.setEnabled(True)
        self.send_test_btn.setText("⚡ Send Test SMS")

        if ok:
            self.result_box.setStyleSheet(
                "background: rgba(0, 255, 157, 0.15); border: 1.5px solid #00FF9D; "
                "border-radius: 8px; padding: 10px 14px;"
            )
            self.result_status.setStyleSheet("color: #00FF9D; font-weight: 750; font-size: 13px;")
            self.result_status.setText(f"✔ SUCCESS: Message delivered to API! (HTTP {status_code}, took {elapsed:.2f}s)")
            if body:
                self.result_detail.setText(f"Server response:\n{body[:400]}")
                self.result_detail.setStyleSheet("color: #E2FBF0; font-family: Consolas, monospace; font-size: 11px;")
                self.result_detail.show()
        else:
            self.result_box.setStyleSheet(
                "background: rgba(255, 51, 102, 0.18); border: 1.5px solid #FF3366; "
                "border-radius: 8px; padding: 10px 14px;"
            )
            self.result_status.setStyleSheet("color: #FF3366; font-weight: 750; font-size: 13px;")
            code_text = f"HTTP {status_code}" if status_code else "Connection Failed"
            self.result_status.setText(f"✖ FAILED ({code_text}, took {elapsed:.2f}s)")
            detail_msg = error_detail or body or "Unknown error"
            self.result_detail.setText(f"Error detail:\n{detail_msg}")
            self.result_detail.setStyleSheet("color: #FFCBD4; font-family: Consolas, monospace; font-size: 11px;")
            self.result_detail.show()
