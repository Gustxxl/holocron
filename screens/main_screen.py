from datetime import date
from pathlib import Path
import shutil

from core import archives
from core.commands import lookup
from core.settings import operator_name
from core.updater import pending_update
from screens.schedule_screen import duty_line
from screens.search_screen import search_screen
from ui.interface import clear_screen, dim, pause, read_command
from core.sources import remindctl
from screens.tasks_screen import summary


APP_DIR = Path(__file__).resolve().parent.parent
LOGO = APP_DIR / "ui" / "logo.txt"
LOGO_TEXT = "HOLOCRON"


def main_screen():
    while True:
        frame = '\n'.join(_frame())
        clear_screen()
        print(frame)
        raw = read_command('system> ')
        if raw == '':
            continue

        command = lookup(raw)
        if command:
            command.run(raw)
            continue

        if not archives.is_loaded():
            print(dim('No archive set — add a path in settings.'))
            pause()
            continue
        search_screen(raw)


def _frame():
    lines = [*_logo(), dim(date.today().strftime("%a %b %d %Y"))]
    operator = operator_name()
    if operator:
        lines.append(f"Welcome back, {operator}")
    total = archives.count()
    if total:
        lines.append(dim(f'{total} cases indexed'))
    duty = duty_line()
    if duty:
        lines += ['', duty]
    reminders = summary(remindctl)
    if reminders:
        lines += ['', *reminders]
    if pending_update():
        lines.append(dim("Update available — type 'update'"))
    lines.append('')
    return lines


def _logo():
    lines = LOGO.read_text(encoding="utf-8").splitlines()
    width = shutil.get_terminal_size().columns
    block = max((len(line) for line in lines), default=0)
    if block > width:
        return ['', dim(LOGO_TEXT.center(width))]
    pad = ' ' * ((width - block) // 2)
    return ['', *(dim(pad + line) for line in lines), '']
