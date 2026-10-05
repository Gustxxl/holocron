import re
import shutil

_SEP_RE = re.compile(r'^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$')
_MD_RE = re.compile(r'\*\*|__|`')


def table_cells(line):
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|'):
        line = line[:-1]
    return [_MD_RE.sub('', c).strip() for c in line.split('|')]


def _render(rows, width):
    cols = max(len(r) for r in rows)
    rows = [r + [''] * (cols - len(r)) for r in rows]
    widths = [max(len(r[i]) for r in rows) for i in range(cols)]
    if sum(widths) + 3 * cols + 1 > width:
        return None

    def border(left, mid, right):
        return left + mid.join('─' * (w + 2) for w in widths) + right

    def row(cells):
        return '│' + '│'.join(f' {c.ljust(w)} ' for c, w in zip(cells, widths)) + '│'

    out = [border('┌', '┬', '┐'), row(rows[0]), border('├', '┼', '┤')]
    out += [row(r) for r in rows[1:]]
    out.append(border('└', '┴', '┘'))
    return out


def render_tables(text, width=None):
    width = width or shutil.get_terminal_size().columns
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        if (lines[i].strip().startswith('|') and i + 1 < len(lines)
                and _SEP_RE.match(lines[i + 1].strip())):
            block = [lines[i]]
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith('|'):
                block.append(lines[j])
                j += 1
            rendered = _render([table_cells(l) for l in block], width)
            out.extend(rendered or lines[i:j])
            i = j
            continue
        out.append(lines[i])
        i += 1
    return '\n'.join(out)
