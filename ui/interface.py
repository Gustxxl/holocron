from core.os_info import user_os
from core.haptic import Holocron, emit


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
