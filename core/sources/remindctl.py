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
    return {
        'id': raw['id'],
        'title': str(raw.get('title') or '').strip() or '(untitled)',
        'due': cli.parse_time(raw.get('dueDate')),
        'all_day': raw.get('dueDateIsAllDay') is True,
        'list': raw.get('listID'),
        'list_name': str(raw.get('listName') or '').strip(),
        'done': raw.get('isCompleted') is True,
    }
