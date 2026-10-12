import re
from pathlib import PurePath

_RE = re.compile(r'(?<!!)\[\[([^\]|\\]+)(?:\\?\|([^\]]+))?\]\]')
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


def numbered(text, cases, mark):
    files, paths, names = index(cases)
    found, order = [], {}

    def repl(m):
        target = m.group(1).strip()
        if target.startswith(('http://', 'https://')):
            return m.group(0)
        shown = label(target, m.group(2))
        cases_ = resolve(target, files, paths, names)
        if cases_ is None:
            return shown
        fp = cases_[0]['filepath']
        if fp not in order:
            found.append(cases_)
            order[fp] = len(found)
        return mark(shown, order[fp])

    return _RE.sub(repl, text), found
