import json
from pathlib import Path
from core.excalidraw import strip_emoji, clean
from core.settings import excalidraw_path
from .base import Archive


def _load_scene(path):
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    scene = json.loads(clean(raw))
    elements = scene.get("elements", [])
    rects = {e["id"]: e for e in elements
             if e.get("type") == "rectangle" and not e.get("isDeleted")}
    cases = []
    for t in elements:
        if t.get("type") != "text" or t.get("isDeleted"):
            continue
        txt = strip_emoji(t.get("originalText") or t.get("text") or "").strip()
        if not txt:
            continue
        r = rects.get(t.get("containerId"))
        x = round((r or t).get("x", 0))
        y = round((r or t).get("y", 0))
        cases.append({"text": txt, "x": x, "y": y, "source": path.name, "filepath": str(path), "element_id": t["id"]})
    cases.sort(key=lambda c: (round(c["y"] / 40), c["x"]))
    return cases


class ExcalidrawPlain(Archive):
    name = "Excalidraw"
    key = "excalidraw"

    def __init__(self):
        self._cases = []
        self._path = None

    def is_configured(self):
        p = excalidraw_path()
        return bool(p and Path(p).exists())

    def load(self):
        p = excalidraw_path()
        if not p or not Path(p).exists():
            self._cases, self._path = [], None
            return
        try:
            path = Path(p)
            if path.is_dir():
                self._cases = []
                for f in sorted(path.rglob("*.excalidraw")):
                    try:
                        self._cases.extend(_load_scene(f))
                    except (json.JSONDecodeError, KeyError):
                        continue
            else:
                self._cases = _load_scene(path)
            self._path = p
        except OSError:
            self._cases, self._path = [], None

    def load_cases(self):
        if not self._cases:
            self.load()
        return self._cases

    def path(self):
        return self._path
