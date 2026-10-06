from core.os_info import user_os
from ui.haptic import Holocron
import sys
import time
import subprocess
import platform
import os


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


def read_command(prompt='> '):
    try:
        line = input(prompt).strip()
    except EOFError:
        quit_app()
    if os.name != 'nt':
        import select
        while select.select([sys.stdin], [], [], 0.05)[0]:
            extra = sys.stdin.readline().strip()
            if extra:
                line += ' ' + extra
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
