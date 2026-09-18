from core.settings import operator_name, update_operator_name
from ui.interface import clear_screen, dim, pause


def settings_screen():
    while True:
        print(f'\033[2mSettings\033[0m')
        print()
        items = ['User', '...', '...']
        for i, item in enumerate(items, start=1):
            print(f'{i}. {item}')
        print()
        command = input('settings> ')
        if command == '1':
            clear_screen()
            print(f'\033[2mSettings > User\033[0m')
            print()
            print(f'Current name: {operator_name()}')
            print()
            chapter = input('Change name? [y/n]> ')
            print()
            if chapter == 'y':
                ask_new_name()
                print()
                pause()
                clear_screen()
                continue
            elif chapter == 'b':
                return
            else:
                clear_screen()
                continue
        elif command == '2':
            clear_screen()
            print()
            continue
        elif command == '3':
            clear_screen()
            print()
            continue
        elif command == 'b':
            return
        else:
            ...


def ask_new_name():
    new_name = input('Enter new name: ')
    update_operator_name(new_name)
