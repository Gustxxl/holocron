import os
import platform
import subprocess
from core import system
from . import cli

BREW_URL = 'https://brew.sh'

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
        return subprocess.call([cli.which('brew'), 'install', formula]) == 0
    except KeyboardInterrupt:
        return False


def open_url(url):
    subprocess.call(['open', url])
