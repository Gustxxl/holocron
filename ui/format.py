from datetime import timedelta

from core.dates import DAYS


def plural(n, word):
    return f'{n} {word}' if n == 1 else f'{n} {word}s'


def day_label(d, today):
    if d == today:
        return 'today'
    if d == today + timedelta(days=1):
        return 'tomorrow'
    return f'{d:%a %d %b}'


def time_range(start, end):
    return f'{start:%H:%M}–{end:%H:%M}'


def date_span(a, b):
    if a == b:
        return f'{a:%d %b %Y}'
    if (a.year, a.month) == (b.year, b.month):
        return f'{a:%d}–{b:%d %b %Y}'
    if a.year == b.year:
        return f'{a:%d %b} – {b:%d %b %Y}'
    return f'{a:%d %b %Y} – {b:%d %b %Y}'


def week_span(first):
    last = first + timedelta(days=6)
    if first.month == last.month:
        return f'{first:%a %d} – {last:%a %d %b}'
    return f'{first:%a %d %b} – {last:%a %d %b}'


def periods(items):
    return ' + '.join(f'{a}–{b}' for a, b in items)


def day_runs(indexes):
    runs = []
    for i in indexes:
        if runs and i == runs[-1][1] + 1:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    return ', '.join(DAYS[a] if a == b else f'{DAYS[a]}–{DAYS[b]}' for a, b in runs)


def days_summary(days):
    groups = {}
    for i, items in enumerate(days):
        if items:
            groups.setdefault(tuple(map(tuple, items)), []).append(i)
    return '   '.join(f'{day_runs(idx)} {periods(key)}' for key, idx in groups.items())


def duration(delta):
    minutes = max(int(delta.total_seconds() // 60), 0)
    days, minutes = divmod(minutes, 1440)
    h, m = divmod(minutes, 60)
    if days:
        return f'{days}d {h}h'
    if h:
        return f'{h}h{m:02d}'
    return f'{m}m'
