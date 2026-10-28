"""User settings + recent items, stored as JSON in the per-user app-data folder."""
import json
import os
import sys
import time
import uuid

from PySide6.QtCore import QStandardPaths

from . import APP_NAME

MAX_RECENT = 9


def app_data_dir():
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        d = os.path.join(os.environ["APPDATA"], APP_NAME)
    else:
        d = os.path.join(os.path.expanduser("~"), ".config", "sw-visualize-texture-maker")
    os.makedirs(d, exist_ok=True)
    return d


def default_output_dir():
    docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    if not docs:
        docs = os.path.join(os.path.expanduser("~"), "Documents")
    return os.path.join(docs, APP_NAME)


class Settings:
    def __init__(self, path=None):
        self.path = path or os.path.join(app_data_dir(), "settings.json")
        self.data = {"output_dir": default_output_dir(), "template": "", "recent": []}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                self.data.update(stored)
        except (OSError, ValueError):
            pass

    def save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass

    @property
    def output_dir(self):
        return self.data.get("output_dir") or default_output_dir()

    @output_dir.setter
    def output_dir(self, value):
        self.data["output_dir"] = value
        self.save()

    @property
    def template(self):
        """Path to a custom template .svap/.xml, or '' for the built-in one."""
        t = self.data.get("template") or ""
        return t if t and os.path.exists(t) else ""

    @template.setter
    def template(self, value):
        self.data["template"] = value or ""
        self.save()

    def recent(self):
        return [r for r in self.data.get("recent", []) if isinstance(r, dict)]

    def add_recent(self, entry, thumb_image=None):
        entry = dict(entry)
        entry.setdefault("id", uuid.uuid4().hex[:12])
        entry["time"] = time.time()
        if thumb_image is not None:
            tdir = os.path.join(app_data_dir(), "thumbs")
            os.makedirs(tdir, exist_ok=True)
            tpath = os.path.join(tdir, entry["id"] + ".png")
            try:
                thumb_image.save(tpath)
                entry["thumb"] = tpath
            except OSError:
                pass
        items = [r for r in self.recent() if r.get("svap") != entry.get("svap")]
        items.insert(0, entry)
        for old in items[MAX_RECENT:]:
            t = old.get("thumb")
            if t and os.path.exists(t):
                try:
                    os.remove(t)
                except OSError:
                    pass
        self.data["recent"] = items[:MAX_RECENT]
        self.save()
