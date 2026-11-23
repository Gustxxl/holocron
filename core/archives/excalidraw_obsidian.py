from pathlib import Path
from core import excalidraw
from core.settings import archive_path
from .base import Archive, BROKEN
from .vault import _roots, is_drawing, note_files


def _board(path):
    try:
        return excalidraw.load_cases(path)
    except BROKEN:
        return []


def _drawing(path):
    try:
        return excalidraw.load_cases(path) if is_drawing(path.read_text(encoding='utf-8')) else []
    except BROKEN:
        return []


class ExcalidrawObsidian(Archive):
    name = "Excalidraw for Obsidian"
    key = "excalidraw_obsidian"

    def is_configured(self):
        p = archive_path()
        return bool(p and Path(p).exists()) or bool(_roots())

    def _load(self):
        p = archive_path()
        path = Path(p) if p and Path(p).exists() else None
        try:
            own = (sorted(path.rglob('*.md')) if path.is_dir() else [path]) if path else []
        except OSError:
            own = []
        mine = set(own)
        seen = {f.resolve() for f in own}
        files = [*own, *(f for f in note_files() if not seen or f.resolve() not in seen)]
        self._cases = self._read(files, lambda f: _board(f) if f in mine else _drawing(f))
        for i, c in enumerate(self._cases, 1):
            c['id'] = i
        self._path = p if path else None
