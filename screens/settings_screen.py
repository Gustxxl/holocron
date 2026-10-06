from core.settings import (
    operator_name,
    update_operator_name,
    archive_path,
    update_archive_path,
    excalidraw_path,
    update_excalidraw_path,
    vault_path,
    update_vault_path,
    keeper_server,
    keeper_model,
    update_keeper_server,
    update_keeper_model,
)
from core import archives, keeper
from ui.interface import clear_screen, dim, pause, read_command, show_menu
from pathlib import Path
from ui.clean_path import clean_input_path
import platform
import sys
import getpass


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
        clear_screen()
        print(dim('Settings > Archive'))
        print()
        p1 = archive_path()
        p2 = excalidraw_path()
        p3 = vault_path()
        p4 = keeper_model('server') or keeper_model('local')
        print(f'1) Excalidraw for Obsidian   {dim("✓") if p1 else dim("—")}')
        print(f'2) Excalidraw                {dim("✓") if p2 else dim("—")}')
        print(f'3) Vault                     {dim("✓") if p3 else dim("—")}')
        print(f'4) Keeper                    {dim("✓") if p4 else dim("—")}')
        print()
        print(dim('  [number] open section   [b] back   [q] quit'))
        print()
        command = read_command('settings> ')
        if command == '1':
            excalidraw_obsidian_screen()
        elif command == '2':
            excalidraw_plain_screen()
        elif command == '3':
            vault_screen()
        elif command == '4':
            keeper_screen()
        elif command == 'b':
            return


def user_screen():
    while True:
        clear_screen()
        print(dim('Settings > User'))
        print()
        name = operator_name() or '(not set)'
        print(f'Name: {name}')
        print()
        print(dim('  [type] new name   [c] clear   [b] back'))
        print()
        command = read_command('name> ')
        if command == 'b':
            return
        if command == 'c':
            update_operator_name('')
            continue
        if command:
            update_operator_name(command)
            continue


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


def vault_screen():
    while True:
        clear_screen()
        print(dim('Settings > Archive > Vault'))
        print()
        p = vault_path()
        if p and not Path(p).exists():
            print(f'Current path: {p}')
            print(dim('  (path not found)'))
        elif p:
            print(f'Current path: {p}')
        else:
            print('Current path: (not set)')
        print()
        print(dim('  [enter path] set vault folder   [c] clear   [b] back'))
        print()
        command = read_command('path> ')
        if command == 'b':
            return
        if command == 'c':
            update_vault_path('')
            archives.load()
            pause()
            return
        cleaned = clean_input_path(command)
        if not Path(cleaned).is_dir():
            clear_screen()
            print(dim('Path must be an existing folder.'))
            pause()
            continue
        update_vault_path(cleaned)
        archives.load()
        pause()
        return


_KEEPER_STATUS = {
    'missing': 'Ollama not installed',
    'stopped': 'Ollama not running',
    'off': 'off',
    'no_models': 'no models',
    'no_model': 'choose a model',
    'model_missing': 'model removed',
    'ready': 'online',
}

_KEEPER_NAMES = {'server': 'Server', 'local': 'This computer'}


def _keeper_install_hint():
    if platform.system() == 'Linux':
        return 'Install: curl -fsSL https://ollama.com/install.sh | sh'
    return 'Download: https://ollama.com/download'


def _keeper_download(conn):
    clear_screen()
    print(dim(f'Settings > Archive > Keeper > {_KEEPER_NAMES[conn["slot"]]}'))
    print()
    print(f'Downloading {keeper.RECOMMENDED}...')
    print(dim('Ctrl+C to cancel'))
    print()

    def progress(status, done, total):
        if total and done:
            line = f'  {status[:30]:<30} {done * 100 // total:>3}%'
        else:
            line = f'  {status[:40]:<40}'
        sys.stdout.write('\r\033[2K' + line)
        sys.stdout.flush()

    try:
        keeper.pull(conn, keeper.RECOMMENDED, progress)
        update_keeper_model(conn['slot'], keeper.RECOMMENDED)
        print('\n')
        print('Done.')
    except keeper.KeeperOffline as e:
        print('\n')
        print(f'Download failed: {e}')
    except KeyboardInterrupt:
        print('\n')
        print('Cancelled.')
    pause()


def _keeper_models_screen(slot):
    while True:
        conn = keeper.connection(slot)
        if conn is None:
            return
        state, found = keeper.status(conn)
        clear_screen()
        print(dim(f'Settings > Archive > Keeper > {_KEEPER_NAMES[slot]}'))
        print()
        if state == 'missing':
            print('  Keeper runs on Ollama, a free app for AI models on this computer.')
            print('  ' + _keeper_install_hint())
            print('  Then open it and press Enter.')
        elif state == 'stopped':
            print('  Open the Ollama app, then press Enter.')
        elif state == 'off':
            print(f'  {conn["url"]} is not responding. Press Enter to check again.')
        elif found:
            for i, m in enumerate(found, 1):
                mark = dim('  ✓') if m == conn['model'] else ''
                print(f'  {i}) {m}{mark}')
        else:
            print('  No models yet.')
        print()

        needs_model = state in ('no_models', 'no_model', 'model_missing')
        can_download = needs_model and keeper.RECOMMENDED not in found
        nav = '  '
        nav += '[number] select   ' if found else ''
        nav += f'[d] download {keeper.RECOMMENDED}   ' if can_download else ''
        nav += '[b] back'
        print(dim(nav))
        print()

        command = read_command('model> ')
        keeper.reset()
        if command == 'b':
            return
        if command == 'd' and can_download:
            _keeper_download(conn)
        elif command.isdigit() and found and 1 <= int(command) <= len(found):
            update_keeper_model(slot, found[int(command) - 1])
            keeper.reset()
            return


def keeper_screen():
    while True:
        rows = keeper.connections()
        has_server = keeper.has_server()
        clear_screen()
        print(dim('Settings > Archive > Keeper'))
        print()
        for i, conn in enumerate(rows, 1):
            state, _ = keeper.status(conn)
            name = _KEEPER_NAMES[conn['slot']]
            model = conn['model'] or '—'
            print(f'{i}) {name:<14} {model:<20} {dim(_KEEPER_STATUS[state])}')
            if conn['slot'] == 'server':
                print(dim(f'   {conn["url"].split("://", 1)[-1]}'))
        print()
        if has_server:
            print(dim('  Keeper uses the server when it is on, otherwise this computer.'))
            print()
        address = '[a] server address' if has_server else '[a] add server'
        print(dim(f'  [number] model   {address}   [↵] check   [b] back'))
        print()

        command = read_command('Keeper> ')
        keeper.reset()
        if command == 'b':
            return
        if command == 'a':
            print(dim('  Address of a computer running Ollama, for example server-ip:11434'))
            if has_server:
                print(dim('  Enter to keep, x to remove.'))
            new = read_command('address> ')
            if new.lower() == 'x' and has_server:
                update_keeper_server('')
            elif new:
                update_keeper_server(new)
        elif command.isdigit() and 1 <= int(command) <= len(rows):
            _keeper_models_screen(rows[int(command) - 1]['slot'])
