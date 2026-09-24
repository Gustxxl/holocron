from core.check_requirements import ensure_environment
ensure_environment()

import colorama
colorama.init()

import os

if os.name != 'nt':
    try:
        import readline
    except ImportError:
        pass


from core import archive
import sys
from pathlib import Path
from time import sleep
from core.settings import update_archive_path
from ui.clean_path import clean_input_path
from screens.main_screen import main_screen
from ui.interface import clear_screen, disconnect
from core import updater


def start():
    updater.check_update_async()
    if len(sys.argv) > 1:
        p = clean_input_path(sys.argv[1])
        if p and Path(p).exists():
            update_archive_path(p)
    try:
        clear_screen()
        print('Accessing the archives...')
        archive.load()
        main_screen()
    except (KeyboardInterrupt, EOFError):
        disconnect()


if __name__ == '__main__':
    start()
