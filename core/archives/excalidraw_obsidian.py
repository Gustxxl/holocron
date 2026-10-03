from pathlib import Path
from core import excalidraw
from core.settings import archive_path
from .base import Archive


class ExcalidrawObsidian(Archive):
    name = "Excalidraw for Obsidian"
    key = "excalidraw_obsidian"

    def __init__(self):
        self._cases = []
        self._path = None

    def is_configured(self):
        p = archive_path()
        return bool(p and Path(p).exists())

    def load(self):
        p = archive_path()
        if not p or not Path(p).exists():
            self._cases, self._path = [], None
            return
        try:
            self._cases = excalidraw.load_path(p)
            self._path = p
        except (OSError, excalidraw.SceneError):
            self._cases, self._path = [], None

    def load_cases(self):
        if not self._cases:
            self.load()
        return self._cases

    def path(self):
        return self._path
