from datetime import date, datetime, timedelta
from pathlib import Path
import shutil
from core.config import load
from core.os_info import user_os
import sys
import time
from screens.settings_screen import operator_name, settings_screen
from ui.interface import dim, clear_screen, pause
from core.updater import update


LOGO = Path("ui/logo.txt")
LOGO_TEXT = "HOLOCRON"



def main_screen():
    while True:
        clear_screen()
        show_logo()
        show_today_date()
        greet()
        print()
        user_input = input('system> ')
        command = user_input.lower()
        if command == 'q':
            disconnect()
            break
        elif command == 'settings':
            clear_screen()
            settings_screen()
        elif command == 'system':
            print(user_os())
            pause()
        elif command == 'update':
            update()
        else:
            ...



def show_logo():
    text = LOGO.read_text(encoding="utf-8")
    width = shutil.get_terminal_size().columns
    lines = text.splitlines()
    block_width = max((len(line) for line in lines), default=0)
    print()
    if block_width > width:
        print(dim(LOGO_TEXT.center(width)))
        return
    pad = (width - block_width) // 2
    for line in lines:
        print(dim(" " * pad + line))
    print()


def show_today_date():
    print(dim(date.today().strftime("%a %b %d %Y")))


def greet():
    print(f"Welcome back, {operator_name()}")


def disconnect():
    clear_screen()
    msg = "Disconnecting from the archives"
    sys.stdout.write(msg)
    sys.stdout.flush()
    for _ in range(3):
        time.sleep(0.12)
        sys.stdout.write(".")
        sys.stdout.flush()
    time.sleep(0.12)
    clear_screen()
