import shutil

from core import history
from core.commands import HELP_SECTIONS
from core.settings import page_rows
from screens.help_screen import render_help
from screens.search_screen import search_screen
from ui.interface import clear_screen, clip, dim, nav_line, num, one_line, pause, pick, read_command


def _frame(queries):
    clear_screen()
    width = shutil.get_terminal_size().columns - 1
    digits = len(str(len(queries)))
    print(dim('Search history'))
    print()
    for i, query in enumerate(queries, 1):
        print(num(i, digits) + clip(one_line(query), width - digits - 3))
    print()
    print(dim(nav_line([('number', 'open', '#', 'open'), ('b', 'back'), ('h', 'help')], width)))
    print()


def history_screen():
    while True:
        queries = history.recent(page_rows())
        if not queries:
            clear_screen()
            print('No searches yet.')
            print(dim('Searches you run show up here.'))
            pause()
            return
        _frame(queries)
        command = read_command('history> ')
        low = command.lower()
        if low in ('b', 'back'):
            return
        if low in ('h', 'help'):
            clear_screen()
            render_help(HELP_SECTIONS)
            pause()
        elif pick(command, len(queries)):
            search_screen(queries[int(command) - 1])
