import re
import textwrap
from ui.interface import bold, dim
from ui.markdown import code_blocks, is_code, links, render_tables

_B_ON, _B_OFF = '\x01', '\x02'

_FRONT_RE = re.compile(r'\A---\n.*?\n---[ \t]*(?:\n|\Z)', re.S)
_COMMENT_RE = re.compile(r'%%.*?%%', re.S)
_HEADING_RE = re.compile(r'^\s{0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$')
_RULE_RE = re.compile(r'^\s{0,3}([-*_])(?:\s*\1){2,}\s*$')
_TASK_RE = re.compile(r'^(\s*)[-*+]\s+\[(.)\]\s+(.*)$')
_BULLET_RE = re.compile(r'^(\s*)[-*+]\s+(.*)$')
_ORDERED_RE = re.compile(r'^(\s*)(\d+[.)])\s+(.*)$')
_QUOTE_RE = re.compile(r'^\s*>\s?(.*)$')
_CALLOUT_RE = re.compile(r'^\[!(\w+)\][-+]?\s*(.*)$')
_BR_RE = re.compile(r'<br\s*/?>', re.I)
_TAG_RE = re.compile(r'</?[a-zA-Z][^>]*>')
_EMBED_RE = re.compile(r'!\[\[([^\]|#]+)[^\]]*\]\]')
_WIKI_RE = re.compile(r'\[\[([^\]|\\]+)(?:\\?\|([^\]]+))?\]\]')
_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)[^)]*\)')
_LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)\s]+)[^)]*\)')
_CODE_RE = re.compile(r'`([^`]+)`')
_BOLD_RE = re.compile(r'(\*\*|__)(?=\S)(.+?)(?<=\S)\1')
_MARK_RE = re.compile(r'(==|~~)(?=\S)(.+?)(?<=\S)\1')
_ITALIC_RE = re.compile(r'(?<![\w*])([*_])(?=\S)(.+?)(?<=\S)\1(?![\w*])')
_BLOCK_ID_RE = re.compile(r'\s\^[\w-]+\s*$')


def _wiki(m):
    if m.group(2):
        return m.group(2)
    return re.sub(r'#\^?', ' › ', m.group(1)).strip(' ›')


def _inline(text):
    text = links(text)
    text = _TAG_RE.sub('', _BR_RE.sub(' ', text))
    text = _EMBED_RE.sub(lambda m: m.group(1), text)
    text = _WIKI_RE.sub(_wiki, text)
    text = _IMAGE_RE.sub(lambda m: m.group(1) or m.group(2).rsplit('/', 1)[-1], text)
    text = _LINK_RE.sub(r'\1', text)
    text = _CODE_RE.sub(r'\1', text)
    text = _BOLD_RE.sub(lambda m: _B_ON + m.group(2) + _B_OFF, text)
    text = _MARK_RE.sub(r'\2', text)
    text = _ITALIC_RE.sub(r'\2', text)
    return _BLOCK_ID_RE.sub('', text)


def _plain(text):
    return _inline(text).replace(_B_ON, '').replace(_B_OFF, '')


def _fill(text, width, first, rest):
    return textwrap.fill(text, width=width, initial_indent=first, subsequent_indent=rest,
                         break_long_words=False, break_on_hyphens=False)


def _line(ln, width):
    if not ln.strip():
        return ''
    if _RULE_RE.match(ln):
        return dim('─' * min(width, 40))
    m = _HEADING_RE.match(ln)
    if m:
        return bold(_fill(_plain(m.group(1)), width, '', ''))
    m = _QUOTE_RE.match(ln)
    if m:
        callout = _CALLOUT_RE.match(m.group(1))
        if callout:
            return '│ ' + bold(_plain(callout.group(2)) or callout.group(1).capitalize())
        return _fill(_inline(m.group(1)), width, '│ ', '│ ')
    m = _TASK_RE.match(ln)
    if m:
        indent, state, body = m.groups()
        done = state.lower() == 'x'
        line = _fill(_inline(body), width, indent + ('✓ ' if done else '○ '), indent + '  ')
        return dim(line) if done else line
    m = _BULLET_RE.match(ln)
    if m:
        indent, body = m.groups()
        return _fill(_inline(body), width, indent + '• ', indent + '  ')
    m = _ORDERED_RE.match(ln)
    if m:
        indent, num, body = m.groups()
        return _fill(_inline(body), width, f'{indent}{num} ', indent + ' ' * (len(num) + 1))
    indent = ln[:len(ln) - len(ln.lstrip())]
    return _fill(_inline(ln.strip()), width, indent, indent)


def render_note(text, width):
    text = code_blocks(_COMMENT_RE.sub('', _FRONT_RE.sub('', text.replace('\r\n', '\n'))))
    out, table = [], []
    for ln in text.splitlines() + ['']:
        if not is_code(ln) and ln.lstrip().startswith('|'):
            table.append(_plain(ln.expandtabs(2)))
            continue
        if table:
            out.extend(render_tables('\n'.join(table), width).splitlines())
            table = []
        out.append(ln if is_code(ln) else _line(ln.expandtabs(2), width))
    text = re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip('\n')
    return text.replace(_B_ON, '\033[1m').replace(_B_OFF, '\033[22m')
