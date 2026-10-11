import importlib.util
import os
import platform
import shlex
import shutil
import subprocess

OS = {'Darwin': 'macOS'}.get(platform.system(), platform.system())
IS_MACOS = OS == 'macOS'
IS_WINDOWS = os.name == 'nt'
CURSES = importlib.util.find_spec('_curses') is not None
EDITORS = ('notepad',) if IS_WINDOWS else ('nano', 'vim', 'vi')
CLIPBOARDS = (('pbcopy',), ('clip',), ('wl-copy',), ('xclip', '-selection', 'clipboard'),
              ('xsel', '--clipboard', '--input'))


def version():
    return platform.mac_ver()[0] if IS_MACOS else platform.release()


def command(line):
    try:
        parts = [p.strip('"') for p in shlex.split(line, posix=not IS_WINDOWS)]
    except ValueError:
        return None
    path = shutil.which(parts[0]) if parts else None
    return [path, *parts[1:]] if path else None


def editor():
    for line in (os.environ.get('VISUAL'), os.environ.get('EDITOR'), *EDITORS):
        cmd = command(line) if line else None
        if cmd:
            return cmd
    return None


def run(args, timeout=None, input=None):
    try:
        return subprocess.run(args, input=input, capture_output=True,
                              text=not isinstance(input, bytes), timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def attach(args):
    try:
        return subprocess.call(args) == 0
    except OSError:
        return False


def copy_text(text):
    for name, *args in CLIPBOARDS:
        path = shutil.which(name)
        if not path:
            continue
        out = run([path, *args], timeout=5, input=text.encode('utf-16' if name == 'clip' else 'utf-8'))
        if out and out.returncode == 0:
            return True
    return False


def open_file(path):
    if IS_WINDOWS:
        try:
            os.startfile(path)
            return True
        except OSError:
            return False
    opener = shutil.which('open' if IS_MACOS else 'xdg-open')
    if not opener:
        return False
    try:
        subprocess. Popen([opener, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False
