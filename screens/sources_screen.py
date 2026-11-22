import re
from core import sources, system
from core.sources import cli, macos
from ui.interface import clear_screen, confirm, dim, error, haptic, is_back, num, pause, pick, read_command, nav_line, wait


_DEFAULT_RE = re.compile(r'd\s*(\d+)')
_STEPS = ['old_macos', 'missing', 'denied']
_BAR_STEPS = ['old_macos', 'missing', 'no_folder', 'off']
_MAIN_RE = re.compile(r'm\s*(\d+)')
_AHEAD_RE = re.compile(r't\s*(\d+)')
_AHEAD = {0: 'any day', 1: 'today', 2: 'today and tomorrow'}
_ORIGINS = {'holocron': 'downloaded by Holocron', 'homebrew': 'installed with Homebrew', 'system': 'installed separately'}
_REMOVABLE = ('holocron', 'homebrew')


def source_setup(source):
    return _SETUPS[source.SETUP](source)


def _macos_setup(source):
    clt = False
    while True:
        state = source.status()
        if state == 'ready':
            return True
        current = _STEPS.index(state)
        names = [f'macOS {source.MACOS} or later', source.PROGRAM, f'Access to {source.PRIVACY}']
        brew = cli.available('brew')
        clear_screen()
        print(dim(f'Settings > {source.NAME}'))
        print()
        print(f'  Holocron shows and adds {source.ABOUT} through {source.PROGRAM},')
        print('  a free command-line tool.')
        print()
        _steps(names, current)
        print()

        nav = []
        if state == 'old_macos':
            print(f'  {source.NAME} needs macOS {source.MACOS} or later.')
            print(dim(f'  This Mac runs macOS {system.version() or "unknown"}.'))
        elif state == 'missing':
            print(f'  Holocron can download {source.PROGRAM} for you, nothing else is needed.')
            if brew:
                print(dim(f'  Or install it with Homebrew: brew install {source.TAP}'))
            if clt:
                print()
                print(f'  Homebrew needs newer Command Line Tools to build {source.PROGRAM}.')
                print('  Press i to download it without Homebrew,')
                print('  or update them in System Settings > General > Software Update.')
                print(dim('  If no update shows up, run: xcode-select --install'))
                nav.append(('u', 'open Software Update', 'u', 'update'))
            nav.append(('i', 'install now', 'i', 'install'))
            if brew:
                nav.append(('brew', 'install with Homebrew', 'brew', 'brew'))
        elif state == 'denied':
            app = macos.terminal()
            print(f'  macOS asks once whether {app} may use {source.PRIVACY}.')
            print(f'  If the request does not appear, turn on {app} in')
            print(f'  System Settings > Privacy & Security > {source.PRIVACY},')
            print(f'  then quit and reopen {app}.')
            nav += [('a', 'ask for access', 'a', 'access'), ('o', 'open System Settings', 'o', 'settings')]
        print()
        nav += [('↵', 'check again', '↵', 'check'), ('b', 'back')]
        print(dim(nav_line(nav)))
        print()

        command = read_command(f'{source.NAME.lower()}> ').lower()
        if is_back(command):
            return False
        if command == 'i' and state == 'missing':
            print()
            ok = wait(f'Downloading {source.PROGRAM}', macos.download, source.REPO, source.PROGRAM)
            print('Installed.' if ok else 'Download did not finish. Check the connection and try again.')
            pause(feedback='success' if ok else 'error')
        elif command == 'brew' and state == 'missing' and brew:
            print()
            result = macos.install(source.TAP)
            clt = result == 'clt'
            print()
            if result == 'clt':
                continue
            print('Installed.' if result == 'ok' else 'Installation did not finish. See the output above.')
            pause(feedback='success' if result == 'ok' else 'error')
        elif command == 'u' and state == 'missing' and clt:
            macos.open_url(macos.UPDATE_URL)
        elif command == 'a' and state == 'denied':
            if not source.authorize():
                error(f'Still no access. Turn on {macos.terminal()} in System Settings.')
        elif command == 'o' and state == 'denied':
            macos.open_url(source.PRIVACY_URL)


def _swiftbar_setup(source):
    while True:
        state = source.status()
        if state == 'ready':
            return True
        brew = cli.available('brew')
        clear_screen()
        print(dim(f'Settings > {source.NAME}'))
        print()
        print('  Holocron shows upcoming reminders and your shift')
        print(f'  in the macOS menu bar through {source.APP}, a free app.')
        print()
        _steps([f'macOS {source.MACOS} or later', source.APP, 'Plugin folder', 'Holocron in the menu bar'],
               _BAR_STEPS.index(state))
        print()

        nav = []
        if state == 'old_macos':
            print(f'  {source.APP} needs macOS {source.MACOS} or later.')
            print(dim(f'  This Mac runs macOS {system.version() or "unknown"}.'))
        elif state == 'missing':
            print(f'  Download {source.APP}: {source.RELEASES}')
            if brew:
                print(dim(f'  Or install it with Homebrew: brew install {source.TAP}'))
            nav.append(('o', 'open the download page', 'o', 'download'))
            if brew:
                nav.append(('brew', 'install with Homebrew', 'brew', 'brew'))
        elif state == 'no_folder':
            print(f'  {source.APP} needs a folder for its plugins.')
            print(f'  Holocron can create {source.HOME} and set it for you.')
            print(dim(f'  {source.APP} restarts if it is open.'))
            nav += [('f', 'create the folder', 'f', 'create'), ('o', f'open {source.APP}', 'o', 'open')]
        else:
            print(f'  Holocron adds {source.FILE} to the {source.APP} plugin folder:')
            print(dim(f'  {source.folder()}'))
            nav.append(('a', 'add to the menu bar', 'a', 'add'))
        print()
        nav += [('↵', 'check again', '↵', 'check'), ('b', 'back')]
        print(dim(nav_line(nav)))
        print()

        command = read_command(f'{source.NAME.lower()}> ').lower()
        if is_back(command):
            return False
        if command == 'o' and state == 'missing':
            macos.open_url(source.RELEASES)
        elif command == 'o' and state == 'no_folder':
            macos.open_url(str(source.app()))
        elif command == 'f' and state == 'no_folder':
            result = wait(f'Setting up {source.APP}', source.create)
            if result == 'ok':
                haptic('success')
            elif result == 'running':
                error(f'{source.APP} did not quit. Quit it, then press f again')
            else:
                error(f'Could not create {source.HOME}')
        elif command == 'brew' and state == 'missing' and brew:
            print()
            ok = macos.install(source.TAP) == 'ok'
            print()
            print('Installed.' if ok else 'Installation did not finish. See the output above.')
            pause(feedback='success' if ok else 'error')
        elif command == 'a' and state == 'off':
            if source.add():
                haptic('success')
            else:
                error(f'Could not write to {source.folder()}')


def _steps(names, current):
    for i, name in enumerate(names):
        mark = dim('✓') if i < current else '→'
        print(f'  {mark} {name}' if i <= current else dim(f'  · {name}'))


_SETUPS = {'macos': _macos_setup, 'swiftbar': _swiftbar_setup}


def tool_screen(source):
    while True:
        where = cli.origin(source.PROGRAM)
        if where is None:
            return
        clear_screen()
        print(dim(f'Settings > {source.NAME} > {source.PROGRAM}'))
        print()
        print(f'  {source.PROGRAM}   {_ORIGINS[where]}')
        print(dim(f'  {cli.which(source.PROGRAM)}'))
        other = cli.shadowed(source.PROGRAM)
        if other:
            print(dim(f'  Also installed at {other}, Holocron uses it once this copy is deleted'))
        print()
        nav = [('d', 'delete')] if where in _REMOVABLE else []
        nav.append(('b', 'back'))
        print(dim(nav_line(nav)))
        print()
        command = read_command(f'{source.PROGRAM}> ').lower()
        if is_back(command):
            return
        if command == 'd' and where in _REMOVABLE and confirm(f'Delete {source.PROGRAM}?'):
            if macos.remove(source.PROGRAM, source.TAP):
                haptic('success')
            elif where == 'homebrew':
                print()
                print('Could not delete. See the output above.')
                pause(feedback='error')
            else:
                error(f'Could not delete {source.PROGRAM}')


def lists_screen(source):
    lists = source.lists()
    if lists is None:
        unreadable(source)
        return
    tool = hasattr(source, 'PROGRAM')
    while True:
        if not source.available():
            return
        chosen = sources.selected(source.KEY)
        main = sources.default(source.KEY, lists)
        shown = sources.option(source.KEY, 'shown', source.SHOWN)
        ahead = sources.option(source.KEY, 'ahead', source.AHEAD)
        lines = [dim(f'Settings > {source.NAME}'), '']
        digits = len(str(len(lists)))
        for i, l in enumerate(lists, 1):
            mark = dim('  ✓') if l['id'] in chosen else ''
            mark += dim('  default') if l['id'] == main else ''
            lines.append(f'{num(i, digits)}{l["title"]}{mark}')
        if not lists:
            lines.append(f'No {source.LISTS}')
        when = _AHEAD.get(ahead, f'next {ahead} days')
        lines += ['', f'Main screen   {dim(f"{shown} · {when}" if shown else "hidden")}']
        nav = [('number', 'show/hide', '#', 'show/hide'), ('d number', 'default', 'd#', 'default'),
               ('m number', 'main screen', 'm#', 'main'), ('t number', 'days', 't#', 'days')]
        nav += [('i', 'info')] if tool else []
        nav.append(('b', 'back'))
        lines += ['', dim(nav_line(nav)), '']
        frame = '\n'.join(lines)
        clear_screen()
        print(frame)
        command = read_command(f'{source.LISTS}> ').lower()
        default = _DEFAULT_RE.fullmatch(command)
        count = _MAIN_RE.fullmatch(command)
        days = _AHEAD_RE.fullmatch(command)
        if is_back(command):
            return
        if command == 'i' and tool:
            tool_screen(source)
        elif default and 1 <= int(default.group(1)) <= len(lists):
            sources.set_default(source.KEY, lists[int(default.group(1)) - 1]['id'])
            haptic('toggle')
        elif count and int(count.group(1)) <= 20:
            sources.set_option(source.KEY, 'shown', int(count.group(1)))
            haptic('toggle')
        elif days and int(days.group(1)) <= 30:
            sources.set_option(source.KEY, 'ahead', int(days.group(1)))
            haptic('toggle')
        elif pick(command, len(lists)):
            sources.toggle_list(source.KEY, lists[int(command) - 1]['id'])
            haptic('toggle')


def unreadable(source):
    error(source.HINT if not source.authorized() else f'Could not read {source.NAME}')


def plugin_screen(source):
    while source.status() == 'ready':
        clear_screen()
        print(dim(f'Settings > {source.NAME}'))
        print()
        print('  Holocron is in the menu bar')
        print(dim(f'  {source.plugin()}'))
        print()
        print(f'  New reminder shortcut   {dim(source.shortcut() or "off")}')
        print()
        print(dim(nav_line([('k', 'shortcut'), ('d', 'remove from the menu bar', 'd', 'remove'), ('b', 'back')])))
        print()
        command = read_command(f'{source.NAME.lower()}> ').lower()
        if is_back(command):
            return
        if command == 'k':
            _shortcut(source)
            continue
        if command != 'd':
            continue
        tidy = source.owned()
        question = 'Remove Holocron from the menu bar?'
        if tidy:
            question = f'Remove Holocron from the menu bar, quit {source.APP} and delete {source.folder()}?'
        if not confirm(question):
            continue
        if wait('Removing', source.remove):
            haptic('success')
        else:
            error(f'Could not remove. Quit {source.APP} and try again' if tidy else f'Could not delete {source.plugin()}')


def _shortcut(source):
    print(dim('  Keys like option+r or ctrl+shift+n, off to turn it off'))
    text = read_command('keys> ').strip().lower()
    if not text:
        return
    combo = '' if text == 'off' else source.keys(text)
    if text != 'off' and not combo:
        error('Type keys like option+r, or off')
        return
    sources.set_option(source.KEY, 'shortcut', combo)
    source.refresh()
    haptic('toggle')
