from pathlib import Path
from core import excalidraw
from core.settings import archive_path
from .base import Archive, BROKEN


def _board(path):
    try:
        return excalidraw.load_cases(path)
    except BROKEN:
        return []


class ExcalidrawObsidian(Archive):
    name = "Excalidraw for Obsidian"
    key = "excalidraw_obsidian"

    def is_configured(self):
        p = archive_path()
        return bool(p and Path(p).exists())

    def _load(self):
        p = archive_path()
        if not p or not Path(p).exists():
            self._reset()
            return
        path = Path(p)
        try:
            files = sorted(path.rglob('*.md')) if path.is_dir() else [path]
        except OSError:
            self._reset()
            return
        self._cases = self._read(files, _board)
        for i, c in enumerate(self._cases, 1):
            c['id'] = i
        self._path = p
