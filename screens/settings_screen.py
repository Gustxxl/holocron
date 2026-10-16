from core.settings import (
    operator_name,
    update_operator_name,
    archive_path,
    update_archive_path,
    excalidraw_path,
    update_excalidraw_path,
    vault_path,
    update_vault_path,
    new_cases_path,
    update_new_cases_path,
    keeper_server,
    keeper_model,
    update_keeper_server,
    update_keeper_model,
    vault_exclude,
    update_vault_exclude
)
from core import archives, keeper
from screens.schedule_settings_screen import schedule_settings
from ui.interface import clear_screen, dim, error, pause, read_command, red, show_menu
from pathlib import Path
from ui.clean_path import clean_input_path
from core import system
from core.sources import remindctl
from screens.tasks_screen import lists_screen
import sys
from core.archives.vault import folders, relative


_SOURCES = [remindctl]

_SOURCE_STATUS = {
    'old_macos': 'needs macOS 14',
    'no_brew': 'needs Homebrew',
    'missing': 'not installed',
    'denied': 'no access',
}

_STEPS = ['old_macos', 'no_brew', 'missing', 'denied']
_STEP_NAMES = ['macOS 14 or later', 'Homebrew', 'remindctl', 'Access to Reminders']


def settings_screen():
    while True:
        extra = [s for s in _SOURCES if s.supported()]
        labels = [_source_label(s) for s in extra]
        show_menu('Settings', ['User', 'Archive', 'Schedule', *labels])
        command = read_command('settings> ')
        if command == '1':
            user_screen()
        elif command == '2':
            archive_screen()
        elif command == '3':
            schedule_settings()
        elif command.isdigit() and 4 <= int(command) < 4 + len(extra):
            source = extra[int(command) - 4]
            if source_setup(source):
                lists_screen(source)
        elif command == 'b':
            return


def _source_label(source):
    note = _SOURCE_STATUS.get(source.status())
    return f'{source.NAME}   {dim(note)}' if note else source.NAME


def source_setup(source):
    while True:
        state = source.status()
        if state == 'ready':
            return True
        current = _STEPS.index(state)
        clear_screen()
        print(dim(f'Settings > {source.NAME}'))
        print()
        print('  Holocron shows and adds Apple Reminders through remindctl,')
        print('  a free command-line tool.')
        print()
        for i, name in enumerate(_STEP_NAMES):
            mark = dim('✓') if i < current else '→' if i == current else dim('·')
            print(f'  {mark} {name}' if i <= current else dim(f'  · {name}'))
        print()

        nav = []
        if state == 'old_macos':
            print('  Reminders need macOS 14 Sonoma or later.')
            print(dim(f'  This Mac runs macOS {platform.mac_ver()[0] or "unknown"}.'))
        elif state == 'no_brew':
            print('  remindctl installs with Homebrew, a package manager for macOS.')
            print('  Open brew.sh, copy the install command into a terminal,')
            print('  then come back and press Enter.')
            nav.append(('o', 'open brew.sh', 'o', 'brew.sh'))
        elif state == 'missing':
            print('  Install remindctl with Homebrew:')
            print(dim(f'  brew install {source.TAP}'))
            nav.append(('i', 'install now', 'i', 'install'))
        elif state == 'denied':
            app = source.terminal()
            print(f'  macOS asks once whether {app} may use Reminders.')
            print(f'  If the request does not appear, turn on {app} in')
            print('  System Settings > Privacy & Security > Reminders,')
            print(f'  then quit and reopen {app}.')
            nav += [('a', 'ask for access', 'a', 'access'), ('o', 'open System Settings', 'o', 'settings')]
        print()
        nav += [('↵', 'check again', '↵', 'check'), ('b', 'back')]
        print(dim(nav_line(nav)))
        print()

        command = read_command(f'{source.NAME.lower()}> ').lower()
        if command == 'b':
            return False
        if command == 'o' and state == 'no_brew':
            source.open_brew_site()
        elif command == 'i' and state == 'missing':
            print()
            ok = source.install()
            print()
            print('Installed.' if ok else 'Installation did not finish. See the output above.')
            pause(feedback=None if ok else 'error')
        elif command == 'a' and state == 'denied':
            if not source.authorize():
                error(f'Still no access. Turn on {source.terminal()} in System Settings.')
        elif command == 'o' and state == 'denied':
            source.open_privacy()


def _mark(path):
    if not path:
        return dim('—')
    return dim('✓') if Path(path).exists() else red('not found')


def archive_screen():
    while True:
        clear_screen()
        print(dim('Settings > Archive'))
        print()
        p1 = archive_path()
        p2 = excalidraw_path()
        p3 = vault_path()
        p4 = keeper_model('server') or keeper_model('local')
        p5 = new_cases_path()
        print(f'1) Excalidraw for Obsidian   {_mark(p1)}')
        print(f'2) Excalidraw                {_mark(p2)}')
        print(f'3) Vault                     {_mark(p3)}')
        print(f'4) Keeper                    {dim("✓") if p4 else dim("—")}')
        print(f'5) Notes                     {_mark(p5)}')
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
        elif command == '5':
            notes_screen()
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


def _print_path(p):
    if p and not Path(p).exists():
        print(f'Current path: {p}')
        print(dim('  (path not found)'))
    elif p:
        print(f'Current path: {p}')
    else:
        print('Current path: (not set)')


def excalidraw_obsidian_screen():
    while True:
        clear_screen()
        print(dim('Settings > Archive > Excalidraw for Obsidian'))
        print()
        _print_path(archive_path())
        print()
        print(dim('  [enter path] set path   [b] back   [q] quit'))
        print()
        command = read_command('path> ')
        if command == 'b':
            return
        cleaned = clean_input_path(command)
        if Path(cleaned).suffix.lower() != '.md' or not Path(cleaned).is_file():
            error('Path must point to an existing .md file.')
            continue
        update_archive_path(cleaned)
        archives.load()
        pause()
        return


def excalidraw_plain_screen():
    while True:
        clear_screen()
        print(dim('Settings > Archive > Excalidraw'))
        print()
        _print_path(excalidraw_path())
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
        cp = Path(clean_input_path(command))
        if not (cp.is_dir() or (cp.is_file() and cp.suffix == '.excalidraw')):
            error('Path must be a folder or an .excalidraw file.')
            continue
        update_excalidraw_path(str(cp))
        archives.load()
        pause()
        return


def _folder_screen(title, current, update, hint):
    while True:
        clear_screen()
        print(dim(f'Settings > Archive > {title}'))
        print()
        _print_path(current())
        print()
        print(dim(f'  [enter path] {hint}   [c] clear   [b] back'))
        print()
        command = read_command('path> ')
        if command == 'b':
            return
        if command == 'c':
            update('')
        else:
            cleaned = clean_input_path(command)
            if not Path(cleaned).is_dir():
                error('Path must be an existing folder.')
                continue
            update(cleaned)
        archives.load()
        pause()
        return


def vault_screen():
    while True:
        current, skip = vault_path(), vault_exclude()
        rows = folders(current, skip, archives.cases()) if current else []
        clear_screen()
        print(dim('Settings > Archive > Vault'))
        print()
        _print_path(current)
        if rows:
            print()
            digits = len(str(len(rows)))
            col = max(len(n) for n, _ in rows)
            for i, (name, count) in enumerate(rows, 1):
                info = dim('excluded') if count is None else dim(str(count)) if count else ''
                print(f'  {dim(str(i).rjust(digits))} {name.ljust(col)}   {info}'.rstrip())
        print()
        nav = '  [number] exclude / include   [a] exclude folder   ' if current else '  '
        print(dim(nav + '[enter path] set vault folder   [c] clear   [b] back'))
        print()
        command = read_command('path> ')
        if command == 'b':
            return
        if command == '':
            continue
        if command.isdigit() and 1 <= int(command) <= len(rows):
            name = rows[int(command) - 1][0]
            update_vault_exclude([p for p in skip if p != name] if name in skip else [*skip, name])
            archives.load()
            continue
        if command == 'a' and current:
            raw = read_command('folder> ')
            if not raw:
                continue
            rel = relative(clean_input_path(raw))
            if rel is None:
                error('Folder must be inside the vault.')
                continue
            if rel not in skip:
                update_vault_exclude([*skip, rel])
                archives.load()
            continue
        if command == 'c':
            update_vault_path('')
        else:
            cleaned = clean_input_path(command)
            if not Path(cleaned).is_dir():
                error('Path must be an existing folder.')
                continue
            update_vault_path(cleaned)
        archives.load()
        pause()
        return


def notes_screen():
    _folder_screen('Notes', new_cases_path, update_new_cases_path, 'set folder for new notes')


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
    if system.OS == 'Linux':
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
        pause()
    except keeper.KeeperOffline as e:
        print('\n')
        print(f'Download failed: {e}')
        pause(feedback='error')
    except KeyboardInterrupt:
        print('\n')
        print('Cancelled.')
        pause(feedback=None)


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
