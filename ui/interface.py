from core import system
from ui.haptic import Holocron
import sys
import time
import os
import re
import shutil
import textwrap
import threading
import unicodedata
from colorama.ansitowin32 import StreamWrapper

if not system.IS_WINDOWS:
    try:
        import readline  # noqa: F401
    except ImportError:
        pass


def dim(text):
    return f"\033[2m{text}\033[0m"


def red(text):
    return f"\033[38;5;131m{text}\033[0m"


def bold(text):
    return f"\033[1m{text}\033[0m"

def num(i, digits=1):
    return f'  {dim(str(i).rjust(digits))} '


def underline(text):
    return f'\033[4m{text}\033[24m'




def hyperlink(url, text):
    return f'\033]8;;{url}\033\\{text}\033]8;;\033\\'


_ESC = re.compile(r'(\033\[[\d;]*m|\033\]8;;[^\033]*\033\\)')


def visible(text):
    return _ESC.sub('', text)


def _cells(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)


def clip(text, width):
    if _cells(visible(text)) <= width:
        return text
    out, used = [], 1
    for i, part in enumerate(_ESC.split(text)):
        if i % 2:
            out.append(part)
            continue
        for c in part:
            used += _cells(c)
            if used > width:
                return ''.join(out) + '…\033[0m'
            out.append(c)
    return ''.join(out)


class Home(BaseException):
    pass


def clear_screen():
    if system.IS_WINDOWS:
        os.system('cls')
    else:
        print('\033[H\033[2J\033[3J', end='')


def haptic(sequence):
    if not system.IS_MACOS:
        return
    try:
        with Holocron() as core:
            core.invoke(sequence)
    except (SystemExit, Exception):
        pass


def error_haptic():
    haptic('error')


def pause(feedback='success'):
    print()
    key = 'return' if system.IS_MACOS else 'Enter'
    input(dim(f'Press {key} to continue...'))
    if feedback:
        haptic(feedback)


def error(text):
    clear_screen()
    print(dim(text))
    error_haptic()
    pause(feedback=None)


_SPIN = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
SPIN_DELAY = 0.15
BAR = 20


def _cursor(visible):
    if not isinstance(sys.stdout, StreamWrapper):
        sys.stdout.write('\033[?25h' if visible else '\033[?25l')


class Spinner:
    def __init__(self, label=''):
        self.label = label
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        if sys.stdout.isatty():
            self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join()
        return False

    def _run(self):
        if self._stop.wait(SPIN_DELAY):
            return
        _cursor(False)
        i = 0
        while not self._stop.is_set():
            width = shutil.get_terminal_size().columns - 1
            line = f'  {_SPIN[i % len(_SPIN)]} {self.label}'
            sys.stdout.write('\r\033[2K' + dim(line[:width]))
            sys.stdout.flush()
            i += 1
            self._stop.wait(0.08)
        sys.stdout.write('\r\033[2K')
        _cursor(True)
        sys.stdout.flush()


def wait(text, fn, *args):
    with Spinner(text):
        return fn(*args)


def progress(label, done, total, note=''):
    filled = BAR * min(done, total) // total if total else 0
    line = f'  {label}  {"•" * filled}{"·" * (BAR - filled)}  {note}'.rstrip()
    width = shutil.get_terminal_size().columns - 1
    sys.stdout.write('\r\033[2K' + dim(line[:width]))
    sys.stdout.flush()


def clear_line():
    sys.stdout.write('\r\033[2K')
    sys.stdout.flush()


def disconnect():
    clear_screen()
    if sys.stdout.isatty():
        for frame in _SPIN[:4]:
            sys.stdout.write(f'\r\033[2K  {dim(frame + " Disconnecting from the archives")}')
            sys.stdout.flush()
            time.sleep(0.12)
    clear_screen()


def quit_app():
    disconnect()
    sys.exit(0)


def screen_rows(text):
    cols = max(shutil.get_terminal_size().columns, 1)
    return max(_cells(visible(text)) - 1, 0) // cols + 1


def fill(text, width, indent=''):
    rows = textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent,
                         break_long_words=False, break_on_hyphens=False).split('\n')
    return '\n'.join(row[len(indent):] if _cells(row) > width else row for row in rows)


def one_line(text):
    return ' '.join(ln.strip() for ln in text.splitlines() if ln.strip())


def _keep_lines(text):
    return '\n'.join(ln.rstrip() for ln in text.splitlines()).strip()


def input_block(prompt, text):
    pad = ' ' * _cells(visible(prompt))
    return prompt + ('\n' + pad).join(text.split('\n'))


def input_rows(prompt, text):
    return sum(screen_rows(row) for row in input_block(prompt, text).split('\n'))


def _drain_tty():
    import select
    import termios
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    raw = termios.tcgetattr(fd)
    raw[3] &= ~(termios.ICANON | termios.ECHO)
    termios.tcsetattr(fd, termios.TCSANOW, raw)
    data = b''
    try:
        while select.select([fd], [], [], 0.05)[0]:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data += chunk
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, old)
    return data.decode('utf-8', 'replace')


def _drain_pipe():
    import select
    lines = []
    while select.select([sys.stdin], [], [], 0.05)[0]:
        line = sys.stdin.readline()
        if not line:
            break
        lines.append(line)
    return ''.join(lines)


def _drain_console():
    import msvcrt
    chars = []
    deadline = time.monotonic() + 0.05
    while time.monotonic() < deadline:
        if msvcrt.kbhit():
            chars.append(msvcrt.getwch())
            deadline = time.monotonic() + 0.05
        else:
            time.sleep(0.005)
    return ''.join(chars).replace('\r', '\n')


def _drain():
    if system.IS_WINDOWS:
        return _drain_console() if sys.stdin.isatty() else ''
    return _drain_tty() if sys.stdin.isatty() else _drain_pipe()


def _echo(prompt, first, line):
    if not sys.stdout.isatty():
        return
    sys.stdout.write(f'\033[{input_rows(prompt, first)}A\r\033[J{input_block(prompt, line)}\n')
    sys.stdout.flush()


def read_command(prompt='> ', lines=False):
    try:
        first = input(prompt)
    except EOFError:
        quit_app()
    line = (_keep_lines if lines else one_line)(f'{first}\n{_drain()}')
    if line != first.strip():
        _echo(prompt, first, line)
    if line.lower() in ('q', 'quit', 'exit'):
        quit_app()
    if line.lower() == 'w':
        raise Home
    return line


def is_back(command):
    return command.strip().lower() in ('b', 'back')


def confirm(question):
    return read_command(f'{question} [y/N] ').lower() == 'y'



def show_menu(breadcrumb, options, footer='  [number] open section   [b] back   [q] quit'):
    clear_screen()
    print(dim(breadcrumb))
    print()
    digits = len(str(len(options)))
    for i, item in enumerate(options, 1):
        print(f'{num(i, digits)}{item}')
    print()
    print(dim(footer))
    print()


def nav_line(items, width=None):
    width = width or shutil.get_terminal_size().columns - 1
    items = [item if len(item) == 4 else (*item, *item) for item in items]
    full = '  ' + '   '.join(f'[{key}] {word}' for key, word, _, _ in items)
    if len(full) <= width:
        return full
    short = '  ' + ' · '.join(f'{key_s} {word_s}' for _, _, key_s, word_s in items)
    if len(short) <= width:
        return short
    return '  ' + ' '.join(key_s for _, _, key_s, _ in items)
