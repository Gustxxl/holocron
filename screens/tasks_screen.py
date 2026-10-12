import re
from datetime import datetime
from core import editor, sources, tasks
from ui.format import day_label
from ui.interface import clear_screen, dim, error, haptic, is_back, pause, read_command, red

_CHECK_RE = re.compile(r'x\s*(\d+)')
_DEFAULT_RE = re.compile(r'd\s*(\d+)')


def tasks_screen(source):
    while True:
        lists = source.lists()
        found = source.items() if lists is not None else None
        if found is None:
            _unreadable(source)
            return
        chosen = sources.selected(source.KEY)
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
            _help()
        elif low in ('s', 'settings'):
            lists_screen(source)
        elif command.startswith('+'):
            _add(source, command[1:], lists, chosen)
        elif check and 1 <= int(check.group(1)) <= len(flat):
            _complete(source, flat[int(check.group(1)) - 1])
        elif low.isdigit() and 1 <= int(low) <= len(flat):
            _open(source, flat, int(low))


def lists_screen(source):
    lists = source.lists()
    if lists is None:
        _unreadable(source)
        return
    while True:
        chosen = sources.selected(source.KEY)
        main = sources.default(source.KEY, lists)
        lines = [dim(f'Settings > {source.NAME}'), '']
        for i, l in enumerate(lists, 1):
            mark = dim('  ✓') if l['id'] in chosen else ''
            mark += dim('  default') if l['id'] == main else ''
            lines.append(f'{i}) {l["title"]}{mark}')
        if not lists:
            lines.append('No lists')
        lines += ['', dim('  [number] show / hide   [d number] default   [b] back'), '']
        frame = '\n'.join(lines)
        clear_screen()
        print(frame)
        command = read_command('lists> ').lower()
        pick = _DEFAULT_RE.fullmatch(command)
        if is_back(command):
            return
        if pick and 1 <= int(pick.group(1)) <= len(lists):
            sources.set_default(source.KEY, lists[int(pick.group(1)) - 1]['id'])
            haptic('toggle')
        elif command.isdigit() and 1 <= int(command) <= len(lists):
            sources.toggle_list(source.KEY, lists[int(command) - 1]['id'])
            haptic('toggle')


def summary(source, now=None):
    chosen = sources.selected(source.KEY)
    if not chosen or not source.available():
        return []
    found = source.items()
    if not found:
        return []
    shown, rest = tasks.upcoming(found, chosen)
    now = now or datetime.now()
    lines = []
    for task in shown:
        line = f'○ {_line(task, now)}'
        if task.get('list_name'):
            line += dim(f' · {task["list_name"]}')
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
        lines.append(dim(title))
        for task in items:
            n += 1
            lines.append(f'  {dim(str(n).rjust(digits))} ○ {_line(task, now)}')
        lines.append('')
    nav = '  [number] open   ' if n else '  '
    lines += [dim(nav + '[s] lists   [b] back   [h] help'), '']
    return lines


def _open(source, flat, number):
    while 1 <= number <= len(flat):
        task = flat[number - 1]
        frame = '\n'.join(_card(task, number, len(flat), datetime.now()))
        clear_screen()
        print(frame)
        command = read_command('reminder> ').lower()
        if is_back(command):
            return
        if command in ('h', 'help'):
            _help()
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


def _card(task, number, total, now):
    lines = [dim(f'── {number}/{total}  {task.get("list_name", "")} ' + '─' * 20), '', task['title']]
    label = _label(task, now)
    if label:
        lines.append(label)
    if task.get('notes'):
        lines += ['', task['notes']]
    nav = '  [x] done   ' + ('[e] edit   ' if editor.available() else '')
    nav += '[n] next   ' if number < total else ''
    nav += '[p] prev   ' if number > 1 else ''
    nav += '[b] back   [h] help'
    lines += ['', dim(nav), '']
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
    default = sources.default(source.KEY, lists)
    title, list_id, problem = tasks.parse_add(text, lists, default)
    if problem:
        error(problem)
        return
    if not source.add(title, list_id):
        error('Could not add the reminder')
        return
    if list_id in chosen:
        haptic('success')
        return
    name = next((l['title'] for l in lists if l['id'] == list_id), '')
    clear_screen()
    print(dim(f'Added to {name} — hidden in settings'))
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


def _unreadable(source):
    error(source.HINT if not source.authorized() else f'Could not read {source.NAME}')


def _help():
    from core.commands import HELP_SECTIONS
    from screens.help_screen import render_help
    clear_screen()
    render_help(HELP_SECTIONS)
    pause()
