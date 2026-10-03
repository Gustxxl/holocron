import shutil
import textwrap
from ui.interface import dim


def render_help(sections):
    width = shutil.get_terminal_size().columns
    col = max(len(e.name) for _, entries in sections for e in entries)
    for title, entries in sections:
        print(dim(f"{title}:"))
        print()
        for e in entries:
            _row(e.name, e.help, col, width)
        print()


def _row(name, desc, col, width):
    left = "  " + name.ljust(col) + "  "
    wrap = max(width - len(left), 20)
    lines = textwrap.wrap(desc, wrap) or [""]
    print(left + lines[0])
    pad = " " * len(left)
    for cont in lines[1:]:
        print(pad + cont)
