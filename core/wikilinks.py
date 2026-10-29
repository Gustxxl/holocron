import re
from pathlib import PurePath

_LINK = r'\[\[([^\]|\\]+)(?:\\?\|([^\]]+))?\]\]'
_RE = re.compile(r'(?<!!)' + _LINK)
_ANY_RE = re.compile(_LINK)
_SUFFIXES = ('.excalidraw.md', '.excalidraw', '.md')


def _bare(name):
    name = name.strip().replace('\\', '/')
    for suffix in _SUFFIXES:
        if name.lower().endswith(suffix):
            return name[:-len(suffix)]
    return name


def label(target, alias=None):
    if alias:
        return alias.strip()
    return re.sub(r'#\^?', ' › ', target).strip(' ›')


def index(cases):
    files = {}
    for case in cases:
        fp = case.get('filepath')
        if fp:
            files.setdefault(fp, []).append(case)
    paths = {fp: _bare(PurePath(fp).as_posix()).casefold() for fp in files}
    names = {}
    for fp in sorted(files, key=lambda p: (len(PurePath(p).parts), p)):
        names.setdefault(paths[fp].rsplit('/', 1)[-1], files[fp])
    return files, paths, names


def resolve(target, files, paths, names):
    key = _bare(target.split('#', 1)[0]).strip('/').casefold()
    if not key:
        return None
    if '/' not in key:
        return names.get(key)
    return next((files[fp] for fp, p in paths.items() if ('/' + p).endswith('/' + key)), None)


def _fold(text):
    text = _RE.sub(lambda m: label(m.group(1), m.group(2)), text)
    return ' '.join(text.casefold().replace('ё', 'е').split())


def titles(files):
    out = {}
    for cases in files.values():
        for case in cases:
            first = next((ln for ln in case.get('text', '').splitlines() if ln.strip()), '')
            if first and not case.get('filename'):
                out.setdefault(_fold(first), []).append(case)
    return out


def _block(blocks, title, path=None):
    found = [c for c in blocks.get(_fold(title), []) if path is None or c['filepath'] == path]
    return found if len(found) == 1 else None


def numbered(text, cases, mark, here=None):
    files, paths, names = index(cases)
    blocks = titles(files)
    found, order = [], {}

    def pick(target):
        if target.startswith('#'):
            board = here in files and not all(c.get('filename') for c in files[here])
            return board and (_block(blocks, target[1:], here) or target[1:])
        own = here and _block(blocks, target, here)
        if own:
            return own
        file = resolve(target, files, paths, names)
        if file:
            anchor = target.partition('#')[2]
            return anchor and _block(blocks, anchor, file[0]['filepath']) or file
        return _block(blocks, target) or target

    def repl(m):
        target = m.group(1).strip()
        if target.startswith(('http://', 'https://')):
            return m.group(0)
        shown = label(target, m.group(2))
        hit = pick(target)
        if not hit:
            return shown
        key = _fold(hit) if isinstance(hit, str) else tuple(map(id, hit))
        if key not in order:
            found.append(hit)
            order[key] = len(found)
        return mark(shown, order[key])

    return _RE.sub(repl, text), found


def linked(filepath, cases):
    files, paths, names = index(cases)
    sources = set()
    for case in cases:
        fp = case.get('filepath')
        if not fp or fp == filepath or fp in sources:
            continue
        for m in _ANY_RE.finditer(case.get('raw', case.get('text', ''))):
            hit = resolve(m.group(1).strip(), files, paths, names)
            if hit and hit[0]['filepath'] == filepath:
                sources.add(fp)
                break
    return len(sources)
