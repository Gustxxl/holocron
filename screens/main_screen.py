from datetime import date, datetime, timedelta
from pathlib import Path
import shutil

from core import archives, routines, schedule, sources, tasks
from core.commands import lookup
from core.settings import home_order, operator_name
from core.sources import registry, swiftbar
from screens.events_screen import agenda
from core.updater import pending_update
from screens.schedule_screen import duty_line
from screens.search_screen import search_screen
from screens.tasks_screen import finished_today, summary, when
from ui.format import day_label
from ui.interface import clear_screen, clip, dim, one_line, pause, read_command, visible, Home

APP_DIR = Path(__file__).resolve().parent.parent
LOGO = APP_DIR / "ui" / "logo.txt"
LOGO_TEXT = "HOLOCRON"
BAR_SOON = timedelta(minutes=30)
BAR_ROWS = 10


def main_screen(first=None, query=None):
    if query:
        first = None
        try:
            _handle(query)
        except Home:
            pass
    while True:
        frame = first or main_frame()
        first = None
        clear_screen()
        print(frame)
        try:
            _handle(read_command('system> ', lines=True))
        except Home:
            continue


def main_frame():
    return '\n'.join(_frame())


def _handle(raw):
    if raw.strip().lower() in ('', 'b', 'back'):
        return
    command = lookup(one_line(raw))
    if command:
        command.run(one_line(raw))
        return
    if not archives.is_loaded():
        hint = 'Archive not found — check settings.' if archives.missing() else 'No archive set — add a path in settings.'
        print(dim(hint))
        pause(feedback='warning')
        return
    search_screen(raw)


def _plan():
    source = registry.active('tasks')
    if source and source.available():
        routines.plan(source)


def bar_frame(now=None):
    now = now or datetime.now()
    _plan()
    sched = schedule.load()
    status = sched.status(now)
    on = bool(status and status.on)
    found, groups = _bar_tasks(now, status.shift.end if on else None)
    duty = duty_line(now, sched)
    late = [t for t in found if tasks.is_overdue(t, now)]
    soon = [t for t in found if not t['all_day'] and now <= t['due'] <= now + BAR_SOON]
    head = (late or soon or [None])[0]
    return swiftbar.render(on, _bar_title(head), bool(late), visible(duty) if duty else '', groups)


def bar_toggle(action, task_id, now=None):
    now = now or datetime.now()
    source = registry.active('tasks')
    if source is None or not source.available():
        return False
    chosen = sources.selected(source.KEY)
    if action == 'done':
        known = {t['id'] for t in source.items() or [] if not t['done'] and t['list'] in chosen}
        return task_id in known and source.complete(task_id)
    known = {t['id'] for t in finished_today(source, chosen, now)}
    return task_id in known and source.reopen(task_id)


def _bar_tasks(now, end):
    source = registry.active('tasks')
    if source is None or not source.available():
        return [], []
    found = source.items()
    if found is None:
        return [], [('', [(f'Could not read {source.NAME}', True, None)])]
    chosen = sources.selected(source.KEY)
    shown, _ = tasks.upcoming([t for t in found if t['due']], chosen, BAR_ROWS)
    groups = {}
    for task in shown:
        groups.setdefault(_bar_group(task, now, end), []).append(_bar_row(task, now))
    finished = finished_today(source, chosen, now)[-BAR_ROWS:]
    if finished:
        groups['done today'] = [(f'✓ {t["finished"]:%H:%M} {t["title"]}', False, ('undo', t['id'])) for t in finished]
    return shown, list(groups.items())


def _bar_group(task, now, end):
    if tasks.is_overdue(task, now):
        return 'overdue'
    if end and task['due'] < end:
        return f'this shift · until {end:%H:%M}'
    return day_label(task['due'].date(), now.date())


def _bar_row(task, now):
    late = tasks.is_overdue(task, now)
    if late:
        stamp = when(task, now)
    else:
        stamp = '' if task['all_day'] else f'{task["due"]:%H:%M}'
    return ' '.join(p for p in ('○', stamp, task['title']) if p), late, ('done', task['id'])


def _bar_title(task):
    if task is None:
        return ''
    return task['title'] if task['all_day'] else f'{task["due"]:%H:%M} {task["title"]}'


def _frame():
    _plan()
    lines = [dim(date.today().strftime('%a %b %d %Y'))]
    operator = operator_name()
    if operator:
        lines.append(f"Welcome back, {operator}")
    total = archives.count()
    if total:
        lines.append(dim(f'{total} cases indexed'))
    for key in home_order():
        block = _block(key)
        if block:
            lines += ['', *block]
    if pending_update():
        lines.append(dim("Update available — type 'update'"))
    lines.append('')
    width = shutil.get_terminal_size().columns - 1
    return [*_logo(), *(clip(line, width) for line in lines)]


def _block(key):
    if key not in registry.BLOCKS:
        line = duty_line()
        return [line] if line else []
    source = registry.block(key)
    if source is None:
        return []
    return agenda(source) if source.KIND == 'events' else summary(source)


def _logo():
    lines = LOGO.read_text(encoding="utf-8").splitlines()
    width = shutil.get_terminal_size().columns
    block = max((len(line) for line in lines), default=0)
    if block > width:
        return ['', dim(LOGO_TEXT.center(width))]
    pad = ' ' * ((width - block) // 2)
    return ['', *(dim(pad + line) for line in lines), '']
