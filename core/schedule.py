from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import NamedTuple, Optional

from core import config
from core.dates import merge_ranges, monday, parse_time, period_on

OFF = '-'
MAX_WEEKS = 52
EPOCH = date(2001, 1, 1)

_CODES = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


class Shift(NamedTuple):
    code: str
    start: datetime
    end: datetime


class Status(NamedTuple):
    on: bool
    shift: Optional[Shift]
    vacation: Optional[tuple]


@dataclass(frozen=True)
class Schedule:
    enabled: bool = False
    shifts: dict = field(default_factory=dict)
    weeks: tuple = ()
    start: Optional[date] = None
    vacations: tuple = ()

    @property
    def cycle_days(self):
        return len(self.weeks) * 7

    @property
    def ready(self):
        return self.enabled and not self.problems()

    def week_days(self):
        return [[self.shifts.get(c) if c != OFF else None for c in w] for w in self.weeks]

    def unknown_codes(self):
        return sorted({c for w in self.weeks for c in w if c != OFF and c not in self.shifts})

    def problems(self):
        out = []
        bad = [str(i) for i, w in enumerate(self.weeks, 1) if not _valid_week(w)]
        if not self.weeks:
            out.append('no weeks')
        elif bad:
            out.append('week ' + ', '.join(bad) + ' needs 7 days')
        elif all(c == OFF for w in self.weeks for c in w):
            out.append('weeks have no shifts')
        if self.start is None:
            out.append('current week not set')
        unknown = self.unknown_codes()
        if unknown:
            out.append('shift ' + ', '.join(unknown) + ' not defined')
        return out

    def week_of(self, d):
        return (d - self.start).days % self.cycle_days // 7

    def vacation_on(self, d):
        for a, b in self.vacations:
            if a <= d <= b:
                return a, b
        return None

    def code_on(self, d):
        if self.vacation_on(d):
            return OFF
        offset = (d - self.start).days % self.cycle_days
        return self.weeks[offset // 7][offset % 7]

    def shifts_on(self, d):
        code = self.code_on(d)
        found = [Shift(code, *period_on(d, a, b)) for a, b in self.shifts.get(code, [])]
        return sorted(found, key=lambda sh: sh.start)

    def current(self, now):
        for d in (now.date() - timedelta(days=1), now.date()):
            for sh in self.shifts_on(d):
                if sh.start <= now < sh.end:
                    return sh
        return None

    def next_shift(self, now):
        today = now.date()
        away = sum((b - max(a, today)).days + 1 for a, b in self.vacations if b >= today)
        for i in range(self.cycle_days + away + 2):
            for sh in self.shifts_on(today + timedelta(days=i)):
                if sh.start > now:
                    return sh
        return None

    def status(self, now=None):
        if not self.ready:
            return None
        now = now or datetime.now()
        sh = self.current(now)
        return Status(sh is not None, sh or self.next_shift(now), self.vacation_on(now.date()))


def _valid_code(code):
    return len(code) == 1 and 'A' <= code <= 'Z'


def _valid_week(week):
    return len(week) == 7 and all(c == OFF or _valid_code(c) for c in week)


def _clean_week(text):
    return ''.join(text.split()).upper().replace('.', OFF)


def _clean_start(text):
    try:
        return monday(date.fromisoformat(str(text)))
    except ValueError:
        return None


def _clean_shifts(raw):
    out = {}
    if not isinstance(raw, dict):
        return out
    for code, periods in raw.items():
        code = str(code).upper()
        if not _valid_code(code) or not isinstance(periods, list):
            continue
        clean = []
        for p in periods:
            if isinstance(p, (list, tuple)) and len(p) == 2:
                a, b = parse_time(str(p[0])), parse_time(str(p[1]))
                if a and b and a != b:
                    clean.append([a, b])
        if clean:
            out[code] = clean
    return out


def _clean_vacations(raw):
    out = []
    for v in raw if isinstance(raw, list) else []:
        if not isinstance(v, dict):
            continue
        try:
            a = date.fromisoformat(str(v.get('from')))
            b = date.fromisoformat(str(v.get('to') or v.get('from')))
        except ValueError:
            continue
        out.append((a, b) if a <= b else (b, a))
    return tuple(merge_ranges(out))


def load():
    raw = config.load().get('schedule') or {}
    weeks = raw.get('weeks') if isinstance(raw.get('weeks'), list) else []
    weeks = tuple(_clean_week(w) for w in weeks if isinstance(w, str))
    start = _clean_start(raw.get('start'))
    if start is None and len(weeks) == 1:
        start = EPOCH
    return Schedule(
        enabled=bool(raw.get('enabled')),
        shifts=_clean_shifts(raw.get('shifts')),
        weeks=weeks,
        start=start,
        vacations=_clean_vacations(raw.get('vacations')),
    )


def _update(**fields):
    cfg = config.load()
    s = dict(cfg.get('schedule') or {})
    s.update(fields)
    cfg['schedule'] = s
    config.save(cfg)


def encode_weeks(weeks_days, shifts=None):
    shifts = shifts or {}
    known = {tuple(map(tuple, p)): c for c, p in sorted(shifts.items())}
    free = iter([c for c in _CODES if c not in shifts])
    out_shifts, out_weeks = {}, []
    for days in weeks_days:
        week = []
        for periods in days:
            if not periods:
                week.append(OFF)
                continue
            key = tuple(map(tuple, periods))
            if key not in known:
                code = next(free, None)
                if code is None:
                    raise ValueError(f'at most {len(_CODES)} different shift times')
                known[key] = code
            out_shifts[known[key]] = [list(p) for p in periods]
            week.append(known[key])
        out_weeks.append(''.join(week))
    return out_shifts, out_weeks


def start_for_week(n, today=None):
    return monday(today or date.today()) - timedelta(weeks=n - 1)


def save_weeks(weeks_days):
    if len(weeks_days) > MAX_WEEKS:
        raise ValueError(f'at most {MAX_WEEKS} weeks')
    shifts, weeks = encode_weeks(weeks_days, load().shifts)
    _update(shifts=shifts, weeks=weeks)


def save_vacations(ranges):
    _update(vacations=[
        {'from': a.isoformat(), 'to': b.isoformat()} for a, b in merge_ranges(ranges)
    ])


def set_enabled(on):
    _update(enabled=bool(on))


def set_current_week(n, today=None):
    _update(start=start_for_week(n, today).isoformat())


def reset():
    _update(enabled=False, shifts={}, weeks=[], start='')
