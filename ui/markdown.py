import re
import shutil
import textwrap
from ui.interface import bold, dim

_SEP_RE = re.compile(r'^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$')
_MD_RE = re.compile(r'\*\*|__|`')
_WIKI_URL_RE = re.compile(r'\[\[(https?://[^\]|]+?)(?:\|([^\]]+))?\]\]')
_MD_URL_RE = re.compile(r'(?<!!)\[([^\]]*)\]\((https?://[^)\s]+)[^)]*\)')
_ANGLE_URL_RE = re.compile(r'<(https?://[^>\s]+)>')
_DUP_RE = re.compile(r'(https?://[^\s<>\[\]()|"\']+?)/?(\s*)\1/?(?![^\s<>\[\]()|"\'])')
_CODE = '\x05'
_CODE_BG = '\033[48;5;236m'
_FENCE_RE = re.compile(r'^\s*(```|~~~)')


def code_blocks(text):
    out, fence = [], None
    for ln in text.splitlines():
        if fence:
            if ln.strip().startswith(fence):
                fence = None
            else:
                out.append(_CODE + ln)
            continue
        m = _FENCE_RE.match(ln)
        if m:
            fence = m.group(1)
            continue
        out.append(ln)
    return '\n'.join(out)


def is_code(line):
    return line.startswith(_CODE)


def paint_code(text):
    out = []
    for ln in text.split('\n'):
        if is_code(ln):
            body = ln[1:].replace('\033[0m', '\033[0m' + _CODE_BG)
            ln = f'{_CODE_BG}{body}\033[K\033[0m'
        out.append(ln)
    return '\n'.join(out)


def _labeled(url, label):
    if not label or label.rstrip('/') == url.rstrip('/'):
        return url
    return f'{label} {url}'


def links(text):
    text = _WIKI_URL_RE.sub(lambda m: _labeled(m.group(1), m.group(2)), text)
    text = _MD_URL_RE.sub(lambda m: _labeled(m.group(2), m.group(1)), text)
    text = _ANGLE_URL_RE.sub(r'\1', text)
    return _DUP_RE.sub(r'\1', text)


def table_cells(line):
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|'):
        line = line[:-1]
    return [_MD_RE.sub('', c).strip() for c in line.split('|')]


def _cards(rows, width):
    head, body = rows[0], rows[1:]
    if not body:
        return [textwrap.fill('  '.join(c for c in head if c), width=width,
                              break_long_words=False, break_on_hyphens=False)]
    labels = head[1:]
    label_w = min(max((len(h) for h in labels), default=0), width // 3)
    out = []
    for r in body:
        out.append(bold(r[0] or '—'))
        for name, value in zip(labels, r[1:]):
            if not value:
                continue
            name = name.ljust(label_w)
            pad = ' ' * (len(name) + 4)
            lines = textwrap.wrap(value, width=max(width - len(pad), 10),
                                  break_long_words=False, break_on_hyphens=False)
            out.append(f'  {dim(name)}  {lines[0]}')
            out.extend(pad + ln for ln in lines[1:])
        out.append('')
    return out[:-1]


def _render(rows, width):
    cols = max(len(r) for r in rows)
    rows = [r + [''] * (cols - len(r)) for r in rows]
    widths = [max(len(r[i]) for r in rows) for i in range(cols)]
    if sum(widths) + 3 * cols + 1 > width:
        return _cards(rows, width)

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
            out.extend(_render([table_cells(l) for l in block], width))
            i = j
            continue
        out.append(lines[i])
        i += 1
    return '\n'.join(out)
