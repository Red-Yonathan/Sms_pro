"""
progress_panel.py
====================
Overall progress bar (with golden firefly pulsating glow, distinct obsidian-amber
card, live elapsed timer, and phones/sec speed indicator) plus an "Interrupt all"
button and "Pause/Resume" button.
Per-target cards display individual progress bars, live timers, and sending speed.
"""
import time
import math
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QTimer
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
    btn.setStyleSheet("padding: 2px 12px;")
    btn.setEnabled(False)
    return btn


class LiveProgressPanel(QWidget):
    interrupt_requested = Signal(str)      # target name
    interrupt_all_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # -- Overall Progress Card with distinct obsidian-amber glass & golden border --
        self.total_card = QFrame()
        self.total_card.setAttribute(Qt.WA_StyledBackground, True)
        self.total_card.setObjectName("OverallProgressCard")
        _glow(self.total_card, "#FF9500", blur_radius=22, offset=(0, 2))

        tl = QVBoxLayout(self.total_card)
        tl.setContentsMargins(18, 14, 18, 14)
        tl.setSpacing(8)

        head = QHBoxLayout()
        self.total_label = QLabel("Overall progress - 0 / 0")
        self.total_label.setObjectName("SectionTitle")
        self.total_label.setStyleSheet("color: #FFF3C4; font-weight: 750;")
        head.addWidget(self.total_label, 1)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setObjectName("PauseButton")
        self.pause_btn.setFixedHeight(30)
        self.pause_btn.setMinimumWidth(82)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_toggle_pause)
        head.addWidget(self.pause_btn)

        self.interrupt_all_btn = _interrupt_button("Interrupt all")
        self.interrupt_all_btn.clicked.connect(self._on_interrupt_all)
        head.addWidget(self.interrupt_all_btn)
        tl.addLayout(head)

        self.reconnect_banner = QFrame()
        self.reconnect_banner.setObjectName("ReconnectBanner")
        rb = QHBoxLayout(self.reconnect_banner)
        rb.setContentsMargins(10, 6, 10, 6)
        rb.setSpacing(8)
        r_icon = QLabel("⚠️")
        self.reconnect_label = QLabel("Retrying to connect to the server...")
        self.reconnect_label.setObjectName("ReconnectText")
        rb.addWidget(r_icon)
        rb.addWidget(self.reconnect_label, 1)
        self.reconnect_banner.hide()
        tl.addWidget(self.reconnect_banner)

        # -- Capsule Progress Bar with Fiery Incandescent Chunk --
        self.total_bar = QProgressBar()
        self.total_bar.setObjectName("OverallProgressBar")
        self.total_bar.setFixedHeight(20)
        self.total_bar.setRange(0, 1)
        self.total_bar.setValue(0)
        self._style_total_bar_in_progress()

        # Dynamic pulsating firefly glow effect
        self._total_glow = QGraphicsDropShadowEffect(self.total_bar)
        self._total_glow.setBlurRadius(20)
        self._total_glow.setColor(QColor(255, 175, 0, 190))
        self._total_glow.setOffset(0, 0)
        self.total_bar.setGraphicsEffect(self._total_glow)
        tl.addWidget(self.total_bar)
        lay.addWidget(self.total_card)

        # Firefly pulsating glow timer (gentle 120ms tick, active only when sending)
        self._glow_phase = 0.0
        self._glow_timer = QTimer(self)
        self._glow_timer.setInterval(120)
        self._glow_timer.timeout.connect(self._pulse_firefly_glow)

        self._is_expanded = False

        # -- Process Section Header with Expand / Collapse Arrow Button --
        self.sub_header = QWidget()
        sh_row = QHBoxLayout(self.sub_header)
        sh_row.setContentsMargins(4, 2, 4, 0)
        self.sub_title = QLabel("Processes in Progress")
        self.sub_title.setStyleSheet("font-size: 12px; font-weight: 750; color: #80F8FF;")
        sh_row.addWidget(self.sub_title, 1)

        self.expand_btn = QPushButton("▼ Show all")
        self.expand_btn.setObjectName("SecondaryButton")
        self.expand_btn.setFixedHeight(26)
        self.expand_btn.setStyleSheet(
            "padding: 2px 10px; font-size: 11px; font-weight: 650; "
            "color: #FFE082; border: 1px solid rgba(255, 175, 0, 0.45); "
            "border-radius: 6px; background: rgba(30, 20, 10, 0.55);"
        )
        self.expand_btn.setCursor(Qt.PointingHandCursor)
        self.expand_btn.clicked.connect(self._toggle_expand)
        sh_row.addWidget(self.expand_btn, 0)
        self.sub_header.hide()
        lay.addWidget(self.sub_header)

        # -- Container for per-target progress cards --
        self.container = QWidget()
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(7)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("ProgressScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.container)
        self.scroll.hide()
        lay.addWidget(self.scroll)

        self.cards = {}       # name -> (card, label, bar, button)
        self.totals = {}      # name -> [total, current, failed]
        self.finished = set()
        self.total_bar_completed = False
        self.is_paused = False
        self.is_reconnecting = False
        self.connection_lost_time = None

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(1000)
        self._reconnect_timer.timeout.connect(self._update_reconnect_timer)

        # -- Live Sending Stats (Elapsed Timer & Phones/Sec Speed) --
        self._sending_active = False
        self._start_time = None
        self._paused_duration = 0.0
        self._pause_start = None
        self._history = []            # list of (timestamp, total_sent)
        self._target_history = {}     # name -> list of (timestamp, sent)
        self._last_speed_str = "0.0 phones/s"
        self._final_elapsed_str = ""
        self._final_avg_speed = 0.0

        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(400)
        self._stats_timer.timeout.connect(self._update_stats_tick)

    # -- Firefly pulsating glow animation ---------------------------- #
    def _pulse_firefly_glow(self):
        self._glow_phase = (self._glow_phase + 0.08) % (2 * math.pi)
        pulse = (math.sin(self._glow_phase) + 1.0) / 2.0  # 0.0 to 1.0
        blur = int(16 + pulse * 18)   # 16 to 34px
        alpha = int(140 + pulse * 105) # 140 to 245

        if self.is_reconnecting:
            color = QColor(255, 23, 68, alpha)
        elif self.total_bar_completed:
            color = QColor(0, 255, 157, alpha)
        elif bool(self.finished) and len(self.finished) == len(self.cards) and self.total_bar.value() < self.total_bar.maximum():
            color = QColor(255, 140, 0, alpha)
        else:
            color = QColor(255, 175, 0, alpha)

        self._total_glow.setBlurRadius(blur)
        self._total_glow.setColor(color)

    # -- Styling ----------------------------------------------------- #
    def _style_total_bar_in_progress(self):
        self.total_bar.setStyleSheet(
            "QProgressBar#OverallProgressBar {"
            "  background: rgba(18, 12, 6, 0.85);"
            "  border: 1.2px solid rgba(255, 165, 0, 0.35);"
            "  border-radius: 10px;"
            "  height: 20px;"
            "  text-align: center;"
            "  color: transparent;"
            "}"
            "QProgressBar#OverallProgressBar::chunk {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            "    stop:0 #FF5500, stop:0.22 #FF9100, stop:0.48 #FFEA00,"
            "    stop:0.62 #FFFDE7, stop:0.78 #FFD600, stop:1 #FF8F00);"
            "  border-radius: 9px;"
            "}"
        )

    def show_reconnecting(self, lost_time=None):
        if lost_time is None:
            lost_time = datetime.now()
        self.connection_lost_time = lost_time
        self.is_reconnecting = True
        self.reconnect_banner.show()
        # Red total bar
        self.total_bar.setStyleSheet(
            "QProgressBar#OverallProgressBar {"
            "  background: rgba(28, 8, 12, 0.85);"
            "  border: 1.2px solid rgba(255, 51, 102, 0.50);"
            "  border-radius: 10px;"
            "  height: 20px;"
            "  text-align: center;"
            "  color: transparent;"
            "}"
            "QProgressBar#OverallProgressBar::chunk {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            "    stop:0 #FF3366, stop:0.5 #FF1744, stop:1 #D50000);"
            "  border-radius: 9px;"
            "}"
        )
        self._update_reconnect_timer()
        if not self._reconnect_timer.isActive():
            self._reconnect_timer.start()

    def hide_reconnecting(self):
        self.is_reconnecting = False
        self.reconnect_banner.hide()
        self._reconnect_timer.stop()
        if self.total_bar_completed:
            self._set_total_bar_completed_style()
        else:
            self._style_total_bar_in_progress()

    def _set_total_bar_completed_style(self):
        self.total_bar.setStyleSheet(
            "QProgressBar#OverallProgressBar {"
            "  background: rgba(6, 24, 16, 0.85);"
            "  border: 1.2px solid rgba(0, 255, 157, 0.45);"
            "  border-radius: 10px;"
            "  height: 20px;"
            "  text-align: center;"
            "  color: transparent;"
            "}"
            "QProgressBar#OverallProgressBar::chunk {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            "    stop:0 #00FF9D, stop:0.45 #69F0AE, stop:0.75 #FFD700, stop:1 #00E676);"
            "  border-radius: 9px;"
            "}"
        )

    def _update_reconnect_timer(self):
        if not self.connection_lost_time:
            return
        lost_str = self.connection_lost_time.strftime("%I:%M %p").lstrip("0")
        elapsed = int(time.time() - self.connection_lost_time.timestamp())
        if elapsed < 60:
            elapsed_str = f"{elapsed}s"
        else:
            elapsed_str = f"{elapsed // 60}m {elapsed % 60}s"
        self.reconnect_label.setText(
            f"Retrying to connect to the server... Connection lost at {lost_str} ({elapsed_str} elapsed)"
        )

    # -- Pause / Resume ---------------------------------------------- #
    def _on_toggle_pause(self):
        if not self.is_paused:
            self.is_paused = True
            self._pause_start = time.time()
            self.pause_btn.setText("Resume")
            self.pause_btn.setProperty("paused", "true")
            self.pause_btn.style().unpolish(self.pause_btn)
            self.pause_btn.style().polish(self.pause_btn)
            self.pause_requested.emit()
        else:
            self.is_paused = False
            if self._pause_start:
                self._paused_duration += (time.time() - self._pause_start)
                self._pause_start = None
            self.pause_btn.setText("Pause")
            self.pause_btn.setProperty("paused", "false")
            self.pause_btn.style().unpolish(self.pause_btn)
            self.pause_btn.style().polish(self.pause_btn)
            self.resume_requested.emit()
        self._refresh_total()

    def set_paused_state(self, is_paused: bool):
        was_paused = self.is_paused
        self.is_paused = bool(is_paused)
        if self.is_paused and not was_paused:
            self._pause_start = time.time()
        elif not self.is_paused and was_paused:
            if self._pause_start:
                self._paused_duration += (time.time() - self._pause_start)
                self._pause_start = None
        self.pause_btn.setText("Resume" if self.is_paused else "Pause")
        self.pause_btn.setProperty("paused", "true" if self.is_paused else "false")
        self.pause_btn.style().unpolish(self.pause_btn)
        self.pause_btn.style().polish(self.pause_btn)
        self._refresh_total()

    # -- Timer & Speed Calculation ----------------------------------- #
    def _start_sending_session(self):
        if not self._sending_active:
            self._sending_active = True
            self._start_time = time.time()
            self._paused_duration = 0.0
            self._pause_start = None
            self._history.clear()
            self._target_history.clear()
            if not self._stats_timer.isActive():
                self._stats_timer.start()
            if not self._glow_timer.isActive():
                self._glow_timer.start()

    def _get_active_elapsed(self):
        if not self._start_time:
            return 0.0
        if self.is_paused and self._pause_start:
            return max(0.0, (self._pause_start - self._start_time) - self._paused_duration)
        return max(0.0, (time.time() - self._start_time) - self._paused_duration)

    @staticmethod
    def _format_time(seconds: float) -> str:
        s = int(max(0.0, seconds))
        mins, secs = divmod(s, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def _calc_speed(self, history, current_count, elapsed):
        if self.is_paused:
            return 0.0, "0.0 phones/s (Paused)"
        now = time.time()
        # Keep samples from the last 3.5 seconds
        while history and (now - history[0][0]) > 3.5:
            history.pop(0)

        if len(history) >= 2:
            dt = history[-1][0] - history[0][0]
            dn = history[-1][1] - history[0][1]
            if dt >= 0.20:
                speed = dn / dt
                return speed, f"{speed:.1f} phones/s"

        if elapsed >= 0.8 and current_count > 0:
            speed = current_count / elapsed
            return speed, f"{speed:.1f} phones/s"
        return 0.0, "0.0 phones/s"

    def _update_stats_tick(self):
        if not self._sending_active:
            return
        self._refresh_total()

    # -- Responsive Process Layout & Expand/Collapse ---------------- #
    def _toggle_expand(self):
        self._is_expanded = not self._is_expanded
        self._update_panel_dimensions()

    def _update_panel_dimensions(self):
        count = len(self.cards)
        if count == 0:
            self.sub_header.hide()
            self.scroll.hide()
            return

        self.sub_header.show()
        self.scroll.show()
        self.sub_title.setText(f"Active Processes ({count})")

        card_h = 72
        spacing = 7
        padding = 10

        if count > 6:
            self.expand_btn.show()
            if self._is_expanded:
                self.expand_btn.setText("▲ Snap to 6")
                self.expand_btn.setToolTip("Click to collapse process view back to 6 items")
                parent_win = self.window()
                screen_h = parent_win.height() if (parent_win and parent_win.height() > 300) else 800
                max_h = max(450, int(screen_h * 0.55))
                needed_h = count * card_h + (count - 1) * spacing + padding
                final_h = min(needed_h, max_h)
                self.scroll.setFixedHeight(final_h)
            else:
                self.expand_btn.setText(f"▼ Show all ({count})")
                self.expand_btn.setToolTip(f"Click to show all {count} process bars")
                target_h = 6 * card_h + 5 * spacing + padding
                self.scroll.setFixedHeight(target_h)
        else:
            self.expand_btn.hide()
            self._is_expanded = False
            target_h = count * card_h + max(0, count - 1) * spacing + padding
            self.scroll.setFixedHeight(target_h)

    # -- Reset ------------------------------------------------------- #
    def reset(self):
        self.hide_reconnecting()
        self.is_paused = False
        self._sending_active = False
        self._start_time = None
        self._paused_duration = 0.0
        self._pause_start = None
        self._history.clear()
        self._target_history.clear()
        self._stats_timer.stop()
        self._glow_timer.stop()
        self._final_elapsed_str = ""
        self._final_avg_speed = 0.0

        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause")
        self.pause_btn.setProperty("paused", "false")
        self.pause_btn.style().unpolish(self.pause_btn)
        self.pause_btn.style().polish(self.pause_btn)

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
        self.interrupt_all_btn.setEnabled(False)
        self.interrupt_all_btn.setText("Interrupt all")
        self.total_bar_completed = False
        self._is_expanded = False
        self._update_panel_dimensions()

    # -- Targets ----------------------------------------------------- #
    def add_target(self, name, total):
        self._start_sending_session()
        self.pause_btn.setEnabled(True)

        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 11, 14, 11)
        lay.setSpacing(6)

        head = QHBoxLayout()
        label = QLabel(f"{name} - 0 / {total:,} (0.0%) | ⏱ 00:00 | ⚡ 0.0 phones/s")
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
        self._target_history[name] = [(time.time(), 0)]
        self._refresh_total()
        self._update_panel_dimensions()

    def _on_interrupt(self, name):
        entry = self.cards.get(name)
        if not entry or name in self.finished:
            return
        entry[3].setEnabled(False)
        entry[3].setText("Stopping...")
        self.interrupt_requested.emit(name)

    def _on_interrupt_all(self):
        self.hide_reconnecting()
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause")
        self.pause_btn.setProperty("paused", "false")
        self.is_paused = False
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
        now = time.time()
        tgt_hist = self._target_history.setdefault(name, [])
        tgt_hist.append((now, current))
        self.totals[name] = [total, current, failed]

        # Record overall history
        total_current = sum(t[1] for t in self.totals.values())
        self._history.append((now, total_current))

        # Update target card
        _card, label, bar, _btn = self.cards[name]
        bar.setValue(current)
        pct = (current / total * 100.0) if total else 0.0
        elapsed = self._get_active_elapsed()
        _sp_num, sp_str = self._calc_speed(tgt_hist, current, elapsed)
        time_str = self._format_time(elapsed)
        label.setText(f"{name} - {current:,} / {total:,} ({pct:.1f}%) | ⏱ {time_str} | ⚡ {sp_str} - {failed:,} failed")

        self._refresh_total()

    def complete_target(self, name, sent, failed):
        """Finished normally: green gradient + tight glow."""
        if name not in self.cards:
            return
        _card, label, bar, btn = self.cards[name]
        self.finished.add(name)
        btn.setEnabled(False)
        btn.setText("Done")
        bar.setValue(bar.maximum())
        color = COLORS["success"] if failed == 0 else COLORS["warning"]
        bar.setStyleSheet(
            f"QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {color}, stop:1 #00B26E); border-radius: 6px; }}"
        )
        _glow(bar, color, blur_radius=20)
        self.totals[name] = [sent + failed, sent + failed, failed]

        elapsed = self._get_active_elapsed()
        time_str = self._format_time(elapsed)
        avg_speed = ((sent + failed) / elapsed) if elapsed > 0 else 0.0
        label.setText(f"{name} - Complete - {sent:,} sent - {failed:,} failed | ⏱ {time_str} | Avg ⚡ {avg_speed:.1f} phones/s")
        self._refresh_total()

    def mark_interrupted(self, name, sent, failed):
        """Stopped early: amber bar stays at the point it reached."""
        if name not in self.cards:
            return
        _card, label, bar, btn = self.cards[name]
        self.finished.add(name)
        btn.setEnabled(False)
        btn.setText("Stopped")
        bar.setStyleSheet(
            f"QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {COLORS['warning']}, stop:1 #FF8A00); border-radius: 6px; }}"
        )
        _glow(bar, COLORS["warning"], blur_radius=16)
        total = self.totals[name][0]
        self.totals[name] = [total, sent + failed, failed]

        elapsed = self._get_active_elapsed()
        time_str = self._format_time(elapsed)
        label.setText(f"{name} - Interrupted - {sent:,} sent - {failed:,} failed | ⏱ {time_str}")
        self._refresh_total()

    # -- Overall Refresh --------------------------------------------- #
    def _refresh_total(self):
        total_all = sum(t[0] for t in self.totals.values())
        current_all = sum(t[1] for t in self.totals.values())
        failed_all = sum(t[2] for t in self.totals.values())

        self.total_bar.setRange(0, max(total_all, 1))
        self.total_bar.setValue(current_all)

        all_finished = bool(self.cards) and len(self.finished) == len(self.cards)
        any_active = bool(self.cards) and not all_finished

        if self.interrupt_all_btn.text() != "Stopping...":
            self.interrupt_all_btn.setEnabled(any_active)

        if any_active:
            self.pause_btn.setEnabled(True)
        elif all_finished:
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("Pause")
            self.pause_btn.setProperty("paused", "false")
            self.is_paused = False
            self.hide_reconnecting()

        elapsed = self._get_active_elapsed()
        time_str = self._format_time(elapsed)
        _sp_num, sp_str = self._calc_speed(self._history, current_all, elapsed)
        pct = (current_all / total_all * 100.0) if total_all else 0.0

        if total_all and current_all >= total_all and not self.total_bar_completed:
            self.total_bar_completed = True
            self._set_total_bar_completed_style()
            self._stats_timer.stop()
            self._glow_timer.stop()
            self._sending_active = False
            avg_speed = (current_all / elapsed) if elapsed > 0 else 0.0
            self.total_label.setText(
                f"Overall progress - Complete - {current_all:,} / {total_all:,} (100%) | ⏱ {time_str} | Avg ⚡ {avg_speed:.1f} phones/s - {failed_all:,} failed"
            )
            return

        if total_all and current_all < total_all:
            if self.total_bar_completed:
                self._style_total_bar_in_progress()
            self.total_bar_completed = False
            if all_finished:
                self._stats_timer.stop()
                self._glow_timer.stop()
                self._sending_active = False
                self.interrupt_all_btn.setText("Interrupt all")
                self.total_label.setText(
                    f"Overall progress - Interrupted - {current_all:,} / {total_all:,} ({pct:.1f}%) | ⏱ {time_str} - {failed_all:,} failed"
                )
                return

        # Active or idle text
        if total_all > 0:
            self.total_label.setText(
                f"Overall progress - {current_all:,} / {total_all:,} ({pct:.1f}%) | ⏱ {time_str} | ⚡ {sp_str} - {failed_all:,} failed"
            )
        else:
            self.total_label.setText("Overall progress - 0 / 0")
