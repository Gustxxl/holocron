from core.settings import (
    operator_name,
    update_operator_name,
    archive_path,
    update_archive_path,
    excalidraw_path,
    update_excalidraw_path,
)
from core import archives
from ui.interface import clear_screen, dim, pause, read_command, show_menu
from pathlib import Path
from ui.clean_path import clean_input_path


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
                  ['Excalidraw for Obsidian', 'Excalidraw', 'Vault            (Soon)'])
        command = read_command('settings> ')
        if command == '1':
            excalidraw_obsidian_screen()
        elif command == '2':
            excalidraw_plain_screen()
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


def excalidraw_obsidian_screen():
    while True:
        clear_screen()
        print(dim('Settings > Archive > Excalidraw for Obsidian'))
        print()
        print(f'Current path: {archive_path() or "(not set)"}')
        print()
        print(dim('  [enter path] set path   [b] back   [q] quit'))
        print()
        command = read_command('path> ')
        if command == 'b':
            return
        cleaned = clean_input_path(command)
        if Path(cleaned).suffix.lower() != '.md' or not Path(cleaned).is_file():
            clear_screen()
            print(dim('Path must point to an existing .md file.'))
            pause()
            continue
        update_archive_path(command)
        archives.load()
        pause()
        return


def excalidraw_plain_screen():
    while True:
        clear_screen()
        print(dim('Settings > Archive > Excalidraw'))
        print()
        p = excalidraw_path()
        if p and not Path(p).exists():
            print(f'Current path: {p}')
            print(dim('  (path not found)'))
        elif p:
            print(f'Current path: {p}')
        else:
            print('Current path: (not set)')
        print()
        print(dim('  [enter path] set folder or .excalidraw file   [c] clear   [b] back'))
        print()
        command = read_command('path> ')
        if command == 'b':
            return
        if command == 'c':
            update_excalidraw_path('')
            archives.load()
            pause()
            return
        # ↓ вот этого не хватает
        cleaned = clean_input_path(command)
        cp = Path(cleaned)
        if not (cp.is_dir() or (cp.is_file() and cp.suffix == '.excalidraw')):
            clear_screen()
            print(dim('Path must be a folder or an .excalidraw file.'))
            pause()
            continue
        update_excalidraw_path(cleaned)
        archives.load()
        pause()
        return


def ask_new_name():
    update_operator_name(input("New name: ").strip())
