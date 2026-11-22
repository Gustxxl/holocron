import sys

if sys.version_info < (3, 12):
    sys.exit(f'Holocron needs Python 3.12+, found {sys.version.split()[0]}. Install a newer Python and run install.py again.')

from core.check_requirements import ensure_environment
ensure_environment()

import colorama
colorama.init()


from core import archives
from core import launch
from screens.main_screen import bar_add, bar_frame, bar_toggle, main_frame, main_screen
from ui.interface import Spinner, clear_screen, disconnect, pause
from core import updater
from core import config
from core.sources import registry


def start():
    action, value = launch.parse(sys.argv[1:])
    if action == 'help':
        print(launch.USAGE)
        return
    if action == 'bar':
        print(bar_frame())
        return
    if action in ('done', 'undo'):
        bar_toggle(action, value)
        return
    if action == 'new':
        bar_add()
        return
    if action == 'unknown':
        print(f'Unknown option {value}. Run holo --help', file=sys.stderr)
        sys.exit(2)
    updater.check_update_async()
    query = value if action == 'search' else None
    bar = registry.active('bar')
    opened = False
    try:
        clear_screen()
        with Spinner('Accessing the archives'):
            archives.load()
            opened = bar is not None and bar.start()
            updater.pending_update(5)
            first = None if config.broken or query else main_frame()
        if config.broken:
            print(f'Settings could not be read, defaults are used. A copy is in {config.broken}')
            pause(feedback='warning')
        main_screen(first, query)
    except (KeyboardInterrupt, EOFError):
        disconnect()
    finally:
        if bar is not None:
            bar.finish(opened)



if __name__ == '__main__':
    start()
