"""
project_ui.py
===============
Everything for the "Projects" nav tab:
  - ProjectsPage: grid of project cards, "+ New Project"
  - NewProjectDialog: name entry
  - ProjectWorkspaceDialog: add files/folders (tracked + persisted to
    the project's manifest), see per-file sent/unsent/failed counts,
    and send only what hasn't been sent yet.

A project folder that exists on disk but wasn't created by this app
(no valid .sms_project.json marker) is still listed, but flagged in
red rather than opened normally.
"""
import os
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QMessageBox, QFileDialog,
    QListWidget, QListWidgetItem, QSizePolicy, QPlainTextEdit,
)

from theme import COLORS
from ui_common import Card, apply_glow, attach_focus_glow, enable_dark_titlebar, UnicodeTextEdit
from phone_utils import SUPPORTED_EXTENSIONS, parse_phone_file
from excel_dialog import resolve_excel_columns
from sender import SendingWorker
from progress_panel import LiveProgressPanel
from projects import ProjectManager


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
    def __init__(self, folder_name, valid, manifest_or_none, on_open, parent=None):
        super().__init__(parent)
        card = Card()
        card.setObjectName("ProjectCard" if valid else "ProjectCardInvalid")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)

        if valid:
            name_label = QLabel(manifest_or_none.get("name", folder_name))
            name_label.setObjectName("ProjectName")
            lay.addWidget(name_label)
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
            name_label = QLabel(folder_name)
            name_label.setObjectName("ProjectName")
            lay.addWidget(name_label)
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
        new_btn.setObjectName("PrimaryButton")
        new_btn.setMinimumHeight(40)
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

    def refresh(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        folders = self.pm.list_project_dirs()
        cols = 3
        for i, folder_name in enumerate(folders):
            valid = self.pm.is_valid_project(folder_name)
            manifest = self.pm.load_manifest(folder_name) if valid else None
            card = ProjectCardWidget(folder_name, valid, manifest, self.open_project, self.grid_container)
            self.grid.addWidget(card, i // cols, i % cols)
        if not folders:
            empty = QLabel("No projects yet. Click \"+ New Project\" to create one.")
            empty.setObjectName("Muted")
            self.grid.addWidget(empty, 0, 0)


class ProjectWorkspaceDialog(QDialog):
    def __init__(self, project_manager: ProjectManager, folder_name, parent=None):
        super().__init__(parent)
        self.pm = project_manager
        self.folder_name = folder_name
        self.manifest = self.pm.load_manifest(folder_name)
        self.active_workers = []
        self.excel_for_all_column = getattr(parent, "excel_for_all_column", None)

        self.setWindowTitle(f"Project - {self.manifest.get('name', folder_name)}")
        self.setModal(True)
        self.resize(1020, 780)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        enable_dark_titlebar(int(self.winId()))
        self._build()
        self._refresh_file_list()

    # -- UI ------------------------------------------------------------ #
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        title = QLabel(self.manifest.get("name", self.folder_name))
        title.setObjectName("DialogTitle")
        root.addWidget(title)
        created = QLabel(f"Created {self.manifest.get('created_at', '?')}  -  stored in Projects/{self.folder_name}")
        created.setObjectName("TinyMuted")
        root.addWidget(created)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        message_card = Card()
        ml = QVBoxLayout(message_card)
        ml.setContentsMargins(18, 18, 18, 18)
        ml.setSpacing(8)
        mlabel = QLabel("Message")
        mlabel.setObjectName("SectionTitle")
        ml.addWidget(mlabel)
        self.message_box = UnicodeTextEdit()
        self.message_box.setPlaceholderText("Message to send for unsent recipients in this project...")
        self.message_box.setMinimumHeight(100)
        self.message_box.setMaximumHeight(150)
        ml.addWidget(self.message_box)
        lay.addWidget(message_card)

        files_card = Card()
        fl = QVBoxLayout(files_card)
        fl.setContentsMargins(18, 16, 18, 16)
        fl.setSpacing(8)
        header = QHBoxLayout()
        ftitle = QLabel("Tracked files")
        ftitle.setObjectName("SectionTitle")
        header.addWidget(ftitle)
        header.addStretch()
        add_files_btn = QPushButton("+ Add files")
        add_files_btn.clicked.connect(self.add_files)
        add_folder_btn = QPushButton("Add folder")
        add_folder_btn.clicked.connect(self.add_folder)
        header.addWidget(add_files_btn)
        header.addWidget(add_folder_btn)
        fl.addLayout(header)

        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(180)
        self.file_list.setMaximumHeight(280)
        fl.addWidget(self.file_list)
        lay.addWidget(files_card)

        self.progress_panel = LiveProgressPanel()
        lay.addWidget(self.progress_panel)

        send_btn = QPushButton("Send to all unsent recipients ->")
        send_btn.setObjectName("PrimaryButton")
        send_btn.setMinimumHeight(46)
        apply_glow(send_btn, COLORS["accent"], blur_radius=14, offset=(0, 2))
        send_btn.clicked.connect(self.send_unsent)
        self.send_btn = send_btn
        lay.addWidget(send_btn)

        activity_card = Card()
        al = QVBoxLayout(activity_card)
        al.setContentsMargins(18, 15, 18, 15)
        al.addWidget(QLabel("Activity"))
        self.log_box = QPlainTextEdit()
        self.log_box.setObjectName("Log")
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(140)
        al.addWidget(self.log_box)
        lay.addWidget(activity_card)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close_btn)
        root.addLayout(row)

    def _log(self, level, text):
        prefix = {"success": "[OK]", "error": "[ERR]", "info": "[*]"}.get(level, "[*]")
        self.log_box.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {prefix} {text}")

    # -- file tracking --------------------------------------------------#
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select phone files", "", "Supported (*.csv *.xlsx *.xls *.json *.txt)"
        )
        if files:
            self._track_files(files)

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
        self._track_files(paths)

    def _track_files(self, paths):
        resolved, overrides, self.excel_for_all_column = resolve_excel_columns(
            paths, self, self._log, self.excel_for_all_column
        )
        added = 0
        for path in resolved:
            try:
                phones = parse_phone_file(path, column_override=overrides.get(path))
            except Exception as exc:
                self._log("error", f"{os.path.basename(path)}: {exc}")
                continue
            if not phones:
                self._log("error", f"{os.path.basename(path)}: no valid phone numbers found")
                continue
            self.manifest = self.pm.add_file_to_manifest(self.folder_name, path, phones)
            added += 1
        if added:
            self._log("success", f"Tracked {added} file(s).")
        self._refresh_file_list()

    def _refresh_file_list(self):
        self.file_list.clear()
        for path, entry in self.manifest.get("files", {}).items():
            stats = ProjectManager.file_stats(entry)
            item = QListWidgetItem(
                f"{os.path.basename(path)}  -  {stats['total']:,} total, "
                f"{stats['sent']:,} sent, {stats['failed']:,} failed, {stats['unsent']:,} unsent"
            )
            item.setToolTip(path)
            self.file_list.addItem(item)

    # -- sending ---------------------------------------------------------#
    def send_unsent(self):
        message = self.message_box.toPlainText().strip()
        url = os.environ.get("SMS_API_URL", "").strip()
        key = os.environ.get("SMS_API_KEY", "").strip()
        if not message:
            QMessageBox.warning(self, "Message required", "Enter a message.")
            return
        if not url or not key:
            QMessageBox.warning(self, "API not configured", "Open API Settings on the main window first.")
            return
        targets = {}
        for path in self.manifest.get("files", {}):
            unsent = self.pm.unsent_phones(self.manifest, path)
            if unsent:
                targets[path] = unsent
        if not targets:
            QMessageBox.information(self, "Nothing to send", "Every tracked recipient in this project has already been sent.")
            return
        total = sum(len(v) for v in targets.values())
        answer = QMessageBox.question(
            self, "Confirm send",
            f"Send to {total:,} unsent recipient(s) across {len(targets):,} file(s)?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.send_btn.setEnabled(False)
        self.progress_panel.reset()
        concurrency = int(os.environ.get("BATCH_CONCURRENCY", "30"))
        for path, phones in targets.items():
            name = os.path.basename(path)
            self.progress_panel.add_target(name, len(phones))
            worker = SendingWorker(name, phones, message, url, key, "project", concurrency, self)
            worker.progress.connect(self.progress_panel.update_target)
            worker.log.connect(self._log)
            worker.phone_result.connect(lambda _n, phone, ok, detail, p=path: self._record_result(p, phone, ok, detail))
            worker.finished.connect(lambda _name, report, _mode, p=path: self._handle_finished(p, report))
            self.active_workers.append(worker)
            worker.start()

    def _record_result(self, path, phone, success, detail):
        self.manifest = self.pm.mark_sent(self.folder_name, path, phone, success, detail)

    def _handle_finished(self, path, report):
        name = os.path.basename(path)
        s = report["summary"]
        self.progress_panel.complete_target(name, s["processed"], s["failed"])
        self._log("success" if s["failed"] == 0 else "error", f"{name}: complete - {s['processed']:,} sent, {s['failed']:,} failed.")
        self._refresh_file_list()
        self.active_workers = [w for w in self.active_workers if w.segment_name != name or w.isRunning()]
        if not any(w.isRunning() for w in self.active_workers):
            self.send_btn.setEnabled(True)

    def closeEvent(self, event):
        for worker in list(self.active_workers):
            worker.running = False
            worker.wait(2000)
        event.accept()
