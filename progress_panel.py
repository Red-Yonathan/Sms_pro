"""
progress_panel.py
====================
Overall progress bar (with an "Interrupt all" button) plus a scrollable
stack of per-target bars (each with its own "Interrupt" button).

Look:
  * overall bar   : blue->purple while filling, cyan/green sweep when complete
  * per-file bars : purple->cyan while filling, green when complete,
                    amber when interrupted

The panel only *asks* for interrupts (signals); whoever owns the workers
decides how to stop them (worker.running = False).
"""
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QScrollArea,
    QFrame, QPushButton, QGraphicsDropShadowEffect,
)

from theme import COLORS


def _glow(widget, color_hex, blur_radius=16, offset=(0, 0)):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur_radius)
    c = QColor(color_hex)
    c.setAlpha(180)
    shadow.setColor(c)
    shadow.setOffset(*offset)
    widget.setGraphicsEffect(shadow)
    return shadow


def _interrupt_button(text):
    btn = QPushButton(text)
    btn.setObjectName("DangerButton")
    btn.setFixedHeight(30)
    btn.setMinimumWidth(96)
    btn.setStyleSheet("padding: 2px 12px;")   # theme's default 8px vertical padding clips text at this height
    btn.setEnabled(False)
    return btn


class LiveProgressPanel(QWidget):
    interrupt_requested = Signal(str)      # target name
    interrupt_all_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        total_card = QFrame()
        total_card.setObjectName("Card")
        tl = QVBoxLayout(total_card)
        tl.setContentsMargins(16, 13, 16, 13)
        head = QHBoxLayout()
        self.total_label = QLabel("Overall progress - 0 / 0")
        self.total_label.setObjectName("SectionTitle")
        head.addWidget(self.total_label, 1)
        self.interrupt_all_btn = _interrupt_button("Interrupt all")
        self.interrupt_all_btn.clicked.connect(self._on_interrupt_all)
        head.addWidget(self.interrupt_all_btn)
        tl.addLayout(head)
        self.total_bar = QProgressBar()
        self.total_bar.setRange(0, 1)
        self.total_bar.setValue(0)
        self._style_total_bar_in_progress()
        _glow(self.total_bar, COLORS["accent"], blur_radius=16)
        tl.addWidget(self.total_bar)
        lay.addWidget(total_card)

        self.container = QWidget()
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(7)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(140)
        scroll.setMaximumHeight(260)
        scroll.setWidget(self.container)
        lay.addWidget(scroll)

        self.cards = {}       # name -> (card, label, bar, button)
        self.totals = {}      # name -> [total, current, failed]
        self.finished = set()
        self.total_bar_completed = False

    # -- helpers ----------------------------------------------------- #
    def _style_total_bar_in_progress(self):
        self.total_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {COLORS['blue']}, stop:0.5 {COLORS['purple']}, stop:1 {COLORS['blue']}); "
            f"border-radius: 6px; }}"
        )

    def reset(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.cards.clear()
        self.totals.clear()
        self.finished.clear()
        self.total_bar.setRange(0, 1)
        self.total_bar.setValue(0)
        self.total_label.setText("Overall progress - 0 / 0")
        self._style_total_bar_in_progress()
        _glow(self.total_bar, COLORS["accent"], blur_radius=16)
        self.interrupt_all_btn.setEnabled(False)
        self.interrupt_all_btn.setText("Interrupt all")
        self.total_bar_completed = False

    # -- targets ------------------------------------------------------- #
    def add_target(self, name, total):
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(13, 11, 13, 11)
        lay.setSpacing(5)
        head = QHBoxLayout()
        label = QLabel(f"{name} - 0 / {total:,}")
        label.setObjectName("SectionTitle")
        head.addWidget(label, 1)
        btn = _interrupt_button("Interrupt")
        btn.setEnabled(True)
        btn.clicked.connect(lambda _checked=False, n=name: self._on_interrupt(n))
        head.addWidget(btn)
        lay.addLayout(head)
        bar = QProgressBar()
        bar.setRange(0, max(total, 1))
        bar.setValue(0)
        _glow(bar, COLORS["accent"], blur_radius=12)
        lay.addWidget(bar)
        self.card_layout.addWidget(card)
        self.cards[name] = (card, label, bar, btn)
        self.totals[name] = [total, 0, 0]
        self._refresh_total()

    def _on_interrupt(self, name):
        entry = self.cards.get(name)
        if not entry or name in self.finished:
            return
        entry[3].setEnabled(False)
        entry[3].setText("Stopping...")
        self.interrupt_requested.emit(name)

    def _on_interrupt_all(self):
        self.interrupt_all_btn.setEnabled(False)
        self.interrupt_all_btn.setText("Stopping...")
        for name, (_c, _l, _b, btn) in self.cards.items():
            if name not in self.finished:
                btn.setEnabled(False)
                btn.setText("Stopping...")
        self.interrupt_all_requested.emit()

    def update_target(self, name, current, total, failed):
        if name not in self.cards or name in self.finished:
            return
        _card, label, bar, _btn = self.cards[name]
        label.setText(f"{name} - {current:,} / {total:,} - {failed:,} failed")
        bar.setValue(current)
        self.totals[name] = [total, current, failed]
        self._refresh_total()

    def complete_target(self, name, sent, failed):
        """Finished normally: green gradient + tight glow."""
        if name not in self.cards:
            return
        _card, label, bar, btn = self.cards[name]
        self.finished.add(name)
        btn.setEnabled(False)
        btn.setText("Done")
        label.setText(f"{name} - Complete - {sent:,} sent - {failed:,} failed")
        bar.setValue(bar.maximum())
        color = COLORS["success"] if failed == 0 else COLORS["warning"]
        bar.setStyleSheet(
            f"QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {color}, stop:1 #00B26E); border-radius: 6px; }}"
        )
        _glow(bar, color, blur_radius=20)
        self.totals[name] = [sent + failed, sent + failed, failed]
        self._refresh_total()

    def mark_interrupted(self, name, sent, failed):
        """Stopped early: amber bar stays at the point it reached."""
        if name not in self.cards:
            return
        _card, label, bar, btn = self.cards[name]
        self.finished.add(name)
        btn.setEnabled(False)
        btn.setText("Stopped")
        label.setText(f"{name} - Interrupted - {sent:,} sent - {failed:,} failed")
        bar.setStyleSheet(
            f"QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {COLORS['warning']}, stop:1 #FF8A00); border-radius: 6px; }}"
        )
        _glow(bar, COLORS["warning"], blur_radius=16)
        total = self.totals[name][0]
        self.totals[name] = [total, sent + failed, failed]
        self._refresh_total()

    # -- overall ------------------------------------------------------- #
    def _refresh_total(self):
        total_all = sum(t[0] for t in self.totals.values())
        current_all = sum(t[1] for t in self.totals.values())
        failed_all = sum(t[2] for t in self.totals.values())
        self.total_bar.setRange(0, max(total_all, 1))
        self.total_bar.setValue(current_all)
        text = f"Overall progress - {current_all:,} / {total_all:,} - {failed_all:,} failed"

        all_finished = bool(self.cards) and len(self.finished) == len(self.cards)
        any_active = bool(self.cards) and not all_finished
        if self.interrupt_all_btn.text() != "Stopping...":
            self.interrupt_all_btn.setEnabled(any_active)

        if total_all and current_all >= total_all and not self.total_bar_completed:
            self.total_bar_completed = True
            color = COLORS["success"]
            self.total_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                f"stop:0 {color}, stop:0.5 {COLORS['accent']}, stop:1 {color}); border-radius: 6px; }}"
            )
            _glow(self.total_bar, color, blur_radius=26)
        elif total_all and current_all < total_all:
            if self.total_bar_completed:
                self._style_total_bar_in_progress()
                _glow(self.total_bar, COLORS["accent"], blur_radius=16)
            self.total_bar_completed = False
            if all_finished:
                text += " - interrupted"
                self.interrupt_all_btn.setText("Interrupt all")
        self.total_label.setText(text)
