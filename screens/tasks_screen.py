import re
from datetime import datetime
from core import dates, editor, schedule, sources, tasks, waypoints
from screens.help_screen import show_help
from ui.format import day_label
from ui.interface import clear_screen, dim, error, haptic, is_back, pause, pick, read_command, red, nav_line
from screens.sources_screen import lists_screen, source_setup, unreadable
from screens.routines_screen import routines_screen

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
        chosen = sources.selected(source.KEY)
        groups = [(title, items) for title, items in tasks.group(found, lists, chosen) if items]
        now = datetime.now()
        finished = finished_today(source, chosen, now)
        flat = tasks.numbered(groups) + finished
        frame = '\n'.join(_frame(source, chosen, groups, now, finished))
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
        elif low == 't':
            routines_screen(source)
        elif low == 'a':
            text = read_command('text> ')
            if text:
                _add(source, text, lists, chosen)
        elif check and 1 <= int(check.group(1)) <= len(flat):
            _toggle(source, flat[int(check.group(1)) - 1])
        elif pick(low, len(flat)):
            _open(source, flat, int(low))


def open_tasks(source, now, limit):
    chosen = sources.selected(source.KEY)
    if not chosen or not limit or not source.available():
        return [], 0
    found = source.items()
    if not found:
        return [], 0
    ahead = sources.option(source.KEY, 'ahead', source.AHEAD)
    found = [t for t in found if dates.within(t['due'], now, ahead)]
    return tasks.upcoming(found, chosen, limit)


def summary(source, now=None):
    now = now or datetime.now()
    shown, rest = open_tasks(source, now, sources.option(source.KEY, 'shown', source.SHOWN))
    lines = []
    for task in shown:
        line = f'○ {task_line(task, now)}'
        if task.get('list_name'):
            line += dim(f' #{task['list_name']}')
        lines.append(line)
    if rest:
        lines.append(dim(f'+{rest} more'))
    done = finished_today(source, sources.selected(source.KEY), now) if source.available() else []
    if done:
        lines.append(dim(f'✓ {len(done)} done today'))
    return lines


def finished_today(source, chosen, now):
    read = getattr(source, 'completed', None)
    if read is None:
        return []
    status = schedule.load().status(now)
    start = tasks.since(now, status.shift.start if status and status.on else None)
    return tasks.done_today(read() or [], chosen, start)


def _frame(source, chosen, groups, now, finished=()):
    lines = [dim(source.NAME), '']
    if not chosen:
        lines += [dim('No lists selected'), '']
    elif not groups:
        lines += [dim('No open tasks'), '']
    digits = len(str(sum(len(items) for _, items in groups) + len(finished)))
    n = 0
    for title, items in groups:
        lines.append(dim(f'#{title}'))
        for task in items:
            n += 1
            lines.append(f'  {dim(str(n).rjust(digits))} ○ {task_line(task, now)}')
        lines.append('')
    if finished:
        lines.append(dim('done today'))
        for task in finished:
            n += 1
            lines.append(dim(f'  {str(n).rjust(digits)} ✓ {task["title"]} · {task["finished"]:%H:%M}'))
        lines.append('')
    mark = 'done/undo' if finished else 'done'
    nav = [('number', 'open', '#', 'open'), ('x number', mark, 'x#', mark)] if n else []
    nav += [('a', 'add'), ('t', 'routines'), ('s', 'lists'), ('b', 'back'), ('h', 'help')]
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
            if _toggle(source, task):
                return
        elif command == 'e' and editor.available():
            _edit(source, task)
        elif command == 'n' and number < len(flat):
            number += 1
        elif command == 'p' and number > 1:
            number -= 1
        elif command == 'nn':
            number = len(flat)
        elif command == 'pp':
            number = 1
        elif pick(command, len(flat)):
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
    if task.get('done') and task.get('finished'):
        lines.append(dim(f'done {task["finished"]:%H:%M}'))
    nav = [('x', 'undo' if task.get('done') else 'done')]
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


def _toggle(source, task):
    if not task['done']:
        return _complete(source, task)
    if source.reopen(task['id']):
        haptic('toggle')
        return True
    error(f'Could not reopen: {task["title"]}')
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
    if not source.add(draft['title'], draft['list'], draft['place'], draft['due']):
        error('Could not add the reminder')
        return
    if draft['list'] in chosen:
        haptic('success')
        return
    name = next((l['title'] for l in lists if l['id'] == draft['list']), '')
    clear_screen()
    print(dim(f'Added to #{name} — hidden in settings'))
    pause(feedback='success')


def task_line(task, now):
    label = _label(task, now)
    return task['title'] + (dim(' · ') + label if label else '')


def when(task, now):
    due = task['due']
    if due is None:
        return ''
    text = day_label(due.date(), now.date())
    return text if task['all_day'] else f'{text} {due:%H:%M}'


def _label(task, now):
    text = when(task, now)
    if not text:
        return ''
    return red(text) if tasks.is_overdue(task, now) else dim(text)
