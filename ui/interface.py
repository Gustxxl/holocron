from core.os_info import user_os
from ui.haptic import Holocron, emit
import sys
import time


def dim(text):
    return f"\033[2m{text}\033[0m"


def clear_screen():
    print('\033[H\033[2J', end='')


def pause():
    if user_os() == 'macOS':
        print()
        input(dim('Press return to continue...'))
        with Holocron() as core:
            core.success()
    else:
        print()
        input(dim('Press Enter to continue...'))


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
    command = input(prompt).strip()
    if command.lower() in ('q', 'quit', 'exit'):
        quit_app()
    return command


def show_menu(breadcrumb, options, footer='  [number] open section   [b] back   [q] quit'):
    clear_screen()
    print(dim(breadcrumb))
    print()
    for i, item in enumerate(options, 1):
        print(f'{i}) {item}')
    print()
    print(dim(footer))
    print()


def error_haptic():
    if user_os() == 'macOS':
        with Holocron() as core:
            core.error()
