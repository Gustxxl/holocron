from datetime import date, datetime, timedelta
from pathlib import Path
import shutil

from core import archives, dates, events, routines, schedule, sources, tasks, waypoints
from core.commands import lookup
from core.settings import home_order, operator_name
from core.sources import registry, swiftbar
from screens.events_screen import agenda, event_time
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
BAR_ASK = 'New reminder: title, optional time, date, #list and @place'


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
    meetings, days = _bar_events(now)
    duty = duty_line(now, sched)
    late = [t for t in found if tasks.is_overdue(t, now)]
    soon = sorted([(t['due'], t['title']) for t in found if not t['all_day'] and now <= t['due'] <= now + BAR_SOON]
                  + [(e['start'], e['title']) for e in meetings if not e['all_day'] and now <= e['start'] <= now + BAR_SOON])
    blocks = {'calendar': days, 'schedule': [('', [(visible(duty), False, None)])] if duty else [], 'reminders': groups}
    source = registry.active('tasks')
    ready = bool(source and source.available())
    return swiftbar.render(on, _bar_title(late, soon), bool(late), [blocks[key] for key in home_order()], ready)


def bar_add(today=None):
    source = registry.active('tasks')
    lists = source.lists() if source and source.available() else None
    if not lists:
        return False
    prompt, text = BAR_ASK, ''
    while True:
        text = swiftbar.ask(prompt, text)
        if not text:
            return False
        draft, problem = tasks.parse_add(text, lists, sources.default(source.KEY, lists), waypoints.load(), today)
        if not problem and source.add(draft['title'], draft['list'], draft['place'], draft['due']):
            return True
        prompt = problem or 'Could not add the reminder'


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
    ahead = sources.option(source.KEY, 'ahead', source.AHEAD)
    shown, _ = tasks.upcoming([t for t in found if t['due'] and dates.within(t['due'], now, ahead)], chosen, BAR_ROWS)
    groups = {}
    for task in shown:
        groups.setdefault(_bar_group(task, now, end), []).append(_bar_row(task, now))
    finished = finished_today(source, chosen, now)
    if finished:
        rows = [(f'✓ {t["finished"]:%H:%M} {t["title"]}', False, ('undo', t['id'])) for t in finished[-BAR_ROWS:]]
        groups[''] = [(f'✓ {len(finished)} done today', False, ('menu', rows))]
    return shown, list(groups.items())


def _bar_events(now):
    source = registry.active('events')
    chosen = sources.selected(source.KEY) if source else []
    if not chosen or not source.available():
        return [], []
    found = source.items()
    if found is None:
        return [], [('', [(f'Could not read {source.NAME}', True, None)])]
    ahead = sources.option(source.KEY, 'ahead', source.AHEAD)
    shown = [e for e in events.upcoming(found, chosen, now) if dates.within(e['start'], now, ahead)][:BAR_ROWS]
    days = events.by_day(shown, now)
    return shown, [(day_label(day, now.date()), [_bar_event(e, now) for e in items]) for day, items in days]


def _bar_event(event, now):
    link = events.meeting(event)
    text = f'{"↗" if link else "◇"} {event_time(event, now)} {event["title"]}'
    return text, False, ('open', link) if link else None


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


def _bar_title(late, soon):
    if late:
        task = late[0]
        return task['title'] if task['all_day'] else f'{task["due"]:%H:%M} {task["title"]}'
    return f'{soon[0][0]:%H:%M} {soon[0][1]}' if soon else ''


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
