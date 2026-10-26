from datetime import date
from pathlib import Path
import shutil

from core import archives
from core.commands import lookup
from core.settings import home_order, operator_name
from core.sources import registry
from screens.events_screen import agenda
from core.updater import pending_update
from screens.schedule_screen import duty_line
from screens.search_screen import search_screen
from screens.tasks_screen import summary
from ui.interface import clear_screen, clip, dim, pause, read_command, Home

APP_DIR = Path(__file__).resolve().parent.parent
LOGO = APP_DIR / "ui" / "logo.txt"
LOGO_TEXT = "HOLOCRON"


def main_screen(first=None, query=None):
    if query:
        first = None
        try:
            _handle(query)
        except Home:
            pass
    while True:
        frame = first or main_frame()
        first = None
        clear_screen()
        print(frame)
        try:
            _handle(read_command('system> '))
        except Home:
            continue


def main_frame():
    return '\n'.join(_frame())


def _handle(raw):
    if raw.strip().lower() in ('', 'b', 'back'):
        return
    command = lookup(raw)
    if command:
        command.run(raw)
        return
    if not archives.is_loaded():
        hint = 'Archive not found — check settings.' if archives.missing() else 'No archive set — add a path in settings.'
        print(dim(hint))
        pause()
        return
    search_screen(raw)


def _frame():
    lines = [dim(date.today().strftime('%a %b %d %Y'))]
    operator = operator_name()
    if operator:
        lines.append(f"Welcome back, {operator}")
    total = archives.count()
    if total:
        lines.append(dim(f'{total} cases indexed'))
    for key in home_order():
        block = _block(key)
        if block:
            lines += ['', *block]
    if pending_update():
        lines.append(dim("Update available — type 'update'"))
    lines.append('')
    width = shutil.get_terminal_size().columns - 1
    return [*_logo(), *(clip(line, width) for line in lines)]


def _block(key):
    if key not in registry.BLOCKS:
        line = duty_line()
        return [line] if line else []
    source = registry.block(key)
    if source is None:
        return []
    return agenda(source) if source.KIND == 'events' else summary(source)


def _logo():
    lines = LOGO.read_text(encoding="utf-8").splitlines()
    width = shutil.get_terminal_size().columns
    block = max((len(line) for line in lines), default=0)
    if block > width:
        return ['', dim(LOGO_TEXT.center(width))]
    pad = ' ' * ((width - block) // 2)
    return ['', *(dim(pad + line) for line in lines), '']
