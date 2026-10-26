import shutil
from pathlib import Path

from core import archives, editor, favorites, tree
from core.settings import archive_path, excalidraw_path, new_cases_path, page_rows, vault_path
from screens.help_screen import show_help
from ui.format import plural
from ui.interface import clear_screen, dim, haptic, num, read_command, nav_line
from screens.search_screen import add_card, by_name, list_rows, open_case, search_screen

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
        found = next((n for n in tree.entries(node) if n['name'] == name), None) if tree.is_branch(node) else None
        if found is None:
            break
        stack.append(found)
    return stack


def tree_screen(start=None, before=False, after=False):
    root, page = _build(), 0
    trail = (tree.trail(root, start) if start else None) or []
    top = len(trail)
    while True:
        stack = _walk(root, trail)
        trail = [n['name'] for n in stack[1:]]
        node = stack[-1]
        items = tree.entries(node) if tree.is_branch(node) else _cases(node)
        edge = start is not None and len(trail) <= top
        frame, page = _frame(stack, items, page, edge and before, edge and after)
        clear_screen()
        print(frame)
        command = read_command('tree> ')
        low = command.lower()
        if low in ('b', 'back'):
            if len(trail) <= top:
                return
            trail.pop()
            page = 0
        elif low in ('h', 'help'):
            show_help()
        elif low == 'n':
            if edge and after and page + 1 >= _pages(items, page_rows()):
                return 'n'
            page += 1
        elif low == 'p':
            if edge and before and page == 0:
                return 'p'
            page -= 1
        elif low == 'nn':
            page = len(items)
        elif low == 'pp':
            page = 0
        elif low in ('f', 'fav') and node.get('case'):
            favorites.toggle(node['case'])
            haptic('toggle')
        elif low == 'a' and node['kind'] == 'lane' and editor.available():
            add_card(node['filepath'], node['name'])
            archives.load()
            root = _build()
        elif command == '':
            archives.load(force=True)
            root = _build()
        elif command.isdigit() and 1 <= int(command) <= len(items):
            item = items[int(command) - 1]
            if not tree.is_branch(node):
                _read(items, int(command))
                root = _build()
            elif item['kind'] == 'note':
                _read(item['cases'], 1)
                root = _build()
            else:
                trail.append(item['name'])
                page = 0


def _cases(node):
    return node['cases'] if node['kind'] == 'lane' else by_name(node['cases'])


def _read(cases, number):
    query = open_case([(0, c) for c in cases], number, '', rerun=False)
    if query:
        search_screen(query)


def _pages(items, size):
    return max(1, -(-len(items) // size))


def _frame(stack, items, page, before=False, after=False):
    width = shutil.get_terminal_size().columns - 1
    size = page_rows()
    pages = _pages(items, size)
    page = max(0, min(page, pages - 1))
    start = page * size
    chunk = items[start:start + size]
    folder = tree.is_branch(stack[-1])
    board = stack[-1].get('case')
    pinned = bool(board) and favorites.is_pinned(board)
    head = ' > '.join(n['name'] for n in stack) + (' · pinned' if pinned else '')
    if not folder:
        head += '   ' + plural(len(items), 'card' if stack[-1]['kind'] == 'lane' else 'block')
    head += f'   {page + 1}/{pages}' if pages > 1 else ''
    digits = len(str(len(items)))
    rows = _entries(chunk, start, digits) if folder else list_rows(chunk, start, len(items), width)
    lines = [dim(head), '', *(rows or [dim('  Nothing indexed')])]
    nav = [('number', 'open', '#', 'open')] if items else []
    if stack[-1]['kind'] == 'lane' and editor.available():
        nav.append(('a', 'add card', 'a', 'add'))
    if board:
        nav.append(('f', 'unpin' if pinned else 'pin', 'f', 'unpin' if pinned else 'pin'))
    if page + 1 < pages or after:
        nav.append(('n', 'next'))
    if page > 0 or before:
        nav.append(('p', 'prev'))
    nav += [('b', 'back'), ('h', 'help')]
    lines += ['', dim(nav_line(nav, width)), '']
    return '\n'.join(lines), page


def _entries(chunk, start, digits):
    names = [n['name'][:NAME_MAX] + ('/' if n['kind'] == 'folder' else '') for n in chunk]
    col = max((len(s) for s in names), default=0)
    cw = max((len(str(tree.count(n))) for n in chunk if n['kind'] == 'folder'), default=0)
    return [f'{num(i, digits)}{name.ljust(col)}   {_info(node, cw)}'.rstrip()
            for i, (node, name) in enumerate(zip(chunk, names), start + 1)]


def _info(node, cw):
    if node['kind'] == 'folder':
        return dim(str(tree.count(node)).rjust(cw))
    if node['kind'] == 'kanban':
        return dim(f'kanban · {plural(tree.count(node), "card")}')
    if node['kind'] == 'lane':
        return dim(plural(len(node['cases']), 'card'))
    if node['kind'] == 'board':
        n = len(node['cases'])
        return dim(f'board · {n} block' + ('' if n == 1 else 's'))
    return ''
