"""
project_ui.py
===============
Everything for the "Projects" nav tab:
  - ProjectsPage: grid of project cards ("+ New Project", delete)
  - NewProjectDialog: name entry
  - ProjectWorkspaceDialog: deliberately mirrors the Batch page --
    same message box, same checkbox+delete file rows, same
    select-all/uncheck-all, same overall+per-file live progress, same
    activity log -- but everything is backed by the project's on-disk
    manifest, so:
      * tracked files/phones persist across closing and reopening
        the project (no re-adding files every time)
      * each file's row shows how many of its numbers are already
        sent (count + percent), not just a raw count
      * "send" only ever sends the CHECKED files' still-unsent
        numbers -- selection IS the "send some, not all" control
"""
import os
from datetime import datetime

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QMessageBox, QFileDialog,
    QListWidget, QListWidgetItem, QSizePolicy, QPlainTextEdit,
    QAbstractItemView, QSizeGrip, QCheckBox,
)

from theme import COLORS
from ui_common import (Card, apply_glow, attach_focus_glow, enable_dark_titlebar, UnicodeTextEdit,
                       build_file_row, set_row_done, open_folder)
from phone_utils import SUPPORTED_EXTENSIONS
from file_loader import FileLoadWorker
from excel_dialog import resolve_excel_columns
from sender import SendingWorker
from progress_panel import LiveProgressPanel
from projects import ProjectManager, record_result, sendable_phones


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New project")
        self.setModal(True)
        self.resize(420, 200)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        enable_dark_titlebar(int(self.winId()))
        self.project_name = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        title = QLabel("Create a new project")
        title.setObjectName("DialogTitle")
        root.addWidget(title)
        hint = QLabel("A folder with this name will be created inside the Projects folder.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.name_entry = QLineEdit()
        self.name_entry.setPlaceholderText("e.g. September Promo Campaign")
        attach_focus_glow(self.name_entry)
        root.addWidget(self.name_entry)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        create = QPushButton("Create")
        create.setObjectName("PrimaryButton")
        apply_glow(create, COLORS["accent"], blur_radius=14, offset=(0, 2))
        create.clicked.connect(self._create)
        buttons.addWidget(cancel)
        buttons.addWidget(create)
        root.addLayout(buttons)

    def _create(self):
        name = self.name_entry.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Enter a project name.")
            return
        self.project_name = name
        self.accept()


class ProjectCardWidget(QWidget):
    def __init__(self, folder_name, valid, manifest_or_none, on_open, on_delete, parent=None):
        super().__init__(parent)
        card = Card()
        card.setObjectName("ProjectCard" if valid else "ProjectCardInvalid")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)

        name_row = QHBoxLayout()
        name_label = QLabel(manifest_or_none.get("name", folder_name) if valid else folder_name)
        name_label.setObjectName("ProjectName")
        name_row.addWidget(name_label, 1)
        delete_btn = QPushButton("X")
        delete_btn.setObjectName("DeleteButton")
        delete_btn.setFixedSize(26, 26)
        delete_btn.setToolTip(f'Delete project "{folder_name}"')
        delete_btn.clicked.connect(lambda: on_delete(folder_name))
        name_row.addWidget(delete_btn)
        lay.addLayout(name_row)

        if valid:
            created = manifest_or_none.get("created_at", "?")
            meta = QLabel(f"Created {created}")
            meta.setObjectName("TinyMuted")
            lay.addWidget(meta)
            stats = ProjectManager.stats(manifest_or_none)
            summary = QLabel(
                f"{stats['total']:,} tracked - {stats['sent']:,} sent - "
                f"{stats['failed']:,} failed - {stats['unsent']:,} unsent"
            )
            summary.setObjectName("Muted")
            lay.addWidget(summary)
            open_btn = QPushButton("Open project")
            open_btn.setObjectName("PrimaryButton")
            apply_glow(open_btn, COLORS["accent"], blur_radius=12, offset=(0, 2))
            open_btn.clicked.connect(lambda: on_open(folder_name))
            lay.addWidget(open_btn)
        else:
            warn = QLabel("Not created by this app (missing or invalid project marker)")
            warn.setObjectName("ProjectWarn")
            warn.setWordWrap(True)
            lay.addWidget(warn)
            disabled_btn = QPushButton("Cannot open")
            disabled_btn.setEnabled(False)
            lay.addWidget(disabled_btn)


class ProjectsPage(QWidget):
    """Embedded directly in the main window's page stack."""
    def __init__(self, project_manager: ProjectManager, main_window, parent=None):
        super().__init__(parent)
        self.pm = project_manager
        self.main_window = main_window
        self.setObjectName("ProjectsPage")
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 38)
        root.setSpacing(18)

        heading_row = QHBoxLayout()
        heading_box = QVBoxLayout()
        title = QLabel("Projects")
        title.setObjectName("PageTitle")
        sub = QLabel("Group target files under a named project; each file/phone's sent status is tracked and saved.")
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        heading_box.addWidget(title)
        heading_box.addWidget(sub)
        heading_row.addLayout(heading_box, 1)
        new_btn = QPushButton("+ New Project")
        new_btn.setObjectName("SmallPrimaryButton")
        new_btn.setFixedHeight(38)
        apply_glow(new_btn, COLORS["accent"], blur_radius=14, offset=(0, 2))
        new_btn.clicked.connect(self.create_project)
        heading_row.addWidget(new_btn, 0, Qt.AlignTop)
        root.addLayout(heading_row)

        self.grid_container = QWidget()
        self.grid = QGridLayout(self.grid_container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_container)
        root.addWidget(scroll, 1)

        self.refresh()

    def create_project(self):
        dialog = NewProjectDialog(self.main_window)
        if dialog.exec() == QDialog.Accepted and dialog.project_name:
            self.pm.create_project(dialog.project_name)
            self.refresh()

    def open_project(self, folder_name):
        workspace = ProjectWorkspaceDialog(self.pm, folder_name, self.main_window)
        workspace.exec()
        self.refresh()

    def delete_project(self, folder_name):
        answer = QMessageBox.question(
            self.main_window, "Delete project",
            f'Permanently delete the project "{folder_name}"?\n\n'
            "This removes its tracking folder and sent/unsent history. "
            "The original source files you added are NOT deleted.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.pm.delete_project(folder_name)
        self.refresh()

    def refresh(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        folders = self.pm.list_project_dirs()
        cols = 3
        for i, folder_name in enumerate(folders):
            valid = self.pm.is_valid_project(folder_name)
            manifest = self.pm.load_manifest(folder_name) if valid else None
            card = ProjectCardWidget(folder_name, valid, manifest, self.open_project, self.delete_project, self.grid_container)
            self.grid.addWidget(card, i // cols, i % cols, Qt.AlignTop)
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)
        self.grid.setRowStretch((len(folders) // cols) + 1, 1)   # keeps cards compact, pushes them to the top
        if not folders:
            empty = QLabel('No projects yet. Click "+ New Project" to create one.')
            empty.setObjectName("Muted")
            self.grid.addWidget(empty, 0, 0)


class ProjectWorkspaceDialog(QDialog):
    def __init__(self, project_manager: ProjectManager, folder_name, parent=None):
        super().__init__(parent)
        self.pm = project_manager
        self.folder_name = folder_name
        self.manifest = self.pm.load_manifest(folder_name)
        self.active_workers = []
        self.loader = None
        self.excel_for_all_column = getattr(parent, "excel_for_all_column", None)
        # Session-only selection state, keyed by tracked file path.
        # Default: checked only if there's still something unsent --
        # a fully-sent file starts unchecked since there's nothing to do.
        self.checked = {
            path: self._has_work(entry)
            for path, entry in self.manifest.get("files", {}).items()
        }
        # In-memory per-file state used only while sending; flushed to disk
        # every few seconds (never once per number -- projects can hold
        # hundreds of thousands of numbers).
        self.states = {}
        self.names = {}
        self.dirty = set()
        self.meta_labels = {}
        self.rows = {}
        self.workers = {}
        self.flush_timer = QTimer(self)
        self.flush_timer.setInterval(4000)
        self.flush_timer.timeout.connect(self._flush)

        self.setWindowTitle(f"Project - {self.manifest.get('name', folder_name)}")
        self.setModal(True)
        self.resize(1040, 820)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        enable_dark_titlebar(int(self.winId()))
        self._build()
        self._refresh_file_list()

    @staticmethod
    def _is_done(entry):
        st = ProjectManager.file_stats(entry)
        return st["total"] > 0 and (st["unsent"] + st["failed"]) == 0

    @staticmethod
    def _has_work(entry):
        st = ProjectManager.file_stats(entry)
        return (st["unsent"] + st["failed"]) > 0

    # -- UI ------------------------------------------------------------ #
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        head = QHBoxLayout()
        title = QLabel(self.manifest.get("name", self.folder_name))
        title.setObjectName("DialogTitle")
        head.addWidget(title, 1)
        open_project_btn = QPushButton("Open project folder")
        open_project_btn.clicked.connect(lambda: open_folder(self.pm.project_path(self.folder_name)))
        open_reports_btn = QPushButton("Open reports folder")
        open_reports_btn.setObjectName("SmallPrimaryButton")
        open_reports_btn.setFixedHeight(36)
        open_reports_btn.clicked.connect(lambda: open_folder(self.pm.reports_dir(self.folder_name)))
        head.addWidget(open_project_btn)
        head.addWidget(open_reports_btn)
        root.addLayout(head)

        info = QLabel(
            f"Folder: {self.pm.project_path(self.folder_name)}\n"
            f"Reports: {os.path.join(self.pm.project_path(self.folder_name), 'Reports')}   -   "
            f"Created {self.manifest.get('created_at', '?')}"
        )
        info.setObjectName("TinyMuted")
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        # -- message --------------------------------------------------- #
        message_card = Card()
        ml = QVBoxLayout(message_card)
        ml.setContentsMargins(18, 18, 18, 18)
        ml.setSpacing(9)
        mlabel = QLabel("Message")
        mlabel.setObjectName("SectionTitle")
        ml.addWidget(mlabel)
        self.message_box = UnicodeTextEdit()
        self.message_box.setPlaceholderText("Write the message for the checked files' unsent recipients...")
        self.message_box.setMinimumHeight(110)
        self.message_box.setMaximumHeight(170)
        self.message_box.textChanged.connect(self._update_message_count)
        ml.addWidget(self.message_box)
        self.message_char_count = QLabel("0 characters")
        self.message_char_count.setObjectName("TinyMuted")
        self.message_char_count.setAlignment(Qt.AlignRight)
        ml.addWidget(self.message_char_count)
        lay.addWidget(message_card)

        # -- tracked files (mirrors Batch's Target files card) --------- #
        files_card = Card()
        fl = QVBoxLayout(files_card)
        fl.setContentsMargins(18, 16, 18, 16)
        fl.setSpacing(8)
        header = QHBoxLayout()
        ftitle = QLabel("Tracked files")
        ftitle.setObjectName("SectionTitle")
        header.addWidget(ftitle)
        header.addStretch()
        self.add_files_btn = QPushButton("+ Add files")
        self.add_files_btn.clicked.connect(self.add_files)
        self.add_folder_btn = QPushButton("Add folder")
        self.add_folder_btn.clicked.connect(self.add_folder)
        header.addWidget(self.add_files_btn)
        header.addWidget(self.add_folder_btn)
        fl.addLayout(header)

        self.loading_label = QLabel("")
        self.loading_label.setObjectName("Loading")
        fl.addWidget(self.loading_label)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.file_list.setMinimumHeight(240)
        self.file_list.setMaximumHeight(8 * 48 + 6)
        fl.addWidget(self.file_list)

        self.checked_count_label = QLabel("0 files checked")
        self.checked_count_label.setObjectName("TinyMuted")
        fl.addWidget(self.checked_count_label)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.select_all_btn = QPushButton("Select all")
        self.uncheck_all_btn = QPushButton("Uncheck all")
        self.select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        self.uncheck_all_btn.clicked.connect(lambda: self._set_all_checked(False))
        actions.addWidget(self.select_all_btn)
        actions.addWidget(self.uncheck_all_btn)
        actions.addStretch()
        fl.addLayout(actions)

        self.targets_summary = QLabel("No files tracked")
        self.targets_summary.setObjectName("TinyMuted")
        fl.addWidget(self.targets_summary)
        lay.addWidget(files_card)

        # -- send button (small, matches Batch) -------------------------#
        send_btn = QPushButton("Send to checked files")
        send_btn.setObjectName("SmallPrimaryButton")
        send_btn.setFixedHeight(40)
        send_btn.setMinimumWidth(190)
        send_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        apply_glow(send_btn, COLORS["accent"], blur_radius=14, offset=(0, 2))
        send_btn.clicked.connect(self.send_checked)
        self.send_btn = send_btn
        send_row = QHBoxLayout()
        send_row.addWidget(send_btn)
        send_row.addStretch()
        lay.addLayout(send_row)

        self.progress_panel = LiveProgressPanel()
        self.progress_panel.interrupt_requested.connect(self._interrupt_one)
        self.progress_panel.interrupt_all_requested.connect(self._interrupt_all)
        lay.addWidget(self.progress_panel)

        activity_card = Card()
        al = QVBoxLayout(activity_card)
        al.setContentsMargins(18, 15, 18, 15)
        al.addWidget(QLabel("Activity"))
        self.log_box = QPlainTextEdit()
        self.log_box.setObjectName("Log")
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(150)
        self.log_box.document().setMaximumBlockCount(3000)   # keeps the UI fast on huge sends
        al.addWidget(self.log_box)
        lay.addWidget(activity_card)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        bottom_row = QHBoxLayout()
        grip = QSizeGrip(self)
        bottom_row.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignLeft)
        bottom_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(close_btn)
        root.addLayout(bottom_row)

    def _update_message_count(self):
        self.message_char_count.setText(f"{len(self.message_box.toPlainText()):,} characters")

    def _log(self, level, text):
        prefix = {"success": "[OK]", "error": "[ERR]", "info": "[*]"}.get(level, "[*]")
        self.log_box.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {prefix} {text}")
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    # -- file tracking ----------------------------------------------------#
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select phone files", "", "Supported (*.csv *.xlsx *.xls *.json *.txt)"
        )
        if files:
            self._start_tracking(files)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder")
        if not folder:
            return
        paths = []
        for root_dir, _, filenames in os.walk(folder):
            for filename in filenames:
                if os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS:
                    paths.append(os.path.join(root_dir, filename))
        if not paths:
            QMessageBox.information(self, "No supported files", "No CSV, Excel, JSON or TXT files were found in that folder.")
            return
        self._start_tracking(paths)

    def _start_tracking(self, paths):
        if self.loader and self.loader.isRunning():
            return
        paths, overrides, self.excel_for_all_column = resolve_excel_columns(
            paths, self, self._log, self.excel_for_all_column
        )
        if not paths:
            return
        self._set_file_controls_enabled(False)
        self.loading_label.setText(f"Loading 0 / {len(paths)} files...")
        self.loader = FileLoadWorker(paths, overrides, self)
        self.loader.progress.connect(lambda current, total, name: self.loading_label.setText(f"Loading {current} / {total} - {name}"))
        self.loader.file_failed.connect(lambda path, error: self._log("error", f"{os.path.basename(path)}: {error}"))
        self.loader.finished.connect(self._finish_tracking)
        self.loader.start()

    def _finish_tracking(self, results):
        added = 0
        for path, phones in results.items():
            self.manifest = self.pm.add_file_to_manifest(self.folder_name, self.manifest, path, phones)
            self.checked.setdefault(path, True)
            added += 1
        self.loading_label.setText(f"Finished loading - {added:,} file(s) tracked" if added else "")
        self._set_file_controls_enabled(True)
        if added:
            self._log("success", f"Tracking {added} file(s). Checked files are the ones that will be sent.")
        self._refresh_file_list()

    def _set_file_controls_enabled(self, enabled):
        self.add_files_btn.setEnabled(enabled)
        self.add_folder_btn.setEnabled(enabled)
        has_files = bool(self.manifest.get("files"))
        self.select_all_btn.setEnabled(enabled and has_files)
        self.uncheck_all_btn.setEnabled(enabled and has_files)

    def _toggle_file(self, path, state):
        self.checked[path] = bool(state)
        self._update_checked_count()

    def _update_checked_count(self):
        checked = [p for p, v in self.checked.items() if v and p in self.manifest.get("files", {})]
        self.checked_count_label.setText(f"{len(checked):,} file{'s' if len(checked) != 1 else ''} checked")

    def _set_all_checked(self, state):
        for path in self.manifest.get("files", {}):
            self.checked[path] = state
        self._refresh_file_list()

    def _remove_file(self, path):
        name = os.path.basename(path)
        answer = QMessageBox.question(
            self, "Stop tracking file",
            f'Stop tracking "{name}" in this project?\n\n'
            "Its sent/unsent history in this project will be lost. "
            "The original file itself is not deleted.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.manifest = self.pm.remove_file_from_manifest(self.folder_name, self.manifest, path)
        self.checked.pop(path, None)
        self.states.pop(path, None)
        self.dirty.discard(path)
        self._refresh_file_list()

    @staticmethod
    def _meta_text(entry):
        stats = ProjectManager.file_stats(entry)
        percent = (stats["sent"] / stats["total"] * 100) if stats["total"] else 0
        done = "DONE - " if (stats["total"] and stats["unsent"] + stats["failed"] == 0) else ""
        return (f"{done}{stats['total']:,} numbers - {stats['sent']:,} sent ({percent:.0f}%) - "
                f"{stats['failed']:,} failed - {stats['unsent']:,} unsent")

    def _update_summary(self):
        files = self.manifest.get("files", {})
        if files:
            t = ProjectManager.stats(self.manifest)
            self.targets_summary.setText(
                f"{len(files):,} file(s) - {t['total']:,} total - {t['sent']:,} sent - "
                f"{t['failed']:,} failed - {t['unsent']:,} unsent")
        else:
            self.targets_summary.setText("No files tracked")
        self.select_all_btn.setEnabled(bool(files))
        self.uncheck_all_btn.setEnabled(bool(files))

    def _refresh_file_list(self):
        self.file_list.clear()
        self.meta_labels = {}
        self.rows = {}
        for path, entry in self.manifest.get("files", {}).items():
            item = QListWidgetItem()
            item.setSizeHint(QSize(100, 46))
            row = build_file_row(
                display_name=os.path.basename(path),
                meta_text=self._meta_text(entry),
                checked=self.checked.get(path, self._has_work(entry)),
                done=self._is_done(entry),
                tooltip=path,
                on_toggle=lambda state, p=path: self._toggle_file(p, state),
                on_delete=lambda checked, p=path: self._remove_file(p),
                delete_tooltip=f"Stop tracking {os.path.basename(path)}",
            )
            self.meta_labels[path] = row.findChild(QLabel, "FileMeta")
            self.rows[path] = row
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, row)
        self._update_checked_count()
        self._update_summary()

    def _refresh_meta_only(self, path):
        """Cheap live update while sending (no list rebuild -> no scroll jump)."""
        label = self.meta_labels.get(path)
        entry = self.manifest.get("files", {}).get(path)
        if label is not None and entry is not None:
            label.setText(self._meta_text(entry))
        row = self.rows.get(path)
        if row is not None and entry is not None:
            set_row_done(row, self._is_done(entry))
        self._update_summary()

    # -- sending ---------------------------------------------------------#
    def send_checked(self):
        message = self.message_box.toPlainText().strip()
        url = os.environ.get("SMS_API_URL", "").strip()
        key = os.environ.get("SMS_API_KEY", "").strip()
        if not message:
            QMessageBox.warning(self, "Message required", "Enter a message.")
            return
        if not url or not key:
            QMessageBox.warning(self, "API not configured", "Open Settings on the main window first.")
            return
        checked_paths = [p for p, v in self.checked.items() if v and p in self.manifest.get("files", {})]
        if not checked_paths:
            QMessageBox.warning(self, "Nothing selected", "Check at least one tracked file.")
            return
        targets = {}
        for path in checked_paths:
            state = self.pm.load_file_state(self.folder_name, self.manifest, path)
            phones = sendable_phones(state)
            if phones:
                self.states[path] = state
                targets[path] = phones
        total = sum(len(v) for v in targets.values())
        answer = QMessageBox.question(
            self, "Confirm send",
            f"Send to {total:,} unsent recipient(s) across {len(targets):,} checked file(s)?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.send_btn.setEnabled(False)
        self.send_btn.setText("Sending...")
        self.progress_panel.reset()
        self.flush_timer.start()
        concurrency = int(os.environ.get("BATCH_CONCURRENCY", "30"))
        self.names = {}
        for path, phones in targets.items():
            name = os.path.basename(path)
            if name in self.names.values():          # same filename, different folder
                name = f"{name} ({os.path.basename(os.path.dirname(path))})"
            self.names[path] = name
            self.progress_panel.add_target(name, len(phones))
            worker = SendingWorker(name, phones, message, url, key, "project", concurrency, self)
            worker.progress.connect(self.progress_panel.update_target)
            worker.log.connect(self._log)
            worker.phone_result.connect(lambda _n, phone, ok, detail, p=path: self._record_result(p, phone, ok, detail))
            worker.finished.connect(lambda _name, report, _mode, p=path: self._handle_finished(p, report))
            self.active_workers.append(worker)
            self.workers[path] = worker
            worker.start()

    def _interrupt_one(self, name):
        for path, worker in self.workers.items():
            if self.names.get(path) == name:
                worker.running = False
                self._log("info", f"Interrupting {name}...")

    def _interrupt_all(self):
        for worker in self.workers.values():
            worker.running = False
        self._log("info", "Interrupting all files...")

    def _record_result(self, path, phone, success, detail):
        if not success and detail == "Cancelled":
            return                      # stopped before it was tried -> stays unsent
        state = self.states.get(path)
        if state is None:
            return
        record_result(state, phone, success, None if success else detail)
        self.dirty.add(path)

    def _flush(self, only=None):
        """Persist dirty per-file states + refresh their counters."""
        for path in list(self.dirty if only is None else ([only] if only in self.dirty else [])):
            state = self.states.get(path)
            if state is None or path not in self.manifest.get("files", {}):
                self.dirty.discard(path)
                continue
            try:
                self.pm.save_file_state(self.folder_name, self.manifest, path, state)
            except OSError as exc:
                self._log("error", f"Could not save progress for {os.path.basename(path)}: {exc}")
                continue
            self.dirty.discard(path)
            self._refresh_meta_only(path)

    def _handle_finished(self, path, report):
        name = self.names.get(path, os.path.basename(path))
        summary = report["summary"]
        interrupted = bool(summary.get("interrupted"))
        self._flush(only=path)
        try:
            report_path = self.pm.save_report(self.folder_name, name, report)
        except OSError as exc:
            report_path = None
            self._log("error", f"Could not save report for {name}: {exc}")
        if interrupted:
            self.progress_panel.mark_interrupted(name, summary["processed"], summary["failed"])
            self._log("info", f"{name}: interrupted - {summary['processed']:,} sent this run, "
                              f"{summary.get('cancelled', 0):,} not attempted (still unsent).")
        else:
            self.progress_panel.complete_target(name, summary["processed"], summary["failed"])
            self._log("success" if summary["failed"] == 0 else "error",
                      f"{name}: complete - {summary['processed']:,} sent, {summary['failed']:,} failed.")
        if report_path:
            self._log("info", f"Report saved: {report_path}")

        entry = self.manifest.get("files", {}).get(path)
        if entry is not None and self._is_done(entry):
            # Finished file: unchecked + row turns green (via _refresh_meta_only).
            self.checked[path] = False
            row = self.rows.get(path)
            if row is not None:
                box = row.findChild(QCheckBox)
                if box is not None:
                    box.setChecked(False)
        self._refresh_meta_only(path)

        self.workers.pop(path, None)
        self.active_workers = [w for w in self.active_workers if w.segment_name != name]
        if not self.active_workers:
            self.flush_timer.stop()
            self._flush()
            self.states.clear()
            self.send_btn.setEnabled(True)
            self.send_btn.setText("Send to checked files")

    def closeEvent(self, event):
        for worker in list(self.active_workers):
            worker.running = False
            worker.wait(2000)
        if self.loader and self.loader.isRunning():
            self.loader.cancel_requested = True
            self.loader.wait(2000)
        self.flush_timer.stop()
        self._flush()          # keep whatever progress was made
        event.accept()
