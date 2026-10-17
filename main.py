import sys

if sys.version_info < (3, 12):
    sys.exit(f'Holocron needs Python 3.12+, found {sys.version.split()[0]}. Install a newer Python and run install.py again.')

from core.check_requirements import ensure_environment
ensure_environment()

import colorama
colorama.init()


from core import archives
from pathlib import Path
from core.settings import update_archive_path
from ui.clean_path import clean_input_path
from screens.main_screen import main_screen
from ui.interface import clear_screen, disconnect, pause
from core import updater
from core import config


def start():
    updater.check_update_async()
    if len(sys.argv) > 1:
        p = clean_input_path(sys.argv[1])
        if p and Path(p).exists():
            update_archive_path(p)
    try:
        clear_screen()
        print('Accessing the archives...')
        archives.load()
        if config.broken:
            print(f'Settings could not be read, defaults are used. A copy is in {config.broken}')
            pause()
        updater.pending_update(wait=5)
        main_screen()
    except (KeyboardInterrupt, EOFError):
        disconnect()



if __name__ == '__main__':
    start()
