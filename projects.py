"""
projects.py
============
"Projects" let you group target files under a named folder inside
./Projects/<name>/, and persistently track, per file and per phone
number, whether it has been sent yet.

Each project folder gets a small marker/manifest file
(.sms_project.json). Its "app_signature" field is how we tell a folder
that was really created by this app apart from one a user renamed,
copied in manually, or that got corrupted -- those get flagged in the
UI instead of trusted silently.
"""
import os
import re
import json
from datetime import datetime

APP_SIGNATURE = "PhoneSenderPro.ProjectMarker.v1"
MARKER_FILENAME = ".sms_project.json"


def safe_project_name(name):
    name = re.sub(r'[<>:"/\\|?*]', "_", str(name)).strip()
    return name or "Untitled"


class ProjectManager:
    def __init__(self, script_dir):
        self.root = os.path.join(script_dir, "Projects")
        os.makedirs(self.root, exist_ok=True)

    # -- discovery -------------------------------------------------- #
    def list_project_dirs(self):
        try:
            return sorted(
                d for d in os.listdir(self.root)
                if os.path.isdir(os.path.join(self.root, d))
            )
        except OSError:
            return []

    def marker_path(self, folder_name):
        return os.path.join(self.root, folder_name, MARKER_FILENAME)

    def project_path(self, folder_name):
        return os.path.join(self.root, folder_name)

    def is_valid_project(self, folder_name):
        path = self.marker_path(folder_name)
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("app_signature") == APP_SIGNATURE
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return False

    # -- manifest I/O ------------------------------------------------ #
    def load_manifest(self, folder_name):
        with open(self.marker_path(folder_name), "r", encoding="utf-8") as f:
            return json.load(f)

    def save_manifest(self, folder_name, data):
        path = self.marker_path(folder_name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)

    # -- lifecycle ----------------------------------------------------#
    def create_project(self, name):
        clean = safe_project_name(name)
        folder_name = clean
        counter = 2
        while os.path.exists(os.path.join(self.root, folder_name)):
            folder_name = f"{clean}_{counter}"
            counter += 1
        os.makedirs(os.path.join(self.root, folder_name), exist_ok=True)
        manifest = {
            "app_signature": APP_SIGNATURE,
            "name": clean,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "files": {},
        }
        self.save_manifest(folder_name, manifest)
        return folder_name

    # -- file / phone tracking ---------------------------------------#
    def add_file_to_manifest(self, folder_name, file_path, phones):
        manifest = self.load_manifest(folder_name)
        entry = manifest["files"].setdefault(file_path, {
            "added_at": datetime.now().isoformat(timespec="seconds"),
            "phones": {},
        })
        for phone in phones:
            entry["phones"].setdefault(phone, {"sent": None, "sent_at": None, "error": None})
        self.save_manifest(folder_name, manifest)
        return manifest

    def remove_file_from_manifest(self, folder_name, file_path):
        manifest = self.load_manifest(folder_name)
        manifest["files"].pop(file_path, None)
        self.save_manifest(folder_name, manifest)
        return manifest

    def mark_sent(self, folder_name, file_path, phone, success, error=None):
        manifest = self.load_manifest(folder_name)
        entry = manifest["files"].get(file_path)
        if entry is None:
            return manifest
        rec = entry["phones"].setdefault(phone, {})
        rec["sent"] = bool(success)
        rec["sent_at"] = datetime.now().isoformat(timespec="seconds")
        rec["error"] = None if success else (error or "Unknown error")
        self.save_manifest(folder_name, manifest)
        return manifest

    def unsent_phones(self, manifest, file_path):
        entry = manifest["files"].get(file_path, {})
        return sorted(
            phone for phone, rec in entry.get("phones", {}).items()
            if rec.get("sent") is not True
        )

    @staticmethod
    def file_stats(entry):
        total = sent = failed = unsent = 0
        for rec in entry.get("phones", {}).values():
            total += 1
            if rec.get("sent") is True:
                sent += 1
            elif rec.get("sent") is False:
                failed += 1
            else:
                unsent += 1
        return {"total": total, "sent": sent, "failed": failed, "unsent": unsent}

    @classmethod
    def stats(cls, manifest):
        total = sent = failed = unsent = 0
        for entry in manifest.get("files", {}).values():
            s = cls.file_stats(entry)
            total += s["total"]; sent += s["sent"]; failed += s["failed"]; unsent += s["unsent"]
        return {"total": total, "sent": sent, "failed": failed, "unsent": unsent}
