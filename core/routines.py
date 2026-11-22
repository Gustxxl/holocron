from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from core import config, dates, schedule, tasks, zones

try:
    import fcntl
except ImportError:
    fcntl = None

KEY = 'routines'
LOCK = Path(config.DATA_DIR) / 'routines.lock'
RULES = ('shift', 'daily', 'manual')
SOON = 2


def _title(raw):
    return ' '.join(raw.split()) if isinstance(raw, str) else ''


def _moment(raw):
    try:
        return datetime.fromisoformat(raw) if isinstance(raw, str) and raw else None
    except ValueError:
        return None


def _record(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get('time'), str):
        return None
    title, at = _title(raw.get('title')), dates.parse_time(raw['time'])
    if not title or at is None:
        return None
    zone = raw.get('zone')
    return {
        'title': title,
        'time': at,
        'zone': zone if zones.valid(zone) else '',
        'rule': raw.get('rule') if raw.get('rule') in RULES else RULES[0],
        'list': raw.get('list') if isinstance(raw.get('list'), str) else '',
        'last': _moment(raw.get('last')),
    }


def load():
    raw = config.load().get(KEY)
    return [r for r in map(_record, raw if isinstance(raw, list) else []) if r]


def _save(items):
    cfg = config.load()
    cfg[KEY] = [{**r, 'last': r['last'].isoformat(timespec='minutes') if r['last'] else ''} for r in items]
    config.save(cfg)


@contextmanager
def _turn(wait=True):
    if fcntl is None:
        yield True
        return
    config.ensure_data_dir()
    with open(LOCK, 'a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB)
            mine = True
        except OSError:
            mine = False
        yield mine


def add(title, at, list_id, zone=''):
    rec = _record({'title': title, 'time': at, 'zone': zone, 'list': list_id})
    if rec is None:
        return False
    with _turn():
        _save([*load(), rec])
    return True


def change(n, **fields):
    with _turn():
        items = load()
        if not 1 <= n <= len(items):
            return False
        items[n - 1].update(fields)
        if 'time' in fields or 'zone' in fields:
            items[n - 1]['last'] = None
        _save(items)
    return True


def remove(n):
    with _turn():
        items = load()
        if not 1 <= n <= len(items):
            return False
        _save(items[:n - 1] + items[n:])
    return True


def next_rule(rule):
    return RULES[(RULES.index(rule) + 1) % len(RULES)]


def parse(text, lists, default, today=None):
    tags, text = tasks.split_tags(text, lists)
    day, when, words = dates.split_when(text, today or date.today())
    if not words:
        return None, 'Type the reminder text'
    if day is not None:
        return None, 'A routine takes a time, not a date'
    if when is None or dates.parse_period(when):
        return None, 'Type one time, e.g. 00:05'
    at = dates.parse_time(when)
    if at is None:
        return None, f'No such time: {when}'
    if len(tags) > 1:
        return None, 'Use one #list'
    list_id, problem = tasks.pick_list(tags[0] if tags else None, lists, default)
    if problem:
        return None, problem
    return {'title': ' '.join(words), 'time': at, 'list': list_id}, None


def _first(routine, now, days, fits):
    at = dates.to_time(routine['time'])
    for i in range(-1, days + 1):
        moment = zones.to_local(datetime.combine(now.date() + timedelta(days=i), at), routine['zone'])
        if moment > now and fits(moment):
            return moment
    return None


def soonest(routine, now):
    return _first(routine, now, SOON, lambda moment: True)


def upcoming(routine, now, sched):
    if routine['rule'] == 'daily':
        return soonest(routine, now)
    if routine['rule'] != 'shift' or not sched.ready:
        return None
    return _first(routine, now, sched.horizon(now.date()), sched.current)


def pending(items, now, sched):
    found = []
    for n, routine in enumerate(items, 1):
        moment = upcoming(routine, now, sched)
        if moment and (routine['last'] is None or moment > routine['last']):
            found.append((n, moment))
    return found


def _place(source, items, n, moment):
    routine = items[n - 1]
    if not source.add(routine['title'], routine['list'], None, moment):
        return False
    if routine['last'] is None or moment > routine['last']:
        routine['last'] = moment
    return True


def plan(source, now=None, sched=None):
    with _turn(wait=False) as mine:
        if not mine:
            return 0
        now = now or datetime.now()
        items = load()
        found = pending(items, now, sched or schedule.load())
        placed = sum(_place(source, items, n, moment) for n, moment in found)
        if placed:
            _save(items)
    return placed


def remind(source, n, now=None):
    with _turn():
        items = load()
        moment = soonest(items[n - 1], now or datetime.now())
        if moment == items[n - 1]['last']:
            return moment, 'Already set'
        if not _place(source, items, n, moment):
            return None, 'Could not add the reminder'
        _save(items)
    return moment, None
