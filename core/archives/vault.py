from pathlib import Path
from core.settings import vault_path
from .base import Archive


class Vault(Archive):
    name = 'Vault'
    key = 'vault'

    def __init__(self):
        self._cases = []
        self._path = None

    def is_configured(self):
        p = vault_path()
        return bool(p and Path(p).exists())

    def load(self):
        p = vault_path()
        if not p or not Path(p).exists():
            self._cases, self._path = [], None
            return
        try:
            path = Path(p)
            self._cases = []
            for f in sorted(path.rglob('*.md')):
                try:
                    text = f.read_text(encoding='utf-8').strip()
                    if not text:
                        continue
                    if '## Drawing' in text or 'excalidraw-plugin' in text:
                        continue
                    self._cases.append({
                        'text': text,
                        'source': f.name,
                        'filepath': str(f),
                        'element_id': f.stem,
                        'x': 0,
                        'y': 0,
                    })
                except (OSError, UnicodeDecodeError):
                    continue
            self._path = p
        except OSError:
            self._cases, self._path = [], None

    def load_cases(self):
        if not self._cases:
            self.load()
        return self._cases

    def path(self):
        return self._path
