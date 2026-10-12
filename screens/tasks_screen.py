from datetime import datetime
from core import sources, tasks
from ui.format import day_label
from ui.interface import clear_screen, dim, error, haptic, is_back, pause, read_command, red


def tasks_screen(source):
    while True:
        lists = source.lists()
        found = source.items() if lists is not None else None
        if found is None:
            _unreadable(source)
            return
        frame = '\n'.join(_frame(source, lists, found, datetime.now()))
        clear_screen()
        print(frame)
        command = read_command(f'{source.NAME.lower()}> ').lower()
        if is_back(command):
            return
        if command in ('h', 'help'):
            from core.commands import HELP_SECTIONS
            from screens.help_screen import render_help
            clear_screen()
            render_help(HELP_SECTIONS)
            pause()
        elif command in ('s', 'settings'):
            lists_screen(source)


def lists_screen(source):
    lists = source.lists()
    if lists is None:
        _unreadable(source)
        return
    while True:
        chosen = sources.selected(source.KEY)
        lines = [dim(f'Settings > {source.NAME}'), '']
        for i, l in enumerate(lists, 1):
            lines.append(f'{i}) {l["title"]}' + (dim('  ✓') if l['id'] in chosen else ''))
        if not lists:
            lines.append('No lists')
        lines += ['', dim('  [number] show / hide   [b] back'), '']
        frame = '\n'.join(lines)
        clear_screen()
        print(frame)
        command = read_command('lists> ')
        if is_back(command):
            return
        if command.isdigit() and 1 <= int(command) <= len(lists):
            sources.toggle_list(source.KEY, lists[int(command) - 1]['id'])
            haptic('toggle')


def _unreadable(source):
    error(source.HINT if not source.authorized() else f'Could not read {source.NAME}')


def _frame(source, lists, found, now):
    chosen = sources.selected(source.KEY)
    groups = [(title, items) for title, items in tasks.group(found, lists, chosen) if items]
    lines = [dim(source.NAME), '']
    if not chosen:
        lines += [dim('No lists selected'), '']
    elif not groups:
        lines += [dim('No open tasks'), '']
    for title, items in groups:
        lines.append(dim(title))
        lines += [_row(t, now) for t in items]
        lines.append('')
    lines += [dim('  [s] lists   [b] back   [h] help'), '']
    return lines


def _row(task, now, with_list=False):
    line = f'○ {task["title"]}'
    due = task['due']
    if due is not None:
        label = day_label(due.date(), now.date())
        if not task['all_day']:
            label += f' {due:%H:%M}'
        line += dim(' · ') + (red(label) if tasks.is_overdue(task, now) else dim(label))
    if with_list and task.get('list_name'):
        line += dim(f' · {task["list_name"]}')
    return line


def summary(source, now=None):
    chosen = sources.selected(source.KEY)
    if not chosen or not source.available():
        return []
    found = source.items()
    if not found:
        return []
    shown, rest = tasks.upcoming(found, chosen)
    now = now or datetime.now()
    lines = [_row(t, now, with_list=True) for t in shown]
    if rest:
        lines.append(dim(f'+{rest} more'))
    return lines
