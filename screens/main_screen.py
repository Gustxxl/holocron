from datetime import date, datetime, timedelta
from pathlib import Path
import shutil
from core.config import load
from core.os_info import user_os, os_version
import sys
import time
from screens.settings_screen import operator_name, settings_screen
from ui.interface import dim, clear_screen, pause, read_command
from core.updater import update
import platform
from screens.search_screen import search_screen
from core.settings import archive_path
from core import archive
from core.updater import update, pending_update


APP_DIR = Path(__file__).resolve().parent.parent
LOGO = APP_DIR / "ui" / "logo.txt"
LOGO_TEXT = "HOLOCRON"


def main_screen():
    while True:
        clear_screen()
        show_logo()
        show_today_date()
        greet()
        show_status()
        new = pending_update()
        if new:
            print(dim(f'Update available — build {new[:7]}.'))
        print()
        raw = read_command('system> ')
        command = raw.lower()
        if command == 'settings':
            clear_screen()
            settings_screen()
        elif command == 'system':
            print(f"{user_os()} {os_version()} ({platform.machine()})")
            pause()
        elif command == 'update':
            try:
                if update() is False:
                    pause()
            except Exception as e:
                print(f'Update failed: {e}')
                pause()
        elif command == '':
            clear_screen()
            continue
        else:
            if not archive.is_loaded():
                print(dim('No archive set — add a path in settings.'))
                pause()
                continue
            search_screen(raw)


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
    operator = operator_name()
    if operator == "":
        return
    else:
        print(f"Welcome back, {operator}")


def show_status():
    if not archive.is_loaded():
        return
    print(dim(f'{Path(archive.path()).stem} ({archive.count()} cases)'))


def count_cases(path):
    try:
        return len(excalidraw.load_path(path))
    except (OSError, excalidraw.SceneError):
        return 0
