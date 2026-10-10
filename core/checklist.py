import re

_TASK_RE = re.compile(r'^(\s*[-*+]\s+\[)(.)(\]\s)')
_FENCE_RE = re.compile(r'^\s*(```|~~~)')


def _task_lines(lines):
    fence = None
    for i, ln in enumerate(lines):
        if fence:
            if ln.strip().startswith(fence):
                fence = None
            continue
        m = _FENCE_RE.match(ln)
        if m:
            fence = m.group(1)
            continue
        if _TASK_RE.match(ln):
            yield i


def count(text):
    return sum(1 for _ in _task_lines(text.split('\n')))


def toggle(text, n):
    lines = text.split('\n')
    found = list(_task_lines(lines))
    if not 1 <= n <= len(found):
        return None
    i = found[n - 1]
    lines[i] = _TASK_RE.sub(
        lambda m: m.group(1) + ('x' if m.group(2) == ' ' else ' ') + m.group(3),
        lines[i], count=1,
    )
    return '\n'.join(lines)
