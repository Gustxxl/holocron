import re
from datetime import date, datetime, timedelta

DAYS = ('Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su')

_TIME_RE = re.compile(r'^(\d{1,2})(?::?(\d{2}))?$')
_PERIOD_RE = re.compile(r'^\s*([\d:]+)\s*[-–—]\s*([\d:]+)\s*$')
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
