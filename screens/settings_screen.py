from core.settings import (
    operator_name,
    update_operator_name,
    archive_path,
    update_archive_path,
)
from core import archive
from ui.interface import clear_screen, dim, pause, read_command, show_menu


def settings_screen():
    while True:
        show_menu('Settings', ['User', 'Archive', '...'])
        command = read_command('settings> ')
        if command == '1':
            user_screen()
        elif command == '2':
            archive_screen()
        elif command == 'b':
            return


def archive_screen():
    while True:
        show_menu('Settings > Archive',
                  ['Excalidraw for Obsidian', 'Excalidraw       (Soon)', 'Vault            (Soon)'])
        command = read_command('settings> ')
        if command == '1':
            excalidraw_screen()
        elif command == 'b':
            return


def user_screen():
    while True:
        clear_screen()
        print(dim('Settings > User'))
        print()
        print(f'Current name: {operator_name()}')
        print()
        print(dim('  [y] change name   [b] back   [q] quit'))
        print()
        command = read_command('Change name? [y/n]> ')
        if command == 'y':
            ask_new_name()
            pause()
        else:
            return


def excalidraw_screen():
    while True:
        clear_screen()
        print(dim('Settings > Archive > Excalidraw'))
        print()
        print(f'Current path: {archive_path() or "(not set)"}')
        print()
        print(dim('  [enter path] set path   [b] back   [q] quit'))
        print()
        command = read_command('path> ')
        if command == 'b':
            return
        else:
            update_archive_path(command)
            archive.load()
            pause()
            return


def ask_new_name():
    update_operator_name(input("New name: ").strip())
