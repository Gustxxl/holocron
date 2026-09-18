from core.os_info import user_os


def dim(text):
    return f"\033[2m{text}\033[0m"


def clear_screen():
    print('\033[H\033[2J', end='')


def pause():
    current_os = user_os()
    if current_os == 'macOS':
        print()
        input(dim('Press return to continue...'))
    else:
        print()
        input(dim('Press Enter to continue...'))
