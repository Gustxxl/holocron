import re
from pathlib import Path
from core.settings import vault_path, new_cases_path, vault_exclude
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


def relative(folder):
    vault = vault_path()
    if not vault or not folder:
        return None
    root = Path(vault).resolve()
    path = Path(folder).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    if path == root or not path.is_dir() or not path.is_relative_to(root):
        return None
    return path.relative_to(root).as_posix()


def folders(root, skip, cases):
    base = Path(root)
    try:
        top = [p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith('.')]
    except OSError:
        top = []
    counts = {}
    for case in cases:
        path = Path(case.get('filepath') or '')
        if case.get('archive') == Vault.name and path.is_relative_to(base):
            parts = path.relative_to(base).parts
            if len(parts) > 1:
                counts[parts[0]] = counts.get(parts[0], 0) + 1
    names = sorted({*top, *skip}, key=str.casefold)
    return [(n, None if n in skip else counts.get(n, 0)) for n in names]


def _skipped(rel, rules):
    return any(p.startswith('.') for p in rel.parts) or any(rel.parts[:len(r)] == r for r in rules)


def _roots():
    return [p for p in (vault_path(), new_cases_path()) if p and Path(p).is_dir()]


def _note(f):
    try:
        text = f.read_text(encoding='utf-8').strip()
    except (OSError, UnicodeDecodeError):
        return []
    if not text or '## Drawing' in text or 'excalidraw-plugin' in text:
        return []
    return [{
        'text': text,
        'source': f.name,
        'filepath': str(f),
        'element_id': f.stem,
        'filename': f.stem,
        'x': 0,
        'y': 0,
    }]


class Vault(Archive):
    name = 'Vault'
    key = 'vault'

    def is_configured(self):
        return bool(_roots())

    def _load(self):
        roots = _roots()
        vault = Path(vault_path()).resolve() if vault_path() else None
        rules = [Path(p).parts for p in vault_exclude()]
        files, seen = [], set()
        for root in roots:
            base = Path(root)
            real = base.resolve()
            own = rules if real == vault else []
            try:
                found = sorted(base.rglob('*.md'))
            except OSError:
                continue
            for f in found:
                rel = f.relative_to(base)
                if _skipped(rel, own) or real / rel in seen:
                    continue
                seen.add(real / rel)
                files.append(f)
        self._cases = self._read(files, _note)
        self._path = roots[0] if roots else None
