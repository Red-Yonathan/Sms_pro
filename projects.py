"""
projects.py
============
Project folders + persistent per-file / per-phone sent tracking.

Layout of Projects/<name>/ :
  .sms_project.json   small "header": signature (proves the app made this
                      folder), name, created_at, and per tracked file just
                      SUMMARY counts (total/sent/failed/unsent) + where its
                      data file is. Cheap to load, so the Projects list and
                      opening a project are instant even with 700k numbers.
  data/<key>.json     one file per tracked file holding the actual numbers:
                      {"pending":[...], "sent":{phone: ts},
                       "failed":{phone: {"at": ts, "error": msg}}}

Older projects (one big manifest with a per-phone dict) are migrated to
this layout automatically the first time they're loaded.
"""
import os
import re
import json
import shutil
import hashlib
from datetime import datetime

APP_SIGNATURE = "PhoneSenderPro.ProjectMarker.v1"
MARKER_FILENAME = ".sms_project.json"
DATA_DIRNAME = "data"


def safe_project_name(name):
    name = re.sub(r'[<>:"/\\|?*]', "_", str(name)).strip()
    return name or "Untitled"


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _write_json(path, obj, compact=False):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def new_state():
    return {"pending": {}, "sent": {}, "failed": {}}


def state_counts(state):
    sent, failed, unsent = len(state["sent"]), len(state["failed"]), len(state["pending"])
    return {"total": sent + failed + unsent, "sent": sent, "failed": failed, "unsent": unsent}


def sendable_phones(state):
    """Everything not yet successfully sent: never-tried + previously failed."""
    return list(state["pending"]) + list(state["failed"])


def record_result(state, phone, success, error=None):
    state["pending"].pop(phone, None)
    state["failed"].pop(phone, None)
    state["sent"].pop(phone, None)
    if success:
        state["sent"][phone] = _now()
    else:
        state["failed"][phone] = {"at": _now(), "error": error or "Unknown error"}


class ProjectManager:
    def __init__(self, script_dir):
        self.root = os.path.join(script_dir, "Projects")
        os.makedirs(self.root, exist_ok=True)

    # -- discovery ----------------------------------------------------- #
    def list_project_dirs(self):
        try:
            return sorted(d for d in os.listdir(self.root)
                          if os.path.isdir(os.path.join(self.root, d)))
        except OSError:
            return []

    def project_path(self, folder_name):
        return os.path.join(self.root, folder_name)

    def marker_path(self, folder_name):
        return os.path.join(self.root, folder_name, MARKER_FILENAME)

    def is_valid_project(self, folder_name):
        path = self.marker_path(folder_name)
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("app_signature") == APP_SIGNATURE
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return False

    # -- header I/O ---------------------------------------------------- #
    def _data_rel(self, file_path):
        key = hashlib.sha1(os.path.normcase(os.path.abspath(file_path)).encode("utf-8")).hexdigest()[:20]
        return f"{DATA_DIRNAME}/{key}.json"

    def _data_abs(self, folder_name, rel):
        return os.path.join(self.project_path(folder_name), *rel.split("/"))

    def load_manifest(self, folder_name):
        with open(self.marker_path(folder_name), "r", encoding="utf-8") as f:
            manifest = json.load(f)
        migrated = False
        for path, entry in list(manifest.get("files", {}).items()):
            if "phones" in entry:                      # legacy layout
                migrated = True
                state = new_state()
                for phone, rec in entry["phones"].items():
                    if rec.get("sent") is True:
                        state["sent"][phone] = rec.get("sent_at") or _now()
                    elif rec.get("sent") is False:
                        state["failed"][phone] = {"at": rec.get("sent_at"), "error": rec.get("error")}
                    else:
                        state["pending"][phone] = None
                rel = self._data_rel(path)
                self._write_state(folder_name, rel, state)
                manifest["files"][path] = {"added_at": entry.get("added_at", _now()),
                                           "data_file": rel, **state_counts(state)}
        if migrated:
            self.save_manifest(folder_name, manifest)
        return manifest

    def save_manifest(self, folder_name, data):
        _write_json(self.marker_path(folder_name), data)

    # -- lifecycle ----------------------------------------------------- #
    def create_project(self, name):
        clean = safe_project_name(name)
        folder_name, counter = clean, 2
        while os.path.exists(self.project_path(folder_name)):
            folder_name = f"{clean}_{counter}"
            counter += 1
        os.makedirs(os.path.join(self.project_path(folder_name), DATA_DIRNAME), exist_ok=True)
        self.save_manifest(folder_name, {
            "app_signature": APP_SIGNATURE, "name": clean,
            "created_at": _now(), "files": {},
        })
        return folder_name

    def delete_project(self, folder_name):
        """Removes only the project's tracking folder; the source files that
        were added to it are never touched (they're only referenced)."""
        shutil.rmtree(self.project_path(folder_name), ignore_errors=True)

    # -- reports (always inside the project's own folder) --------------- #
    def reports_dir(self, folder_name):
        path = os.path.join(self.project_path(folder_name), "Reports")
        os.makedirs(path, exist_ok=True)
        return path

    def save_report(self, folder_name, target_name, report):
        """Projects/<name>/Reports/<dd-mm-yyyy>/<target>_<HHMMSS>_report.json"""
        day = os.path.join(self.reports_dir(folder_name), datetime.now().strftime("%d-%m-%Y"))
        os.makedirs(day, exist_ok=True)
        safe = re.sub(r'[<>:"/\\|?*]', "_", str(target_name))
        path = os.path.join(day, f"{safe}_{datetime.now().strftime('%H%M%S')}_report.json")
        _write_json(path, report)
        return path

    # -- per-file state ------------------------------------------------ #
    def _write_state(self, folder_name, rel, state):
        os.makedirs(os.path.join(self.project_path(folder_name), DATA_DIRNAME), exist_ok=True)
        _write_json(self._data_abs(folder_name, rel), {
            "pending": list(state["pending"]),
            "sent": state["sent"],
            "failed": state["failed"],
        }, compact=True)

    def load_file_state(self, folder_name, manifest, file_path):
        entry = manifest["files"].get(file_path)
        state = new_state()
        if not entry:
            return state
        try:
            with open(self._data_abs(folder_name, entry["data_file"]), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, KeyError):
            return state
        state["pending"] = dict.fromkeys(data.get("pending", []))
        state["sent"] = data.get("sent", {})
        state["failed"] = data.get("failed", {})
        return state

    def save_file_state(self, folder_name, manifest, file_path, state):
        """Writes the file's numbers + updates the header's summary counts
        (mutates `manifest` in place too). Returns the manifest."""
        entry = manifest["files"].setdefault(file_path, {
            "added_at": _now(), "data_file": self._data_rel(file_path)})
        self._write_state(folder_name, entry["data_file"], state)
        entry.update(state_counts(state))
        self.save_manifest(folder_name, manifest)
        return manifest

    def add_file_to_manifest(self, folder_name, manifest, file_path, phones):
        """Track a file. Re-adding an already-tracked file only adds numbers
        that are new -- existing sent/failed history is kept."""
        state = self.load_file_state(folder_name, manifest, file_path)
        for phone in phones:
            if phone not in state["pending"] and phone not in state["sent"] and phone not in state["failed"]:
                state["pending"][phone] = None
        return self.save_file_state(folder_name, manifest, file_path, state)

    def remove_file_from_manifest(self, folder_name, manifest, file_path):
        entry = manifest["files"].pop(file_path, None)
        if entry:
            try:
                os.remove(self._data_abs(folder_name, entry["data_file"]))
            except OSError:
                pass
        self.save_manifest(folder_name, manifest)
        return manifest

    # -- summaries ----------------------------------------------------- #
    @staticmethod
    def file_stats(entry):
        return {k: int(entry.get(k, 0)) for k in ("total", "sent", "failed", "unsent")}

    @classmethod
    def stats(cls, manifest):
        out = {"total": 0, "sent": 0, "failed": 0, "unsent": 0}
        for entry in manifest.get("files", {}).values():
            for k, v in cls.file_stats(entry).items():
                out[k] += v
        return out
