"""
file_loader.py
================
Background QThread that parses a batch of phone-source files (txt/json/
csv/xlsx) off the UI thread. Lives in its own module (rather than
main.py) so project_ui.py can reuse it for Projects without a circular
import between main.py and project_ui.py.
"""
import os
from PySide6.QtCore import QThread, Signal

from phone_utils import parse_phone_file


class FileLoadWorker(QThread):
    progress = Signal(int, int, str)
    file_loaded = Signal(str, int)
    file_failed = Signal(str, str)
    finished = Signal(dict)

    def __init__(self, paths, column_overrides=None, parent=None):
        super().__init__(parent)
        self.paths = list(dict.fromkeys(paths))
        self.column_overrides = column_overrides or {}
        self.cancel_requested = False

    def run(self):
        results = {}
        total = len(self.paths)
        for index, path in enumerate(self.paths, 1):
            if self.cancel_requested:
                break
            try:
                phones = parse_phone_file(path, column_override=self.column_overrides.get(path))
                if phones:
                    results[path] = phones
                    self.file_loaded.emit(path, len(phones))
                else:
                    self.file_failed.emit(path, "No valid phone numbers found")
            except Exception as exc:
                self.file_failed.emit(path, f"{type(exc).__name__}: {exc}")
            self.progress.emit(index, total, os.path.basename(path))
        self.finished.emit(results)
