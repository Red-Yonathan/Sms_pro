"""
wallpaper.py
=============
Lets the user pick a background image; it is copied into a Wallpaper/
folder next to main.py, and the chosen filename is remembered in a
small .txt pointer file so it's restored automatically next launch.
"""
import os
import shutil


class WallpaperManager:
    POINTER_NAME = "current_wallpaper.txt"

    def __init__(self, script_dir):
        self.folder = os.path.join(script_dir, "Wallpaper")
        os.makedirs(self.folder, exist_ok=True)
        self.pointer_file = os.path.join(self.folder, self.POINTER_NAME)
        self._listeners = []

    def add_listener(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def notify(self):
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:
                pass

    def get_current(self):
        """Returns an absolute path to the saved wallpaper, or None."""
        if not os.path.exists(self.pointer_file):
            return None
        try:
            with open(self.pointer_file, "r", encoding="utf-8") as f:
                name = f.read().strip()
        except OSError:
            return None
        if not name:
            return None
        path = os.path.join(self.folder, name)
        return path if os.path.exists(path) else None

    def set_wallpaper(self, source_path):
        """Copies source_path into the Wallpaper folder and remembers it.
        Returns the new absolute path."""
        ext = os.path.splitext(source_path)[1].lower() or ".png"
        dest_name = f"wallpaper{ext}"
        dest_path = os.path.join(self.folder, dest_name)
        shutil.copyfile(source_path, dest_path)
        with open(self.pointer_file, "w", encoding="utf-8") as f:
            f.write(dest_name)
        try:
            from PySide6.QtGui import QPixmapCache
            QPixmapCache.clear()
        except Exception:
            pass
        self.notify()
        return dest_path

    def reset(self):
        """Back to the default (no wallpaper, animated blob background)."""
        try:
            if os.path.exists(self.pointer_file):
                os.remove(self.pointer_file)
        except OSError:
            pass
        try:
            from PySide6.QtGui import QPixmapCache
            QPixmapCache.clear()
        except Exception:
            pass
        self.notify()

