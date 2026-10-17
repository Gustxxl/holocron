import re
from core import sources, system
from core.sources import macos
from ui.interface import clear_screen, dim, error, haptic, is_back, pause, read_command, nav_line

_DEFAULT_RE = re.compile(r'd\s*(\d+)')
_STEPS = ['old_macos', 'no_brew', 'missing', 'denied']
_MAIN_RE = re.compile(r'm\s*(\d+)')
_AHEAD_RE = re.compile(r't\s*(\d+)')
_AHEAD = {0: 'any day', 1: 'today', 2: 'today and tomorrow'}


def source_setup(source):
    clt = False
    while True:
        state = source.status()
        if state == 'ready':
            return True
        current = _STEPS.index(state)
        names = [f'macOS {source.MACOS} or later', 'Homebrew', source.PROGRAM, f'Access to {source.PRIVACY}']
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
            print(f'  {source.NAME} needs macOS {source. MACOS} or later.')
            print(dim(f'  This Mac runs macOS {system.version() or "unknown"}.'))
        elif state == 'no_brew':
            print(f'  {source.PROGRAM} installs with Homebrew, a package manager for macOS.')
            print('  Open brew.sh, copy the install command into a terminal,')
            print('  then come back and press Enter.')
            nav.append(('o', 'open brew.sh', 'o', 'brew.sh'))
        elif state == 'missing':
            print(f'  Install {source.PROGRAM} with Homebrew:')
            print(dim(f'  brew install {source.TAP}'))
            if clt:
                print()
                print(f'  Homebrew needs newer Command Line Tools to build {source.PROGRAM}.')
                print('  Update them in System Settings > General > Software Update,')
                print('  then press i again.')
                print(dim('  If no update shows up, run: xcode-select --install'))
                nav.append(('u', 'open Software Update', 'u', 'update'))
            nav.append(('i', 'install now', 'i', 'install'))
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
        if command == 'o' and state == 'no_brew':
            macos.open_url(macos.BREW_URL)
        elif command == 'i' and state == 'missing':
            print()
            result = macos.install(source.TAP)
            clt = result == 'clt'
            print()
            print('Installed.' if result == 'ok' else 'Installation did not finish. See the output above.')
            pause(feedback=None if result == 'ok' else 'error')
        elif command == 'u' and state == 'missing' and clt:
            macos.open_url(macos.UPDATE_URL)
        elif command == 'a' and state == 'denied':
            if not source.authorize():
                error(f'Still no access. Turn on {macos.terminal()} in System Settings.')
        elif command == 'o' and state == 'denied':
            macos.open_url(source.PRIVACY_URL)


def lists_screen(source):
    lists = source.lists()
    if lists is None:
        unreadable(source)
        return
    while True:
        chosen = sources.selected(source.KEY)
        main = sources.default(source.KEY, lists)
        shown = sources.option(source.KEY, 'shown', source.SHOWN)
        ahead = sources.option(source.KEY, 'ahead', source.AHEAD)
        lines = [dim(f'Settings > {source.NAME}'), '']
        for i, l in enumerate(lists, 1):
            mark = dim('  ✓') if l['id'] in chosen else ''
            mark += dim('  default') if l['id'] == main else ''
            lines.append(f'{i}) {l["title"]}{mark}')
        if not lists:
            lines.append(f'No {source.LISTS}')
        when = _AHEAD.get(ahead, f'next {ahead} days')
        lines += ['', f'Main screen   {dim(f"{shown} · {when}" if shown else "hidden")}']
        nav = [('number', 'show / hide', '#', 'show/hide'), ('d number', 'default', 'd#', 'default'),
               ('m number', 'on main screen', 'm#', 'main'), ('t number', 'days ahead', 't#', 'days'),
               ('b', 'back')]
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
        if pick and 1 <= int(pick.group(1)) <= len(lists):
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
