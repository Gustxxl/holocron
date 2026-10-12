from core import system
from . import cli

NAME = 'Reminders'
KEY = 'remindctl'
KIND = 'tasks'
PROGRAM = 'remindctl'
HINT = 'No access to Reminders. Run: remindctl authorize'


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


def add(title, list_id, place=None):
    args = ['add', '--title', title, '--list-id', list_id]
    if place:
        args += ['--location', place['address'], '--radius', str(place['radius'])]
        if place['proximity'] == 'leaving':
            args.append('--leaving')
    return cli.run_ok(PROGRAM, *args)


def edit(task_id, title=None, notes=None):
    args = []
    if title is not None:
        args += ['--title', title]
    if notes is not None:
        args += ['--notes', notes]
    return cli.run_ok(PROGRAM, 'edit', task_id, *args) if args else True


def parse_lists(data):
    if not isinstance(data, list):
        return None
    return [{'id': d['id'], 'title': d['title']} for d in data
            if isinstance(d, dict) and isinstance(d.get('id'), str) and isinstance(d.get('title'), str)]


def parse_items(data):
    if not isinstance(data, list):
        return None
    return [t for t in map(_task, data) if t]


def _task(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get('id'), str):
        return None
    trigger = raw.get('locationTrigger')
    return {
        'id': raw['id'],
        'title': str(raw.get('title') or '').strip() or '(untitled)',
        'due': cli.parse_time(raw.get('dueDate')),
        'all_day': raw.get('dueDateIsAllDay') is True,
        'list': raw.get('listID'),
        'list_name': str(raw.get('listName') or '').strip(),
        'notes': str(raw.get('notes') or '').strip(),
        'place': str(trigger.get('address') or '').strip() if isinstance(trigger, dict) else '',
        'done': raw.get('isCompleted') is True,
    }
