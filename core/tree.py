from pathlib import Path

ROOT = 'Archive'
_SUFFIXES = ('.excalidraw.md', '.excalidraw', '.md')


def _name(path):
    for suffix in _SUFFIXES:
        if path.name.endswith(suffix):
            return path.name[:-len(suffix)]
    return path.name


def _folder(name):
    return {'name': name, 'kind': 'folder', 'folders': {}, 'files': {}}


def _parts(path, bases, flat):
    for base in bases:
        if path.is_relative_to(base):
            rel = path.relative_to(base).parts
            return rel if base == flat else (base.name, *rel)
    return (path.name,)


def build(cases, vault=None, folders=()):
    flat = Path(vault).resolve() if vault else None
    bases = [b for b in (flat, *(Path(p).resolve() for p in folders)) if b]
    root, paths = _folder(ROOT), {}
    for case in cases:
        fp = case.get('filepath')
        if not fp:
            continue
        if fp not in paths:
            paths[fp] = Path(fp).resolve()
        path = paths[fp]
        parts = _parts(path, bases, flat)
        node = root
        for part in parts[:-1]:
            node = node['folders'].setdefault(part, _folder(part))
        kind = 'note' if case.get('filename') else 'board'
        leaf = node['files'].setdefault(str(path), {'name': _name(path), 'kind': kind, 'cases': []})
        leaf['cases'].append(case)
    return root


def entries(node):
    folders = sorted(node['folders'].values(), key=lambda n: n['name'].casefold())
    files = sorted(node['files'].values(), key=lambda n: n['name'].casefold())
    return [*folders, *files]


def count(node):
    if node['kind'] != 'folder':
        return len(node['cases'])
    return sum(count(n) for n in entries(node))
