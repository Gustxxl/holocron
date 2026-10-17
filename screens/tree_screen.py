import shutil
from pathlib import Path

from core import archives, tree
from core.settings import archive_path, excalidraw_path, new_cases_path, vault_path
from screens.help_screen import show_help
from ui.format import plural
from ui.interface import clear_screen, dim, read_command, nav_line
from screens.search_screen import by_name, list_rows, open_case, search_screen

PAGE = 15
NAME_MAX = 40


def _dir(path):
    return path if path and Path(path).is_dir() else None


def _build():
    folders = [p for p in (new_cases_path(), excalidraw_path(), archive_path()) if _dir(p)]
    return tree.build(archives.cases(), _dir(vault_path()), folders)


def _walk(root, trail):
    stack = [root]
    for name in trail:
        node = stack[-1]
        found = next((n for n in tree.entries(node) if n['name'] == name), None) if node['kind'] == 'folder' else None
        if found is None:
            break
        stack.append(found)
    return stack


def tree_screen():
    root, trail, page = _build(), [], 0
    while True:
        stack = _walk(root, trail)
        trail = [n['name'] for n in stack[1:]]
        node = stack[-1]
        items = tree.entries(node) if node['kind'] == 'folder' else by_name(node['cases'])
        frame, page = _frame(stack, items, page)
        clear_screen()
        print(frame)
        command = read_command('tree> ')
        low = command.lower()
        if low in ('b', 'back'):
            if not trail:
                return
            trail.pop()
            page = 0
        elif low in ('h', 'help'):
            show_help()
        elif low == 'n':
            page += 1
        elif low == 'p':
            page -= 1
        elif command == '':
            archives.load(force=True)
            root = _build()
        elif command.isdigit() and 1 <= int(command) <= len(items):
            item = items[int(command) - 1]
            if node['kind'] != 'folder':
                _read(items, int(command))
                root = _build()
            elif item['kind'] == 'note':
                _read(item['cases'], 1)
                root = _build()
            else:
                trail.append(item['name'])
                page = 0


def _read(cases, number):
    query = open_case([(0, c) for c in cases], number, '', rerun=False)
    if query:
        search_screen(query)


def _frame(stack, items, page):
    width = shutil.get_terminal_size().columns - 1
    pages = max(1, -(-len(items) // PAGE))
    page = max(0, min(page, pages - 1))
    start = page * PAGE
    chunk = items[start:start + PAGE]
    folder = stack[-1]['kind'] == 'folder'
    head = ' > '.join(n['name'] for n in stack)
    if not folder:
        head += '   ' + plural(len(items), 'block')
    head += f'   {page + 1}/{pages}' if pages > 1 else ''
    digits = len(str(len(items)))
    rows = _entries(chunk, start, digits) if folder else list_rows(chunk, start, len(items), width)
    lines = [dim(head), '', *(rows or [dim('  Nothing indexed')])]
    nav = [('number', 'open', '#', 'open')] if items else []
    if page + 1 < pages:
        nav.append(('n', 'next'))
    if page > 0:
        nav.append(('p', 'prev'))
    nav += [('b', 'back'), ('h', 'help')]
    lines += ['', dim(nav_line(nav, width)), '']
    return '\n'.join(lines), page


def _entries(chunk, start, digits):
    names = [n['name'][:NAME_MAX] + ('/' if n['kind'] == 'folder' else '') for n in chunk]
    col = max((len(s) for s in names), default=0)
    cw = max((len(str(tree.count(n))) for n in chunk if n['kind'] == 'folder'), default=0)
    return [f'  {dim(str(i).rjust(digits))} {name.ljust(col)}   {_info(node, cw)}'.rstrip()
            for i, (node, name) in enumerate(zip(chunk, names), start + 1)]


def _info(node, cw):
    if node['kind'] == 'folder':
        return dim(str(tree.count(node)).rjust(cw))
    if node['kind'] == 'board':
        n = len(node['cases'])
        return dim(f'board · {n} block' + ('' if n == 1 else 's'))
    return ''
