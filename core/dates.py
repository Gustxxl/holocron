import re
from datetime import date, datetime, timedelta

DAYS = ('Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su')

_TIME_RE = re.compile(r'^(\d{1,2})(?::?(\d{2}))?$')
_PERIOD_RE = re.compile(r'^\s*([\d:]+)\s*[-–—]\s*([\d:]+)\s*$')
_WHEN_RE = re.compile(r'\d{1,2}:\d{2}(?:[-–]\d{1,2}:\d{2})?')
_IN_RE = re.compile(r'\+(?:(\d{1,2})h(\d{1,2})?|(\d{1,3})m?)')
BOTH = 'Use +5 or a date, not both'
_DATE_FORMATS = ('%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y', '%d/%m/%Y')
_SHORT_FORMATS = ('%d-%m', '%d.%m', '%d/%m')


def parse_time(text):
    m = _TIME_RE.match(text.strip())
    if not m:
        return None
    h, mnt = int(m.group(1)), int(m.group(2) or 0)
    if h == 24 and mnt == 0:
        h = 0
    if h > 23 or mnt > 59:
        return None
    return f'{h:02d}:{mnt:02d}'


def parse_period(text):
    m = _PERIOD_RE.match(text)
    if not m:
        return None
    a, b = parse_time(m.group(1)), parse_time(m.group(2))
    if not a or not b or a == b:
        return None
    return [a, b]


def parse_periods(text):
    periods = [parse_period(part) for part in text.split(',')]
    return None if None in periods else periods


def parse_date(text, today=None):
    today = today or date.today()
    t = text.strip().lower()
    if t == 'today':
        return today
    if t == 'tomorrow':
        return today + timedelta(days=1)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    for fmt in _SHORT_FORMATS:
        try:
            return datetime.strptime(f'{t}{fmt[2]}{today.year}', f'{fmt}{fmt[2]}%Y').date()
        except ValueError:
            continue
    return None


def split_when(text, today):
    day, when, words = None, None, []
    for word in text.split():
        if when is None and (_WHEN_RE.fullmatch(word) or _IN_RE.fullmatch(word)):
            when = word
        elif day is None and parse_date(word, today):
            day = parse_date(word, today)
        else:
            words.append(word)
    return day, when, words


def after(text, now):
    m = _IN_RE.fullmatch(text)
    if not m:
        return None
    hours, minutes, alone = m.groups()
    if int(minutes or 0) > 59:
        return None
    ahead = timedelta(hours=int(hours or 0), minutes=int(minutes or alone or 0))
    return (now + ahead).replace(second=0, microsecond=0) if ahead else None


def monday(d):
    return d - timedelta(days=d.weekday())


def merge_ranges(ranges):
    out = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1] + timedelta(days=1):
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def to_time(hhmm):
    return datetime.strptime(hhmm, '%H:%M').time()


def period_on(d, a, b):
    start = datetime.combine(d, to_time(a))
    end = datetime.combine(d, to_time(b))
    if end <= start:
        end += timedelta(days=1)
    return start, end


def within(moment, now, days):
    if not days:
        return True
    return moment is not None and moment.date() < now.date() + timedelta(days=days)
