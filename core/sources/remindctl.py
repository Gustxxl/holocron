from datetime import datetime
from core import system
from . import cli, macos

NAME = 'Reminders'
KEY = 'remindctl'
KIND = 'tasks'
SETUP = 'macos'
PROGRAM = 'remindctl'
REPO = 'openclaw/remindctl'
TAP = 'steipete/tap/remindctl'
MACOS = 14
ABOUT = 'Apple Reminders'
LISTS = 'lists'
PRIVACY = 'Reminders'
PRIVACY_URL = 'x-apple.systempreferences:com.apple.preference.security?Privacy_Reminders'
HINT = 'No access to Reminders. Open settings (s) > Reminders'
SHOWN = 3
AHEAD = 0

supported = macos.supported


def status():
    return macos.status(PROGRAM, MACOS, authorized)


def authorize():
    cli.run_ok(PROGRAM, 'authorize', timeout=120)
    return authorized()


def available():
    return system.IS_MACOS and cli.available(PROGRAM)


def authorized():
    data = cli.run_json(PROGRAM, 'status', '--json')
    return isinstance(data, dict) and data.get('authorized') is True


def lists():
    return parse_lists(cli.run_json(PROGRAM, 'list', '--json'))


def items():
    return parse_items(cli.run_json(PROGRAM, 'open', '--json'))


def complete(task_id):
    return cli.run_ok(PROGRAM, 'complete', task_id)


def reopen(task_id):
    return cli.run_ok(PROGRAM, 'edit', task_id, '--incomplete')


def completed():
    return parse_items(cli.run_json(PROGRAM, 'completed', '--json'))


def add(title, list_id, place=None, due=None):
    args = ['add', '--title', title, '--list-id', list_id]
    if place:
        args += ['--location', place['address'], '--radius', str(place['radius'])]
        if place['proximity'] == 'leaving':
            args.append('--leaving')
    if due is not None:
        args += ['--due', _stamp(due)]
    return cli.run_ok(PROGRAM, *args)


def edit(task_id, title=None, notes=None, **when):
    args = []
    if title is not None:
        args += ['--title', title]
    if notes is not None:
        args += ['--notes', notes]
    for key in ('due', 'alarm'):
        if key in when:
            args += [f'--{key}', _stamp(when[key])] if when[key] is not None else [f'--clear-{key}']
    return cli.run_ok(PROGRAM, 'edit', task_id, *args) if args else True


def move(task_id, list_id):
    return cli.run_ok(PROGRAM, 'edit', task_id, '--list-id', list_id)


def parse_lists(data):
    if not isinstance(data, list):
        return None
    return [{'id': d['id'], 'title': d['title']} for d in data
            if isinstance(d, dict) and isinstance(d.get('id'), str) and isinstance(d.get('title'), str)]


def parse_items(data):
    if not isinstance(data, list):
        return None
    return [t for t in map(_task, data) if t]


def _stamp(due):
    return f'{due:%Y-%m-%d %H:%M}' if isinstance(due, datetime) else due.isoformat()


def _task(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get('id'), str):
        return None
    trigger = raw.get('locationTrigger')
    return {
        'id': raw['id'],
        'title': str(raw.get('title') or '').strip() or '(untitled)',
        'due': cli.parse_time(raw.get('dueDate')),
        'all_day': raw.get('dueDateIsAllDay') is True,
        'alarm': cli.parse_time(raw.get('alarmDate')),
        'list': raw.get('listID'),
        'list_name': str(raw.get('listName') or '').strip(),
        'notes': str(raw.get('notes') or '').strip(),
        'place': str(trigger.get('address') or '').strip() if isinstance(trigger, dict) else '',
        'done': raw.get('isCompleted') is True,
        'finished': cli.parse_time(raw.get('completionDate')),
    }
