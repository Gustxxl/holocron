from core.check_requirements import ensure_environment
ensure_environment()

import colorama
colorama.init()


from screens.main_screen import main_screen, disconnect
import os
from time import sleep
from ui.interface import clear_screen


def start():
    try:
        clear_screen()
        print('Accessing the archives...')
        sleep(0.4)
        clear_screen()

        # start cycle
        main_screen()

    # errors
    except (KeyboardInterrupt, EOFError):
        disconnect()


if __name__ == '__main__':
    start()
