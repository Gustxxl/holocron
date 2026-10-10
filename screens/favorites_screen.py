from core import archives, favorites
from core.commands import HELP_SECTIONS
from screens.help_screen import render_help
from screens.search_screen import open_case, search_screen, show_list
from ui.interface import clear_screen, dim, pause, read_command


def _open(results, number):
    new = open_case(results, number, '', rerun=False)
    if new:
        search_screen(new)
    return new


def favorites_screen():
    page = 0
    while True:
        results = [(0, c) for c in favorites.resolve(archives.cases())]
        if not results:
            clear_screen()
            print('No favorites yet.')
            print(dim('Open a record and press f to pin it.'))
            pause(feedback=None)
            return
        if len(results) == 1:
            _open(results, 1)
            return
        page = show_list(results, page, '', note='Favorites')
        command = read_command('favorites> ').lower()
        if command in ('b', 'back'):
            return
        if command in ('h', 'help'):
            clear_screen()
            render_help(HELP_SECTIONS)
            pause()
        elif command == 'n':
            page += 1
        elif command == 'p':
            page -= 1
        elif command.isdigit() and 1 <= int(command) <= len(results):
            if _open(results, int(command)):
                return
