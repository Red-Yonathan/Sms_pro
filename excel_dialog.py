"""
excel_dialog.py
=================
When a spreadsheet is added, we need to know which column holds the
phone numbers. ExcelColumnDialog previews the file and either confirms
an auto-detected column, or lets you type/click one manually --
optionally remembering that choice for every other spreadsheet found
in this batch/project ("Use this column for all").
"""
import os
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QCheckBox, QScrollArea, QWidget,
    QGridLayout, QMessageBox, QHeaderView,
)

from phone_utils import detect_phone_column, truncate_cell, read_table_preview


class ExcelColumnDialog(QDialog):
    """On accept: self.chosen_column (str) and self.use_for_all (bool)
    are set. On reject/skip, self.chosen_column stays None."""

    def __init__(self, file_name, df_preview, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Phone column - {file_name}")
        self.setModal(True)
        self.resize(780, 520)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        self.df = df_preview
        self.detected = detect_phone_column(self.df.columns)
        self.chosen_column = None
        self.use_for_all = False
        self._build(file_name)

    def _build(self, file_name):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(12)

        title = QLabel("Excel file detected")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        sub = QLabel(file_name)
        sub.setObjectName("Muted")
        root.addWidget(sub)

        if self.detected:
            msg = QLabel(f'Phone_number column found: "{self.detected}". Use it to fetch phone numbers?')
            msg.setStyleSheet("color:#00FF9D; font-weight:700;")
        else:
            msg = QLabel(
                'No column named "Phone_number", "Phone" or "Phone Number" was found. '
                "Pick the right column below, or type its exact name."
            )
            msg.setStyleSheet("color:#FF3366; font-weight:700;")
        msg.setWordWrap(True)
        root.addWidget(msg)

        preview_label = QLabel("Preview (first 5 rows) - scroll to see more columns")
        preview_label.setObjectName("SectionTitle")
        root.addWidget(preview_label)

        self.table = QTableWidget()
        columns = list(self.df.columns)
        rows = self.df.head(5)
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels([str(c) for c in columns])
        self.table.setRowCount(len(rows))
        for r in range(len(rows)):
            for c in range(len(columns)):
                val = rows.iloc[r, c]
                item = QTableWidgetItem(truncate_cell(val))
                item.setToolTip("" if val is None else str(val))
                self.table.setItem(r, c, item)
        self.table.setMinimumHeight(170)
        self.table.setMaximumHeight(220)
        self.table.horizontalHeader().setMinimumSectionSize(95)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table)

        entry_row = QHBoxLayout()
        entry_row.addWidget(QLabel("Column name:"))
        self.entry = QLineEdit(self.detected or "")
        entry_row.addWidget(self.entry, 1)
        self.yes_btn = QPushButton("Yes, use this column")
        self.yes_btn.setObjectName("PrimaryButton")
        self.yes_btn.clicked.connect(self._accept_column)
        entry_row.addWidget(self.yes_btn)
        root.addLayout(entry_row)

        autofill_label = QLabel("Or click a column name to autofill:")
        autofill_label.setObjectName("TinyMuted")
        root.addWidget(autofill_label)

        autofill_scroll = QScrollArea()
        autofill_scroll.setWidgetResizable(True)
        autofill_scroll.setMaximumHeight(96)
        autofill_container = QWidget()
        grid = QGridLayout(autofill_container)
        grid.setContentsMargins(0, 0, 0, 0)
        max_cols = 4
        for i, col in enumerate(columns):
            btn = QPushButton(str(col))
            btn.clicked.connect(lambda _checked, c=str(col): self.entry.setText(c))
            grid.addWidget(btn, i // max_cols, i % max_cols)
        autofill_scroll.setWidget(autofill_container)
        root.addWidget(autofill_scroll)

        self.for_all_check = QCheckBox("Use this column name for all remaining Excel files")
        root.addWidget(self.for_all_check)

        buttons = QHBoxLayout()
        buttons.addStretch()
        skip_btn = QPushButton("Skip this file")
        skip_btn.setObjectName("DangerButton")
        skip_btn.clicked.connect(self.reject)
        buttons.addWidget(skip_btn)
        root.addLayout(buttons)

    def _accept_column(self):
        name = self.entry.text().strip()
        columns = [str(c) for c in self.df.columns]
        if not name or name not in columns:
            QMessageBox.warning(self, "Column not found", f'"{name}" is not a column in this file.')
            return
        self.chosen_column = name
        self.use_for_all = self.for_all_check.isChecked()
        self.accept()


def resolve_excel_columns(paths, parent_widget, log_callback, for_all_column):
    """Walks `paths`; for every .xlsx/.xls file, resolves which column
    holds phone numbers (auto, remembered "for all", or via dialog).
    Returns (resolved_paths, overrides_dict, updated_for_all_column).
    Non-excel paths pass through untouched. Files that can't be read,
    or where the user skips the picker, are dropped (and logged).
    """
    resolved = []
    overrides = {}
    for path in paths:
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".xlsx", ".xls"):
            resolved.append(path)
            continue
        try:
            df_head = read_table_preview(path, n_rows=5)
        except Exception as exc:
            log_callback("error", f"{os.path.basename(path)}: could not read Excel file ({exc})")
            continue
        if df_head is None or df_head.empty or len(df_head.columns) == 0:
            log_callback("error", f"{os.path.basename(path)}: Excel file has no columns")
            continue
        columns = list(df_head.columns)
        if for_all_column and for_all_column in columns:
            overrides[path] = for_all_column
            resolved.append(path)
            continue
        dialog = ExcelColumnDialog(os.path.basename(path), df_head, parent_widget)
        if dialog.exec() == QDialog.Accepted and dialog.chosen_column:
            overrides[path] = dialog.chosen_column
            if dialog.use_for_all:
                for_all_column = dialog.chosen_column
            resolved.append(path)
        else:
            log_callback("info", f"Skipped {os.path.basename(path)} (no column chosen)")
    return resolved, overrides, for_all_column
