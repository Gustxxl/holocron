import shutil
from pathlib import Path

from core import archives, editor, favorites, search, tree
from core.settings import archive_path, excalidraw_path, new_cases_path, page_rows, vault_path
from screens.help_screen import show_help
from ui.format import plural
from ui.interface import clear_screen, dim, haptic, num, pause, pick, read_command, nav_line
from screens.search_screen import (MIN_QUERY, _nothing, _suggest, add_card, by_name, list_rows, open_case,
                                   search_screen)

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
    root, page, found = _build(), 0, None
    trail = (tree.trail(root, start) if start else None) or []
    top = len(trail)
    while True:
        stack = _walk(root, trail)
        trail = [n['name'] for n in stack[1:]]
        node = stack[-1]
        if found:
            query, items, trails, pool = found
        else:
            query, trails, pool = '', None, None
            items = tree.entries(node) if tree.is_branch(node) else _cases(node)
        edge = start is not None and len(trail) <= top and not found
        if found and not items:
            clear_screen()
            print(_nothing(query))
            tips = _suggest(pool, query)
            if tips:
                print(dim('Maybe: ' + ', '.join(tips)))
            print()
            print(dim('  [b] back   [h] help'))
            print()
            haptic('warning')
        else:
            frame, page = _frame(stack, items, page, edge and before, edge and after, query, trails)
            clear_screen()
            print(frame)
        command = read_command('tree> ')
        low = command.lower()
        if low in ('b', 'back') and found:
            found, page = None, 0
        elif low in ('b', 'back'):
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
        elif low in ('f', 'fav') and node.get('case') and not found:
            favorites.toggle(node['case'])
            haptic('toggle')
        elif low == 'a' and node['kind'] == 'lane' and editor.available() and not found:
            add_card(node['filepath'], node['name'])
            archives.load()
            root = _build()
        elif command == '' and found and not items:
            found, page = None, 0
        elif command == '':
            archives.load(force=True)
            root = _build()
            if found:
                found = _search(_walk(root, trail)[-1], query)
        elif pick(command, len(items)):
            item = items[int(command) - 1]
            if found and trails is None:
                _read(items, int(command), query)
                root = _build()
                found = _search(_walk(root, trail)[-1], query)
            elif found and item['kind'] != 'note':
                trail, found, page = [*trail, *trails[int(command) - 1]], None, 0
            elif not tree.is_branch(node):
                _read(items, int(command))
                root = _build()
            elif item['kind'] == 'note':
                _read(item['cases'], 1)
                root = _build()
            else:
                trail.append(item['name'])
                page = 0
        elif command.startswith('/') and len(command[1:].strip()) >= MIN_QUERY:
            search_screen(command[1:].strip())
            root = _build()
        elif not command.startswith('/') and len(command.strip()) >= MIN_QUERY:
            found, page = _search(node, command.strip()), 0
        else:
            clear_screen()
            print(f'Type at least {MIN_QUERY} characters.')
            pause(feedback='warning')


def _search(node, query):
    if node['kind'] == 'folder':
        named = [{'text': n['name'], 'path': p, 'node': n} for p, n in tree.descendants(node)]
        hits = [c for _, c in search.search(named, query)]
        return query, [c['node'] for c in hits], [c['path'] for c in hits], named
    cases = [c for lane in tree.entries(node) for c in lane['cases']] if node['kind'] == 'kanban' else node['cases']
    return query, [c for _, c in search.search(cases, query)], None, cases


def _cases(node):
    return node['cases'] if node['kind'] == 'lane' else by_name(node['cases'])


def _read(cases, number, query=''):
    asked = open_case([(0, c) for c in cases], number, query, rerun=False)
    if asked:
        search_screen(asked)


def _pages(items, size):
    return max(1, -(-len(items) // size))


def _frame(stack, items, page, before=False, after=False, query='', trails=None):
    width = shutil.get_terminal_size().columns - 1
    size = page_rows()
    pages = _pages(items, size)
    page = max(0, min(page, pages - 1))
    start = page * size
    chunk = items[start:start + size]
    folder = tree.is_branch(stack[-1]) and not query
    board = None if query else stack[-1].get('case')
    pinned = bool(board) and favorites.is_pinned(board)
    head = ' > '.join(n['name'] for n in stack) + (' · pinned' if pinned else '')
    if query:
        head += f'   "{query}"   {plural(len(items), "result")}'
    elif len(stack) == 1:
        head += '   ' + plural(tree.count(stack[0]), 'case')
    elif not folder:
        head += '   ' + plural(len(items), 'card' if stack[-1]['kind'] == 'lane' else 'block')
    head += f'   {page + 1}/{pages}' if pages > 1 else ''
    digits = len(str(len(items)))
    if trails is not None:
        rows = _entries(chunk, start, digits, trails[start:start + size])
    elif folder:
        rows = _entries(chunk, start, digits)
    else:
        rows = list_rows(chunk, start, len(items), width, query)
    lines = [dim(head), '', *(rows or [dim('  Nothing indexed')])]
    nav = [('number', 'open', '#', 'open')] if items else []
    if not query and stack[-1]['kind'] == 'lane' and editor.available():
        nav.append(('a', 'add card', 'a', 'add'))
    if board:
        nav.append(('f', 'unpin' if pinned else 'pin', 'f', 'unpin' if pinned else 'pin'))
    if page + 1 < pages or after:
        nav.append(('n', 'next'))
    if page > 0 or before:
        nav.append(('p', 'prev'))
    nav += [('type', 'search'), ('b', 'back'), ('h', 'help')]
    lines += ['', dim(nav_line(nav, width)), '']
    return '\n'.join(lines), page


def _entries(chunk, start, digits, trails=None):
    names = [n['name'][:NAME_MAX] + ('/' if n['kind'] == 'folder' else '') for n in chunk]
    col = max((len(s) for s in names), default=0)
    cw = max((len(str(tree.count(n))) for n in chunk if n['kind'] == 'folder'), default=0)
    places = [' > '.join(t[:-1]) for t in trails] if trails else [''] * len(chunk)
    return [f'{num(i, digits)}{name.ljust(col)}   {_place(where, _info(node, cw))}'.rstrip()
            for i, (node, name, where) in enumerate(zip(chunk, names, places), start + 1)]


def _place(where, info):
    if not where:
        return info
    return dim(where) + (dim(' · ') + info if info else '')


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
