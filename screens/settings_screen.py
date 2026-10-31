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
    keeper_model,
    update_keeper_server,
    update_keeper_model,
    vault_exclude,
    update_vault_exclude,
    search_separator,
    update_search_separator,
    SEARCH_SEPARATOR,
    home_order,
    update_home_order,
    reorder,
    page_rows,
    update_page_rows,
    PAGE_ROWS,
    PAGE_MIN,
    PAGE_MAX
)

from core import archives, keeper
from screens.schedule_settings_screen import schedule_settings
from ui.interface import (clear_line, clear_screen, dim, error, haptic, is_back, nav_line, num, pause, progress,
                          read_command, red, show_menu, wait)
from pathlib import Path
from ui.clean_path import clean_input_path
from core import system
from core.archives.vault import folders, relative
from core.sources import registry
from screens.sources_screen import lists_screen, source_setup


def settings_screen():
    while True:
        extra = registry.supported()
        items = [('User', user_screen)]
        if extra:
            items.append(('Main screen', home_screen))
        items += [('Lists', rows_screen), ('Archive', archive_screen), ('Schedule', schedule_settings)]
        items += [(s.NAME, lambda s=s: _open_source(s)) for s in extra]
        show_menu('Settings', [name for name, _ in items])
        command = read_command('settings> ')
        if command == 'b':
            return
        if command.isdigit() and 1 <= int(command) <= len(items):
            items[int(command) - 1][1]()


def _open_source(source):
    if source_setup(source):
        lists_screen(source)


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
        p6 = search_separator()
        print(f'{num(1)}Excalidraw for Obsidian   {_mark(p1)}')
        print(f'{num(2)}Excalidraw                {_mark(p2)}')
        print(f'{num(3)}Vault                     {_mark(p3)}')
        print(f'{num(4)}Keeper                    {dim("✓") if p4 else dim("—")}')
        print(f'{num(5)}Notes                     {_mark(p5)}')
        print(f'{num(6)}Search separator          {dim(p6) if p6 else dim("off")}')
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
        elif command == '6':
            separator_screen()
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
            haptic('toggle')
            continue
        if command:
            update_operator_name(command)
            haptic('toggle')




def home_screen():
    while True:
        order = home_order()
        shown = [b for b in order if b not in registry.BLOCKS or registry.block(b)]
        clear_screen()
        print(dim('Settings > Main screen'))
        print()
        for i, key in enumerate(shown, 1):
            name = registry.block(key).NAME if key in registry.BLOCKS else 'Schedule'
            print(f'{num(i)}{name}')
        print()
        print(dim('  Type the numbers in the new order. Blocks you skip keep their order.'))
        print(dim(f'  [numbers] reorder, e.g. {len(shown)}1   [d] default   [b] back'))
        print()
        command = read_command('order> ')
        if command == 'b':
            return
        if command == 'd':
            update_home_order([])
            haptic('toggle')
            continue
        new = reorder(shown, command)
        if new:
            update_home_order([*new, *(b for b in order if b not in new)])
            haptic('toggle')
        elif command:
            error(f'Type block numbers, e.g. {len(shown)}1')


def rows_screen():
    while True:
        clear_screen()
        print(dim('Settings > Lists'))
        print()
        print(f'Rows per page: {page_rows()}')
        print(dim('  For l, tree and kanban boards'))
        print()
        print(dim(f'  [type] {PAGE_MIN} to {PAGE_MAX}   [d] default {PAGE_ROWS}   [b] back'))
        print()
        command = read_command('rows> ')
        if command == 'b':
            return
        if command == 'd':
            update_page_rows(PAGE_ROWS)
            haptic('toggle')
        elif command.isascii() and command.isdigit() and PAGE_MIN <= int(command) <= PAGE_MAX:
            update_page_rows(int(command))
            haptic('toggle')
        elif command:
            error(f'Type a number from {PAGE_MIN} to {PAGE_MAX}')


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
        pause(feedback='success')
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
            pause(feedback='success')
            return
        cp = Path(clean_input_path(command))
        if not (cp.is_dir() or (cp.is_file() and cp.suffix == '.excalidraw')):
            error('Path must be a folder or an .excalidraw file.')
            continue
        update_excalidraw_path(str(cp))
        archives.load()
        pause(feedback='success')
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
        pause(feedback='success')
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
                print(f'{num(i, digits)}{name.ljust(col)}   {info}'.rstrip())
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
            haptic('toggle')
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
                haptic('toggle')
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
        pause(feedback='success')
        return


def notes_screen():
    _folder_screen('Notes', new_cases_path, update_new_cases_path, 'set folder for new notes')


def separator_screen():
    while True:
        clear_screen()
        print(dim('Settings > Archive > Search separator'))
        print()
        sep = search_separator()
        if sep:
            print(f'Several searches at once: {sep}')
            print(dim(f'  Put it between queries to search for each, e.g. nginx{sep} ERR504'))
        else:
            print('Several searches at once: off')
        print()
        print(dim(f'  [type] new symbol   [d] default {SEARCH_SEPARATOR}   [c] turn off   [b] back'))
        print()
        command = read_command('separator> ')
        if command == 'b':
            return
        if command == 'd':
            update_search_separator(SEARCH_SEPARATOR)
            haptic('toggle')
        elif command == 'c':
            update_search_separator('')
            haptic('toggle')
        elif command and not any(ch.isalnum() or ch.isspace() for ch in command):
            update_search_separator(command)
            haptic('toggle')
        elif command:
            error('Use symbols only, like ; or |')


_KEEPER_STATUS = {
    'missing': 'Ollama not installed',
    'stopped': 'Ollama not running',
    'docker': 'Ollama not running',
    'off': 'off',
    'foreign': 'not Ollama',
    'no_models': 'no models',
    'no_model': 'choose a model',
    'model_missing': 'model removed',
    'ready': 'online',
}

_KEEPER_NAMES = {'server': 'Server', 'local': 'This computer'}


_OLLAMA_DOCS = {
    'macOS': 'https://docs.ollama.com/macos',
    'Windows': 'https://docs.ollama.com/windows',
    'Linux': 'https://docs.ollama.com/linux',
}
_OLLAMA_FAQ = 'https://docs.ollama.com/faq'
_OLLAMA_START = {
    'macOS': 'Open Ollama from Applications, then press Enter.',
    'Windows': 'Open Ollama from the Start menu, then press Enter.',
}
_KEEPER_STEPS = {'missing': 0, 'stopped': 1, 'docker': 1, 'foreign': 1, 'no_models': 2, 'no_model': 2,
                 'model_missing': 2}
_OLLAMA_GPU = 'https://docs.ollama.com/gpu'
_OLLAMA_DOCKER = 'https://docs.ollama.com/docker'
_DOCKER_START = 'If it runs in Docker, start the container: docker start ollama'
_DOCKER_PORT = 'In Docker, publish the port: -p 11434:11434'
_DOCKER_GPU = f'If Ollama runs in Docker, pass the GPU to the container: {_OLLAMA_DOCKER}'


def _ollama_docs():
    return _OLLAMA_DOCS.get(system.OS, 'https://ollama.com/download')


def _keeper_rows(rows):
    states = keeper.statuses(rows)
    return [(s, keeper.placement(c) if s[0] == 'ready' else None) for c, s in zip(rows, states)]


def _keeper_download(conn):
    clear_screen()
    print(dim(f'Settings > Archive > Keeper > {_KEEPER_NAMES[conn["slot"]]}'))
    print()
    print(f'  {keeper.RECOMMENDED}')
    print(dim('  Ctrl+C to cancel'))
    print()

    def step(status, done, total):
        note = f'{done * 100 // total}%  {status}' if total and done else status
        progress('Downloading', done or 0, total or 0, note)

    try:
        keeper.pull(conn, keeper.RECOMMENDED, step)
        update_keeper_model(conn['slot'], keeper.RECOMMENDED)
        clear_line()
        print('Done.')
        pause(feedback='success')
    except keeper.KeeperOffline as e:
        clear_line()
        print(f'Download failed: {e}')
        pause(feedback='error')
    except KeyboardInterrupt:
        clear_line()
        print('Cancelled.')
        pause()


def _keeper_models(found, current):
    for i, name in enumerate(found, 1):
        marks = [m for m, on in (('tested', name == keeper.RECOMMENDED), ('current', name == current)) if on]
        print(f'{num(i, len(str(len(found))))}{name}' + (dim('  ' + ' · '.join(marks)) if marks else ''))
    if any(name != keeper.RECOMMENDED for name in found):
        print(dim(f'  Keeper is tested on {keeper.RECOMMENDED}. Larger models often answer better, smaller ones worse.'))
    if found:
        print()


def _keeper_models_screen(slot):
    while True:
        conn = keeper.connection(slot)
        if conn is None:
            return
        clear_screen()
        print(dim(f'Settings > Archive > Keeper > {_KEEPER_NAMES[slot]}'))
        print()
        state, found = wait('Checking models', keeper.status, conn)
        if state == 'missing':
            print('  Keeper runs on Ollama, a free app for AI models on this computer.')
            print(f'  Install it: {_ollama_docs()}')
            print('  Then open it and press Enter.')
            print()
        elif state == 'stopped':
            print('  Ollama is installed but not running. Start it, then press Enter.')
            print(dim(f'  How to start it: {_ollama_docs()}'))
            print()
        elif state == 'docker':
            print('  Ollama is not responding on this computer.')
            print(f'  {_DOCKER_START}')
            print(dim(f'  Docker guide: {_OLLAMA_DOCKER}'))
            print(dim(f'  Not installed yet: {_ollama_docs()}'))
            print()
        elif state == 'off':
            print(f'  {conn["url"]} is not responding. Press Enter to check again.')
            print(dim('  Ollama on another computer must be open to the network.'))
            print(dim(f'  {_OLLAMA_FAQ}'))
            print(dim(f'  {_DOCKER_PORT}'))
            print()
        elif state == 'foreign':
            print(f'  {conn["url"]} answers, but it is not Ollama.')
            print(dim('  Check the address and port.' if slot == 'server' else '  Another program is using this port.'))
            print()
        _keeper_models(found, conn['model'])

        needs_model = state in ('no_models', 'no_model', 'model_missing')
        can_download = needs_model and keeper.RECOMMENDED not in found
        nav = [('number', 'select', '#', 'select')] if found else []
        nav += [('d', f'download {keeper.RECOMMENDED}', 'd', 'download')] if can_download else []
        nav.append(('b', 'back'))
        print(dim(nav_line(nav)))
        print()

        command = read_command('model> ').lower()
        keeper.reset()
        if is_back(command):
            return
        if command == 'd' and can_download:
            _keeper_download(conn)
        elif found and command.isascii() and command.isdigit() and 1 <= int(command) <= len(found):
            update_keeper_model(slot, found[int(command) - 1])
            keeper.reset()
            haptic('toggle')
            return


def _open_docs(url):
    if not system.open_file(url):
        error(f'Could not open a browser. The guide is at {url}')


def _keeper_setup():
    while True:
        conn = keeper.connection('local')
        clear_screen()
        print(dim('Settings > Archive > Keeper'))
        print()
        state, found = wait('Checking Ollama', keeper.status, conn)
        if state == 'ready':
            return True
        current = _KEEPER_STEPS[state]
        print('  Keeper answers questions about your archive in your own words.')
        print('  It runs on Ollama, a free app for AI models on this computer.')
        print()
        for i, name in enumerate(('Ollama installed', 'Ollama running', 'Model chosen')):
            mark = dim('✓') if i < current else '→'
            print(f'  {mark} {name}' if i <= current else dim(f'  · {name}'))
        print()
        if state == 'missing':
            print('  Install Ollama, open it once, then press Enter.')
            print(dim(f'  Guide: {_ollama_docs()}'))
        elif state == 'stopped':
            print('  Ollama is installed but not running.')
            print(f'  {_OLLAMA_START.get(system.OS, "Run ollama serve, then press Enter.")}')
            print(dim(f'  Guide: {_ollama_docs()}'))
        elif state == 'docker':
            print('  Ollama is not responding on this computer.')
            print(f'  {_DOCKER_START}')
            print(dim(f'  Guide: {_OLLAMA_DOCKER}'))
            print(dim(f'  Not installed yet: {_ollama_docs()}'))
        elif state == 'foreign':
            print(f'  {conn["url"]} answers, but it is not Ollama.')
            print(dim('  Another program is using this port.'))
        elif state == 'no_models':
            print('  Ollama has no models yet. Download one to start.')
            print(dim(f'  Keeper is tested on {keeper.RECOMMENDED}.'))
        elif state == 'model_missing':
            print(f'  {conn["model"]} is no longer in Ollama. Choose another model.')
        else:
            print('  Choose the model Keeper will use.')
        print()
        _keeper_models(found, conn['model'])

        guide = state in ('missing', 'stopped', 'docker')
        can_download = current == 2 and keeper.RECOMMENDED not in found
        nav = [('number', 'select', '#', 'select')] if found else []
        nav += [('o', 'open the guide', 'o', 'guide')] if guide else []
        nav += [('d', f'download {keeper.RECOMMENDED}', 'd', 'download')] if can_download else []
        nav += [('s', 'use a server', 's', 'server'), ('↵', 'check again', '↵', 'check'), ('b', 'back')]
        print(dim(nav_line(nav)))
        print()

        command = read_command('keeper> ').lower()
        keeper.reset()
        if is_back(command):
            return False
        if command == 'o' and guide:
            _open_docs(_OLLAMA_DOCKER if state == 'docker' else _ollama_docs())
        elif command == 'd' and can_download:
            _keeper_download(conn)
        elif command == 's':
            _server_screen()
            if keeper.has_server():
                return True
        elif found and command.isascii() and command.isdigit() and 1 <= int(command) <= len(found):
            update_keeper_model('local', found[int(command) - 1])
            haptic('toggle')


def _server_screen():
    while True:
        conn = keeper.connection('server')
        clear_screen()
        print(dim('Settings > Archive > Keeper > Server'))
        print()
        print('  Keeper can use Ollama on another computer, for example one with a GPU.')
        print()
        if conn:
            state, _ = wait('Checking server', keeper.status, conn)
            print(f'  Address   {conn["url"].split("://", 1)[-1]}')
            print(f'  Model     {conn["model"] or "—"}')
            print(f'  Status    {dim(_KEEPER_STATUS[state])}')
            if state == 'off':
                print()
                print(dim('  Ollama on that computer must be open to the network.'))
                print(dim(f'  {_OLLAMA_FAQ}'))
                print(dim(f'  {_DOCKER_PORT}'))
            elif state == 'foreign':
                print()
                print(dim('  Check the address and port.'))
        else:
            print(f'  Address   {dim("not set")}')
        print()
        nav = [('type', 'address, e.g. server-ip:11434', 'type', 'address')]
        nav += [('m', 'model'), ('c', 'clear')] if conn else []
        nav += [('↵', 'check again', '↵', 'check'), ('b', 'back')]
        print(dim(nav_line(nav)))
        print()

        command = read_command('address> ')
        keeper.reset()
        low = command.lower()
        if is_back(low):
            return
        if low == 'c':
            if conn:
                update_keeper_server('')
                haptic('toggle')
        elif low == 'm':
            if conn:
                _keeper_models_screen('server')
        elif command:
            try:
                update_keeper_server(command)
            except ValueError:
                error('Type an address like server-ip:11434')
            else:
                haptic('toggle')


def keeper_screen():
    while True:
        if not keeper.has_server() and not _keeper_setup():
            return
        rows = keeper.connections()
        has_server = keeper.has_server()
        clear_screen()
        print(dim('Settings > Archive > Keeper'))
        print()
        states = wait('Checking Keeper', _keeper_rows, rows)
        for i, (conn, ((state, _), where)) in enumerate(zip(rows, states), 1):
            name = _KEEPER_NAMES[conn['slot']]
            model = conn['model'] or '—'
            shown = f'{_KEEPER_STATUS[state]} · {where}' if where else _KEEPER_STATUS[state]
            print(f'{num(i)}{name:<14} {model:<20} {dim(shown)}')
            if conn['slot'] == 'server':
                print(dim(f'    {conn["url"].split("://", 1)[-1]}'))
        print()
        cpu = [conn['slot'] for conn, (_, where) in zip(rows, states) if where == 'CPU']
        if cpu:
            print(dim('  The model runs on the CPU, so replies are slow.'))
            print(dim(f'  GPU support: {_OLLAMA_GPU}'))
            if 'server' in cpu or keeper.docker():
                print(dim(f'  {_DOCKER_GPU}'))
            print()
        if has_server:
            print(dim('  Keeper uses the server when it is on, otherwise this computer.'))
            print()
        nav = [('number', 'model', '#', 'model'), ('s', 'server'), ('↵', 'check again', '↵', 'check'), ('b', 'back')]
        print(dim(nav_line(nav)))
        print()

        command = read_command('keeper> ').lower()
        keeper.reset()
        if is_back(command):
            return
        if command == 's':
            _server_screen()
        elif command.isascii() and command.isdigit() and 1 <= int(command) <= len(rows):
            _keeper_models_screen(rows[int(command) - 1]['slot'])
