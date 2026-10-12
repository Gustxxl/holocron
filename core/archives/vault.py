import re
from pathlib import Path
from core.settings import vault_path, new_cases_path
from .base import Archive

NAME_MAX = 80
_UNSAFE = re.compile(r'[\\/:*?"<>|#^\[\]]')
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}


def save_note(filepath, text):
    Path(filepath).write_text(text.rstrip('\n') + '\n', encoding='utf-8')


def note_name(text):
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), '')
    name = ' '.join(_UNSAFE.sub(' ', first.lstrip('#')).split())[:NAME_MAX].strip(' .')
    if name.upper() in _RESERVED:
        name += '_'
    return name or 'Untitled'


def create_note(folder, text):
    text = text.strip()
    if not text:
        return None
    base = note_name(text)
    for n in range(1, 1000):
        path = Path(folder) / (f'{base}.md' if n == 1 else f'{base} {n}.md')
        try:
            with open(path, 'x', encoding='utf-8') as f:
                f.write(text + '\n')
            return str(path)
        except FileExistsError:
            continue
        except OSError:
            return None
    return None


def _roots():
    return [p for p in (vault_path(), new_cases_path()) if p and Path(p).is_dir()]


class Vault(Archive):
    name = 'Vault'
    key = 'vault'

    def __init__(self):
        self._cases = []
        self._path = None

    def is_configured(self):
        return bool(_roots())

    def load(self):
        roots = _roots()
        self._cases, seen = [], set()
        for root in roots:
            try:
                files = sorted(Path(root).rglob('*.md'))
            except OSError:
                continue
            for f in files:
                try:
                    key = f.resolve()
                    if key in seen:
                        continue
                    seen.add(key)
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
                        'filename': f.stem,
                        'x': 0,
                        'y': 0,
                    })
                except (OSError, UnicodeDecodeError):
                    continue
        self._path = roots[0] if roots else None

    def load_cases(self):
        if not self._cases:
            self.load()
        return self._cases

    def path(self):
        return self._path
