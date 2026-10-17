import os
import platform
import subprocess
from collections import deque
from core import system
from . import cli

BREW_URL = 'https://brew.sh'
UPDATE_URL = 'x-apple.systempreferences:com.apple.Software-Update-Settings.extension'
_CLT = 'Command Line Tools'

_TERMINALS = {'Apple_Terminal': 'Terminal', 'iTerm.app': 'iTerm', 'ghostty': 'Ghostty',
              'WezTerm': 'WezTerm', 'vscode': 'VS Code', 'WarpTerminal': 'Warp'}


def supported():
    return system.IS_MACOS


def status(program, version, authorized):
    major = platform.mac_ver()[0].split('.')[0]
    if not (major.isdigit() and int(major) >= version):
        return 'old_macos'
    if not cli.available(program):
        return 'missing' if cli.available('brew') else 'no_brew'
    return 'ready' if authorized() else 'denied'


def terminal():
    return _TERMINALS.get(os.environ.get('TERM_PROGRAM', ''), 'your terminal app')


def install(formula):
    try:
        proc = subprocess.Popen([cli.which('brew'), 'install', formula], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, errors='replace')
        tail = deque(maxlen=50)
        for line in proc.stdout:
            print(line, end='', flush=True)
            tail.append(line)
        code = proc.wait()
    except KeyboardInterrupt:
        return 'failed'
    if code == 0:
        return 'ok'
    return 'clt' if _CLT in ''.join(tail) else 'failed'


def open_url(url):
    subprocess.call(['open', url])
