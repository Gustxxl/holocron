import os
import stat
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
MAIN = APP_DIR / 'main.py'
NAME = 'holo'
PATH_LINE = 'export PATH="$HOME/.local/bin:$PATH"'


def _windows_target():
    return Path(os.environ['LOCALAPPDATA']) / 'Microsoft' / 'WindowsApps' / f'{NAME}.cmd'


def _posix_target():
    return Path.home() / '.local' / 'bin' / NAME


def _install_windows():
    target = _windows_target()
    target.write_text(
        f'@echo off\r\nsetlocal\r\ncd /d "{APP_DIR}"\r\n"{sys.executable}" "{MAIN}" %*\r\n',
        encoding='oem',
    )
    return target, True


def _install_posix():
    target = _posix_target()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f'#!/bin/sh\ncd "{APP_DIR}" && exec "{sys.executable}" "{MAIN}" "$@"\n',
        encoding='utf-8',
    )
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return target, str(target.parent) in os.environ.get('PATH', '').split(os.pathsep)


def _shell_rc():
    shell = os.path.basename(os.environ.get('SHELL', ''))
    if shell == 'zsh':
        return Path.home() / '.zshrc'
    if shell == 'bash':
        return Path.home() / ('.bash_profile' if sys.platform == 'darwin' else '.bashrc')
    return None


def _add_to_path():
    rc = _shell_rc()
    if rc is None:
        return False
    text = rc.read_text(encoding='utf-8') if rc.exists() else ''
    if '.local/bin' not in text:
        with rc.open('a', encoding='utf-8') as f:
            f.write(f'\n{PATH_LINE}\n')
    return True


def install():
    target, on_path = _install_windows() if os.name == 'nt' else _install_posix()
    print(f'Installed: {target}')
    if not on_path and not _add_to_path():
        print(f'Add {target.parent} to PATH, then open a new terminal and type: {NAME}')
        return
    print(f'Open a new terminal and type: {NAME}')


def remove():
    target = _windows_target() if os.name == 'nt' else _posix_target()
    if target.exists():
        target.unlink()
        print(f'Removed: {target}')
    else:
        print('Nothing to remove.')


if __name__ == '__main__':
    remove() if '--remove' in sys.argv else install()
