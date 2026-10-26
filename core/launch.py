from pathlib import Path
from ui.clean_path import clean_input_path

HELP = ('-h', '--help')
USAGE = '''Usage:
  holo                  open Holocron
  holo words            search the archive, or run a command like holo schedule
  holo "nginx; ERR504"  several searches at once, in quotes
  holo path/board.md    use this board as the archive'''


def parse(args, cwd=None):
    if not args:
        return None, None
    first = args[0]
    if first in HELP:
        return 'help', None
    if first.startswith('-'):
        return 'unknown', first
    if len(args) == 1:
        board = _board(first, cwd)
        if board:
            return 'board', board
    text = ' '.join(args).strip()
    return ('search', text) if text else (None, None)


def _board(text, cwd):
    path = Path(clean_input_path(text) or '.')
    if path.suffix.lower() != '.md':
        return None
    if not path.is_absolute():
        if not cwd:
            return None
        path = Path(cwd) / path
    return str(path.resolve()) if path.is_file() else None
