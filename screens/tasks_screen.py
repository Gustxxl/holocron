import re
from datetime import datetime
from core import dates, editor, sources, tasks, waypoints
from screens.help_screen import show_help
from ui.format import day_label
from ui.interface import clear_screen, dim, error, haptic, is_back, pause, read_command, red, nav_line
from screens.sources_screen import lists_screen, source_setup, unreadable

_CHECK_RE = re.compile(r'x\s*(\d+)')


def tasks_screen(source):
    if not source_setup(source):
        return
    while True:
        lists = source.lists()
        found = source.items() if lists is not None else None
        if found is None:
            unreadable(source)
            return
        chosen = sources.selected(source. KEY)
        groups = [(title, items) for title, items in tasks.group(found, lists, chosen) if items]
        flat = tasks.numbered(groups)
        frame = '\n'.join(_frame(source, chosen, groups, datetime.now()))
        clear_screen()
        print(frame)
        command = read_command(f'{source.NAME.lower()}> ')
        low = command.lower()
        check = _CHECK_RE.fullmatch(low)
        if is_back(low):
            return
        if low in ('h', 'help'):
            show_help()
        elif low in ('s', 'settings'):
            lists_screen(source)
        elif low == 'a':
            text = read_command('text> ')
            if text:
                _add(source, text, lists, chosen)
        elif check and 1 <= int(check.group(1)) <= len(flat):
            _complete(source, flat[int(check.group(1)) - 1])
        elif low.isdigit() and 1 <= int(low) <= len(flat):
            _open(source, flat, int(low))


def summary(source, now=None):
    chosen = sources.selected(source.KEY)
    limit = sources.option(source.KEY, 'shown', source.SHOWN)
    if not chosen or not limit or not source.available():
        return []
    found = source.items()
    if not found:
        return []
    now = now or datetime.now()
    ahead = sources.option(source.KEY, 'ahead', source.AHEAD)
    found = [t for t in found if dates.within(t['due'], now, ahead)]
    shown, rest = tasks.upcoming(found, chosen, limit)
    lines = []
    for task in shown:
        line = f'○ {_line(task, now)}'
        if task.get('list_name'):
            line += dim(f' #{task['list_name']}')
        lines.append(line)
    if rest:
        lines.append(dim(f'+{rest} more'))
    return lines


def _frame(source, chosen, groups, now):
    lines = [dim(source.NAME), '']
    if not chosen:
        lines += [dim('No lists selected'), '']
    elif not groups:
        lines += [dim('No open tasks'), '']
    digits = len(str(sum(len(items) for _, items in groups)))
    n = 0
    for title, items in groups:
        lines.append(dim(f'#{title}'))
        for task in items:
            n += 1
            lines.append(f'  {dim(str(n).rjust(digits))} ○ {_line(task, now)}')
        lines.append('')
    nav = [('number', 'open', '#', 'open'), ('x number', 'done', 'x#', 'done')] if n else []
    nav += [('a', 'add'), ('s', 'lists'), ('b', 'back'), ('h', 'help')]
    lines += [dim(nav_line(nav)), '']
    return lines


def _open(source, flat, number):
    points = waypoints.load()
    while 1 <= number <= len(flat):
        task = flat[number - 1]
        frame = '\n'.join(_card(task, number, len(flat), datetime.now(), points))
        clear_screen()
        print(frame)
        command = read_command('reminder> ').lower()
        if is_back(command):
            return
        if command in ('h', 'help'):
            show_help()
        elif command == 'x':
            if _complete(source, task):
                return
        elif command == 'e' and editor.available():
            _edit(source, task)
        elif command == 'n' and number < len(flat):
            number += 1
        elif command == 'p' and number > 1:
            number -= 1
        elif command.isdigit():
            number = int(command)


def _card(task, number, total, now, points):
    tag = f'#{task['list_name']}' if task.get('list_name') else ''
    lines = [dim(f'── {number}/{total}  {tag} ' + '─' * 20), '', task['title']]
    label = _label(task, now)
    if label:
        lines.append(label)
    if task.get('place'):
        name = waypoints.find(points, task['place'])
        lines.append(dim(f'@{name}' if name else task['place']))
    if task.get('notes'):
        lines += ['', task['notes']]
    nav = [('x', 'done')]
    if editor.available():
        nav.append(('e', 'edit'))
    if number < total:
        nav.append(('n', 'next'))
    if number > 1:
        nav.append(('p', 'prev'))
    nav += [('b', 'back'), ('h', 'help')]
    lines += ['', dim(nav_line(nav)), '']
    return lines


def _complete(source, task):
    if source.complete(task['id']):
        haptic('toggle')
        return True
    error(f'Could not complete: {task["title"]}')
    return False


def _edit(source, task):
    text = editor.edit_text(tasks.to_text(task))
    if text is None:
        error('Could not open the editor')
        return
    found = tasks.changes(task, text)
    if found is None:
        error('Empty text — edit cancelled')
        return
    if not found:
        return
    if not source.edit(task['id'], **found):
        error('Could not save the reminder')
        return
    task.update(found)
    haptic('success')


def _add(source, text, lists, chosen):
    draft, problem = tasks.parse_add(text, lists, sources.default(source.KEY, lists), waypoints.load())
    if problem:
        error(problem)
        return
    if not source.add(draft['title'], draft['list'], draft['place']):
        error('Could not add the reminder')
        return
    if draft['list'] in chosen:
        haptic('success')
        return
    name = next((l['title'] for l in lists if l['id'] == draft['list']), '')
    clear_screen()
    print(dim(f'Added to #{name} — hidden in settings'))
    pause()


def _line(task, now):
    label = _label(task, now)
    return task['title'] + (dim(' · ') + label if label else '')


def _label(task, now):
    due = task['due']
    if due is None:
        return ''
    text = day_label(due.date(), now.date())
    if not task['all_day']:
        text += f' {due:%H:%M}'
    return red(text) if tasks.is_overdue(task, now) else dim(text)
