from .excalidraw_obsidian import ExcalidrawObsidian
from .excalidraw_plain import ExcalidrawPlain

_ARCHIVES = [ExcalidrawObsidian(), ExcalidrawPlain()]


def load():
    for arch in _ARCHIVES:
        arch.load()


def cases():
    result = []
    for arch in _ARCHIVES:
        if arch.is_configured():
            result.extend(arch.load_cases())
    return result


def count():
    return len(cases())

def is_loaded():
    return any(arch._path is not None for arch in _ARCHIVES)


def path():
    for arch in _ARCHIVES:
        if arch._path:
            return arch._path
    return None


def status():
    info = []
    for arch in _ARCHIVES:
        if arch.is_configured():
            cases = arch.load_cases()
            info.append((arch.name, len(cases)))
    return info
