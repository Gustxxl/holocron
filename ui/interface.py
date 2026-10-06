from core.os_info import user_os
from ui.haptic import Holocron
import sys
import time
import subprocess
import platform
import os

if os.name != 'nt':
    try:
        import readline
    except ImportError:
        pass


def dim(text):
    return f"\033[2m{text}\033[0m"


def red(text):
    return f"\033[38;5;131m{text}\033[0m"


def bold(text):
    return f"\033[1m{text}\033[0m"


def clear_screen():
    if os.name == 'nt':
        os.system('cls')
    else:
        print('\033[H\033[2J\033[3J', end='')


def haptic(sequence):
    if user_os() != 'macOS':
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
    key = 'return' if user_os() == 'macOS' else 'Enter'
    input(dim(f'Press {key} to continue...'))
    if feedback:
        haptic(feedback)


def error(text):
    clear_screen()
    print(dim(text))
    error_haptic()
    pause(feedback=None)


def disconnect():
    clear_screen()
    msg = "Disconnecting from the archives"
    sys.stdout.write(msg)
    sys.stdout.flush()
    for _ in range(3):
        time.sleep(0.12)
        sys.stdout.write(".")
        sys.stdout.flush()
    time.sleep(0.12)
    clear_screen()


def quit_app():
    disconnect()
    sys.exit(0)


def _join(text):
    return ' '.join(ln.strip() for ln in text.splitlines() if ln.strip())


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
    return _join(data.decode('utf-8', 'replace'))


def _drain_pipe():
    import select
    lines = []
    while select.select([sys.stdin], [], [], 0.05)[0]:
        line = sys.stdin.readline()
        if not line:
            break
        lines.append(line)
    return _join(''.join(lines))


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
    return _join(''.join(chars).replace('\r', '\n'))


def _drain():
    if os.name == 'nt':
        return _drain_console() if sys.stdin.isatty() else ''
    return _drain_tty() if sys.stdin.isatty() else _drain_pipe()


def read_command(prompt='> '):
    try:
        line = input(prompt).strip()
    except EOFError:
        quit_app()
    extra = _drain()
    if extra:
        line = f'{line} {extra}'.strip()
    if line.lower() in ('q', 'quit', 'exit'):
        quit_app()
    return line


def is_back(command):
    return command.strip().lower() in ('b', 'back')


def confirm(question):
    return read_command(f'{question} [y/N] ').lower() == 'y'


def show_menu(breadcrumb, options, footer='  [number] open section   [b] back   [q] quit'):
    clear_screen()
    print(dim(breadcrumb))
    print()
    for i, item in enumerate(options, 1):
        print(f'{i}) {item}')
    print()
    print(dim(footer))
    print()


def open_file(filepath):
    system = platform.system()
    if system == 'Darwin':
        subprocess.Popen(['open', filepath])
    elif system == 'Windows':
        subprocess.Popen(['start', '', filepath], shell=True)
    else:
        subprocess.Popen(['xdg-open', filepath])
