import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

REGIONS = ('Africa', 'America', 'Antarctica', 'Asia', 'Atlantic', 'Australia', 'Europe', 'Indian', 'Pacific')
NAME_MAX = 64

_NAME_RE = re.compile(r'[A-Za-z][A-Za-z0-9_+-]*(?:/[A-Za-z0-9_+-]+)*')
_OFFSET_RE = re.compile(r'(?:utc|gmt)?\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?')


def valid(name):
    return isinstance(name, str) and len(name) <= NAME_MAX and bool(_NAME_RE.fullmatch(name))


@lru_cache(maxsize=None)
def get(name):
    if not valid(name):
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


@lru_cache(maxsize=1)
def names():
    return tuple(sorted(n for n in available_timezones() if '/' in n and n.split('/', 1)[0] in REGIONS))


def label(name):
    return name.rsplit('/', 1)[-1].replace('_', ' ')


def _key(text):
    return ' '.join(text.lower().replace('_', ' ').split())


def _local():
    return None


def _now(now):
    return now or datetime.now(timezone.utc)


def offset(name, now=None):
    tz = get(name)
    return _now(now).astimezone(tz).utcoffset() if tz else None


def clock(name, now=None):
    tz = get(name)
    return f'{_now(now).astimezone(tz):%H:%M}' if tz else ''


def utc(delta):
    minutes = int(delta.total_seconds() // 60)
    h, m = divmod(abs(minutes), 60)
    return f'UTC{"-" if minutes < 0 else "+"}{h}' + (f':{m:02d}' if m else '')


def find(text, now=None):
    key = _key(text)
    m = _OFFSET_RE.fullmatch(key)
    if m:
        sign = -1 if m.group(1) == '-' else 1
        want = sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0))
        now = _now(now)
        return [n for n in names() if offset(n, now) == want]
    if len(key) < 2:
        return []
    exact = [n for n in names() if key in (_key(n), _key(label(n)))]
    return exact or [n for n in names() if key in _key(n)]


def to_local(dt, zone):
    tz = get(zone) if zone else None
    if tz is None:
        return dt
    return dt.replace(tzinfo=tz).astimezone(_local()).replace(tzinfo=None)


def differs(name, now=None):
    tz = get(name)
    if tz is None:
        return False
    now = _now(now)
    return now.astimezone(tz).utcoffset() != now.astimezone(_local()).utcoffset()
