"""
progress_panel.py
====================
One overall progress bar (turns green + gradient glow when the whole
batch finishes) plus a scrollable stack of per-target bars (turn green
with their OWN, differently-themed glow the moment that target
finishes). Used by both the Batch page and Project workspace so the
"live sending" look is consistent everywhere.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QScrollArea, QFrame,
    QGraphicsDropShadowEffect,
)
from PySide6.QtGui import QColor

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


class LiveProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        total_card = QFrame()
        total_card.setObjectName("Card")
        tl = QVBoxLayout(total_card)
        tl.setContentsMargins(16, 13, 16, 13)
        self.total_label = QLabel("Overall progress - 0 / 0")
        self.total_label.setObjectName("SectionTitle")
        self.total_bar = QProgressBar()
        self.total_bar.setRange(0, 1)
        self.total_bar.setValue(0)
        _glow(self.total_bar, COLORS["accent"], blur_radius=16, offset=(0, 0))
        tl.addWidget(self.total_label)
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

        self.cards = {}     # name -> (card, label, bar)
        self.totals = {}    # name -> [total, current, failed]
        self.total_bar_completed = False

    def reset(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards.clear()
        self.totals.clear()
        self.total_bar.setRange(0, 1)
        self.total_bar.setValue(0)
        self.total_label.setText("Overall progress - 0 / 0")
        self.total_bar.setStyleSheet("")
        _glow(self.total_bar, COLORS["accent"], blur_radius=16, offset=(0, 0))
        self.total_bar_completed = False

    def add_target(self, name, total):
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(13, 11, 13, 11)
        lay.setSpacing(5)
        label = QLabel(f"{name} - 0 / {total:,}")
        label.setObjectName("SectionTitle")
        bar = QProgressBar()
        bar.setRange(0, max(total, 1))
        bar.setValue(0)
        _glow(bar, COLORS["accent"], blur_radius=12, offset=(0, 0))
        lay.addWidget(label)
        lay.addWidget(bar)
        self.card_layout.addWidget(card)
        self.cards[name] = (card, label, bar)
        self.totals[name] = [total, 0, 0]
        self._refresh_total()

    def update_target(self, name, current, total, failed):
        if name not in self.cards:
            return
        _card, label, bar = self.cards[name]
        label.setText(f"{name} - {current:,} / {total:,} - {failed:,} failed")
        bar.setValue(current)
        self.totals[name] = [total, current, failed]
        self._refresh_total()

    def complete_target(self, name, sent, failed):
        """Per-file completion theme: solid success-green gradient with
        a tight, warm glow -- deliberately different from the overall
        bar's cooler cyan/green sweep below."""
        if name not in self.cards:
            return
        _card, label, bar = self.cards[name]
        label.setText(f"{name} - Complete - {sent:,} sent - {failed:,} failed")
        bar.setValue(bar.maximum())
        color = COLORS["success"] if failed == 0 else COLORS["warning"]
        bar.setStyleSheet(
            f"QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {color}, stop:1 #00B26E); border-radius: 6px; }}"
        )
        _glow(bar, color, blur_radius=20, offset=(0, 0))
        self.totals[name] = [sent + failed, sent + failed, failed]
        self._refresh_total()

    def _refresh_total(self):
        total_all = sum(t[0] for t in self.totals.values())
        current_all = sum(t[1] for t in self.totals.values())
        failed_all = sum(t[2] for t in self.totals.values())
        self.total_bar.setRange(0, max(total_all, 1))
        self.total_bar.setValue(current_all)
        self.total_label.setText(
            f"Overall progress - {current_all:,} / {total_all:,} - {failed_all:,} failed"
        )
        if total_all and current_all >= total_all and not self.total_bar_completed:
            self.total_bar_completed = True
            color = COLORS["success"]
            self.total_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                f"stop:0 {color}, stop:0.5 {COLORS['accent']}, stop:1 {color}); border-radius: 6px; }}"
            )
            _glow(self.total_bar, color, blur_radius=26, offset=(0, 0))
        elif total_all and current_all < total_all:
            self.total_bar_completed = False
