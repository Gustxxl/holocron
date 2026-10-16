import os
import platform
import subprocess
from core import system
from . import cli

NAME = 'Reminders'
KEY = 'remindctl'
KIND = 'tasks'
PROGRAM = 'remindctl'
TAP = 'steipete/tap/remindctl'
HINT = 'No access to Reminders. Open settings (s) > Reminders'
PRIVACY_URL = 'x-apple.systempreferences:com.apple.preference.security?Privacy_Reminders'

_TERMINALS = {'Apple_Terminal': 'Terminal', 'iTerm.app': 'iTerm', 'ghostty': 'Ghostty',
              'WezTerm': 'WezTerm', 'vscode': 'VS Code', 'WarpTerminal': 'Warp'}


def supported():
    return system.IS_MACOS


def _new_macos():
    major = platform.mac_ver()[0].split('.')[0]
    return major.isdigit() and int(major) >= 14


def status():
    if not _new_macos():
        return 'old_macos'
    if not cli.available(PROGRAM):
        return 'missing' if cli.available('brew') else 'no_brew'
    return 'ready' if authorized() else 'denied'


def terminal():
    return _TERMINALS.get(os.environ.get('TERM_PROGRAM', ''), 'your terminal app')


def install():
    try:
        return subprocess.call([cli.which('brew'), 'install', TAP]) == 0
    except KeyboardInterrupt:
        return False


def authorize():
    cli.run_ok(PROGRAM, 'authorize', timeout=120)
    return authorized()


def open_privacy():
    subprocess.call(['open', PRIVACY_URL])


def open_brew_site():
    subprocess.call(['open', 'https://brew.sh'])


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
