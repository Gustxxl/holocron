import sys

if sys.version_info < (3, 12):
    sys.exit(f'Holocron needs Python 3.12+, found {sys.version.split()[0]}. Install a newer Python and run install.py again.')

from core.check_requirements import ensure_environment
ensure_environment()

import colorama
colorama.init()


import os
from core import archives
from core import launch
from core.settings import update_archive_path
from screens.main_screen import main_frame, main_screen
from ui.interface import Spinner, clear_screen, disconnect, pause
from core import updater
from core import config


def start():
    action, value = launch.parse(sys.argv[1:], os.environ.get('HOLO_CWD'))
    if action == 'help':
        print(launch.USAGE)
        return
    if action == 'unknown':
        sys.exit(f'Unknown option {value}. Run holo --help')
    updater.check_update_async()
    if action == 'board':
        update_archive_path(value)
    query = value if action == 'search' else None
    try:
        clear_screen()
        with Spinner('Accessing the archives'):
            archives.load()
            updater.pending_update(5)
            first = None if config.broken or query else main_frame()
        if config.broken:
            print(f'Settings could not be read, defaults are used. A copy is in {config.broken}')
            pause()
        main_screen(first, query)
    except (KeyboardInterrupt, EOFError):
        disconnect()



if __name__ == '__main__':
    start()
