from pathlib import Path

from core import excalidraw
from core.settings import archive_path

_cases = []
_path = None


def load():
    global _cases, _path
    p = archive_path()
    if not p or not Path(p).exists():
        _cases, _path = [], None
        return
    try:
        _cases = excalidraw.load_path(p)
        _path = p
    except (OSError, excalidraw.SceneError):
        _cases, _path = [], None


def cases():
    return _cases


def count():
    return len(_cases)


def path():
    return _path


def is_loaded():
    return _path is not None
