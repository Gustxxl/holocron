import re
from core import sources, system
from core.sources import cli, macos
from ui.interface import clear_screen, confirm, dim, error, haptic, is_back, num, pause, read_command, nav_line, wait

_DEFAULT_RE = re.compile(r'd\s*(\d+)')
_STEPS = ['old_macos', 'missing', 'denied']
_MAIN_RE = re.compile(r'm\s*(\d+)')
_AHEAD_RE = re.compile(r't\s*(\d+)')
_AHEAD = {0: 'any day', 1: 'today', 2: 'today and tomorrow'}
_ORIGINS = {'holocron': 'downloaded by Holocron', 'homebrew': 'installed with Homebrew', 'system': 'installed separately'}
_REMOVABLE = ('holocron', 'homebrew')


def source_setup(source):
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
        for i, name in enumerate(names):
            mark = dim('✓') if i < current else '→'
            print(f'  {mark} {name}' if i <= current else dim(f'  · {name}'))
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
        if command == 'b':
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
    while True:
        if not cli.available(source.PROGRAM):
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
               ('m number', 'main screen', 'm#', 'main'), ('t number', 'days', 't#', 'days'),
               ('i', 'info'), ('b', 'back')]
        lines += ['', dim(nav_line(nav)), '']
        frame = '\n'.join(lines)
        clear_screen()
        print(frame)
        command = read_command(f'{source.LISTS}> ').lower()
        pick = _DEFAULT_RE.fullmatch(command)
        count = _MAIN_RE.fullmatch(command)
        days = _AHEAD_RE.fullmatch(command)
        if is_back(command):
            return
        if command == 'i':
            tool_screen(source)
        elif pick and 1 <= int(pick.group(1)) <= len(lists):
            sources.set_default(source.KEY, lists[int(pick.group(1)) - 1]['id'])
            haptic('toggle')
        elif count and int(count.group(1)) <= 20:
            sources.set_option(source.KEY, 'shown', int(count.group(1)))
            haptic('toggle')
        elif days and int(days.group(1)) <= 30:
            sources.set_option(source.KEY, 'ahead', int(days.group(1)))
            haptic('toggle')
        elif command.isdigit() and 1 <= int(command) <= len(lists):
            sources.toggle_list(source.KEY, lists[int(command) - 1]['id'])
            haptic('toggle')


def unreadable(source):
    error(source.HINT if not source.authorized() else f'Could not read {source.NAME}')
