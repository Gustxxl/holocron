from datetime import date
from pathlib import Path
import shutil

from core import archives
from core.commands import _INDEX
from core.settings import operator_name
from core.updater import pending_update
from screens.schedule_screen import duty_line
from screens.search_screen import search_screen
from ui.interface import clear_screen, dim, pause, read_command

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
        show_duty()
        if pending_update():
            print(dim("Update available — type 'update'"))
        print()
        raw = read_command('system> ')
        command = raw.lower()
        if command == '':
            continue

        handler = _INDEX.get(command)
        if handler:
            handler.run(raw)
            continue

        if not archives.is_loaded():
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
    if operator:
        print(f"Welcome back, {operator}")


def show_status():
    total = archives.count()
    if total:
        print(dim(f'{total} cases indexed'))


def show_duty():
    print()
    line = duty_line()
    if line:
        print(line)
