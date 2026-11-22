import os
import re
import shlex
import sys
import time
from pathlib import Path
from core import config, sources, system
from . import cli, macos

NAME = 'Menu bar'
KEY = 'swiftbar'
KIND = 'bar'
SETUP = 'swiftbar'
APP = 'SwiftBar'
TAP = 'swiftbar'
MACOS = 12
DOMAIN = 'com.ameba.SwiftBar'
RELEASES = 'https://github.com/swiftbar/SwiftBar/releases'
FILE = 'holocron.1m.sh'
HOME = '~/SwiftBar'
APPS = ('/Applications', '~/Applications')
MAIN = str(Path(config.APP_DIR) / 'main.py')
_TAGS = ('refreshOnOpen', 'hideAbout', 'hideRunInTerminal', 'hideLastUpdated')
_LEFTOVERS = ('.DS_Store', f'.{FILE}.tmp')
_RUNNING = f'application id "{DOMAIN}" is running'
_WAIT = 15
ICON = '◇'
DUTY = '●'
HEAD = 12
RED = '#af5f5f'
LENGTH = 40
_PLAIN = 'symbolize=false emojize=false'
_ID = re.compile(r'[\w:/.-]+')
_ASK = ('on run argv', 'activate',
        'set found to display dialog (item 1 of argv) default answer (item 2 of argv) '
        'with title "Holocron" giving up after 120',
        'if gave up of found then return ""', 'return text returned of found', 'end run')
_ASK_WAIT = 130

supported = macos.supported


def status():
    if macos.outdated(MACOS):
        return 'old_macos'
    if app() is None:
        return 'missing'
    if folder() is None:
        return 'no_folder'
    return 'ready' if added() else 'off'


def available():
    return system.IS_MACOS and added()


def app():
    found = (Path(p).expanduser() / f'{APP}.app' for p in APPS)
    return next((p for p in found if p.is_dir()), None)


def folder():
    out = system.run(['defaults', 'read', DOMAIN, 'PluginDirectory'], timeout=cli.TIMEOUT)
    text = out.stdout.strip() if out and out.returncode == 0 else ''
    path = Path(text).expanduser() if text else None
    return path if path and path.is_dir() else None


def plugin():
    found = folder()
    return found / FILE if found else None


def script():
    tags = [f'# <swiftbar.{t}>true</swiftbar.{t}>' for t in _TAGS]
    return '\n'.join(['#!/bin/sh', *tags, f'exec {shlex.join([sys.executable, MAIN, "--bar"])}', ''])


def added():
    path = plugin()
    try:
        return path is not None and path.read_text(encoding='utf-8') == script()
    except OSError:
        return False


def owned():
    path = folder()
    mine = sources.text(KEY, 'folder')
    if path is None or not mine or path != Path(mine):
        return False
    try:
        return {p.name for p in path.iterdir()} <= {FILE, *_LEFTOVERS}
    except OSError:
        return False


def running():
    out = system.run(['osascript', '-e', f'return {_RUNNING}'], timeout=cli.TIMEOUT)
    return out is not None and out.stdout.strip() == 'true'


def stop():
    system.run(['osascript', '-e', f'if {_RUNNING} then tell application id "{DOMAIN}" to quit'],
               timeout=cli.TIMEOUT)
    for _ in range(_WAIT):
        if not running():
            return True
        time.sleep(0.2)
    return False


def create():
    path = Path(HOME).expanduser()
    if not stop():
        return 'running'
    made = not path.exists()
    try:
        path.mkdir(exist_ok=True)
    except OSError:
        return 'failed'
    if not _defaults('write', DOMAIN, 'PluginDirectory', str(path)):
        return 'failed'
    if made:
        sources.set_option(KEY, 'folder', str(path))
    macos.open_url(str(app()))
    return 'ok'


def add():
    path = plugin()
    if path is None:
        return False
    tmp = path.with_name(f'.{FILE}.tmp')
    try:
        tmp.write_text(script(), encoding='utf-8')
        tmp.chmod(0o755)
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        return False
    return True


def remove():
    path = plugin()
    if path is None:
        return False
    tidy = owned()
    if tidy and not stop():
        return False
    try:
        path.unlink(missing_ok=True)
        if tidy:
            for name in _LEFTOVERS:
                (path.parent / name).unlink(missing_ok=True)
            path.parent.rmdir()
    except OSError:
        return False
    if tidy:
        _defaults('delete', DOMAIN, 'PluginDirectory')
        sources.set_option(KEY, 'folder', '')
    return True


def start():
    if status() != 'ready' or running():
        return False
    system.run(['open', '-g', str(app())], timeout=cli.TIMEOUT)
    return True


def finish(opened):
    if opened or owned():
        stop()


def ask(prompt, text=''):
    script = [part for line in _ASK for part in ('-e', line)]
    out = system.run(['osascript', *script, prompt, text], timeout=_ASK_WAIT)
    return out.stdout.strip() if out and out.returncode == 0 else ''


def render(on, title, alert, duty, groups, add=False):
    lines = [_line(f'{DUTY if on else ICON} {title}', alert, f'length={LENGTH}')]
    if duty:
        lines += ['---', _line(duty)]
    if groups:
        lines.append('---')
    for head, rows in groups:
        if head:
            lines.append(_line(head, extra=f'size={HEAD}'))
        lines += [_row(*row) for row in rows]
    if add:
        lines += ['---', _line('+ New reminder', extra=_run('--new'))]
    return '\n'.join(lines)


def _row(text, late, action):
    if action is None or not _ID.fullmatch(action[1]):
        return _line(text, late)
    kind, task_id = action
    return _line(text, late, _run(f'--{kind}', task_id))


def _run(*args):
    params = ' '.join(f'param{i}={arg}' for i, arg in enumerate(args, 2))
    return f'bash="{sys.executable}" param1="{MAIN}" {params} terminal=false refresh=true'


def _line(text, alert=False, extra=''):
    params = [extra, _PLAIN, f'color={RED}' if alert else '']
    return f'{_clean(text)} | {" ".join(p for p in params if p)}'


def _clean(text):
    return ' '.join(text.replace('|', '¦').split()).lstrip('-').lstrip()


def _defaults(*args):
    out = system.run(['defaults', *args], timeout=cli.TIMEOUT)
    return out is not None and out.returncode == 0
