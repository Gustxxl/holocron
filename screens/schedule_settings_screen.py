from datetime import date, datetime, timezone
from core import clocks, schedule, zones
from core.dates import DAYS, monday, parse_date, parse_periods
from ui.format import date_span, day_runs, days_summary, periods, plural, week_span
from core.system import copy_text
from ui.interface import clear_screen, confirm, dim, error, is_back, pause, read_command, red, nav_line
import re


def _value(text):
    return dim(text or '—')


def _current_week(sched):
    if not sched.weeks or sched.start is None:
        return None
    return sched.week_of(date.today())


def _vacations_value(sched):
    upcoming = [v for v in sched.vacations if v[1] >= date.today()]
    if not upcoming:
        return ''
    text = date_span(*upcoming[0])
    return f'{text}   +{len(upcoming) - 1} more' if len(upcoming) > 1 else text


def _pick_days(text):
    picked = set()
    for part in text.replace(',', ' ').split():
        a, sep, b = part.partition('-')
        if not a.isdigit() or (sep and not b.isdigit()):
            return []
        first, last = int(a), int(b) if sep else int(a)
        if not 1 <= first <= last <= 7:
            return []
        picked.update(range(first - 1, last))
    return sorted(picked)


def _print_weeks(weeks, current=None):
    width = len(str(len(weeks)))
    for i, days in enumerate(weeks, 1):
        mark = dim('  ✓') if i - 1 == current else ''
        print(f'{i:>{width}}) Week {i:<{width}}   {_value(days_summary(days))}{mark}')


def _hours_screen(index, picked):
    while True:
        days = schedule.load().week_days()[index]
        values = {tuple(map(tuple, days[i])) if days[i] else None for i in picked}
        clear_screen()
        print(dim(f'Settings > Schedule > Weeks > Week {index + 1} > {day_runs(picked)}'))
        print()
        if len(values) > 1:
            print('Hours: different')
        else:
            only = days[picked[0]]
            print(f'Hours: {periods(only) if only else "day off"}')
        print()
        print(dim('  [7-15] set hours   [-] day off   [b] back'))
        print()
        command = read_command('hours> ')
        if not command or is_back(command):
            return
        if command == '-':
            value = None
        else:
            value = parse_periods(command)
            if not value:
                error('Hours not recognized. Example: 7-15 or 20-7')
                continue
        weeks = schedule.load().week_days()
        for i in picked:
            weeks[index][i] = value
        schedule.save_weeks(weeks)
        return


def _week_screen(index):
    while True:
        weeks = schedule.load().week_days()
        if index >= len(weeks):
            return
        clear_screen()
        print(dim(f'Settings > Schedule > Weeks > Week {index + 1}'))
        print()
        for i, items in enumerate(weeks[index]):
            print(f'{i + 1}) {DAYS[i]}   {_value(periods(items) if items else "")}')
        print()
        print(dim('  [number] set hours   [1-5] several days   [b] back'))
        print()
        command = read_command('day> ')
        if is_back(command):
            return
        picked = _pick_days(command)
        if picked:
            _hours_screen(index, picked)


def _weeks_screen():
    while True:
        weeks = schedule.load().week_days()
        clear_screen()
        print(dim('Settings > Schedule > Weeks'))
        print()
        zone = schedule.load().zone
        if zone:
            print(dim(f'Hours in {zones.label(zone)} time'))
            print()
        if weeks:
            _print_weeks(weeks)
        else:
            print('No weeks yet.')
        print()
        if weeks:
            print(dim('  [number] open week   [+] add week   [-] remove last   [b] back'))
        else:
            print(dim('  [+] add week   [b] back'))
        print()
        command = read_command('weeks> ')
        if is_back(command):
            return
        if command == '+':
            if len(weeks) >= schedule.MAX_WEEKS:
                error(f'The cycle can be at most {schedule.MAX_WEEKS} weeks.')
                continue
            schedule.save_weeks(weeks + [[None] * 7])
            _week_screen(len(weeks))
        elif command == '-' and weeks:
            if confirm(f'Remove week {len(weeks)}?'):
                schedule.save_weeks(weeks[:-1])
        elif command.isdigit() and 1 <= int(command) <= len(weeks):
            _week_screen(int(command) - 1)


def _current_week_screen():
    while True:
        sched = schedule.load()
        weeks = sched.week_days()
        clear_screen()
        print(dim('Settings > Schedule > Current week'))
        print()
        print(f'This week: {week_span(monday(date.today()))}')
        print()
        if weeks:
            _print_weeks(weeks, _current_week(sched))
        else:
            print('No weeks yet.')
        print()
        print(dim('  [number] select   [b] back' if weeks else '  [b] back'))
        print()
        command = read_command('week> ')
        if is_back(command):
            return
        if command.isdigit() and 1 <= int(command) <= len(weeks):
            schedule.set_current_week(int(command))
            return


def _add_vacation(vacations):
    print(dim('  01-11-2026, today or tomorrow'))
    raw = read_command('from> ')
    if not raw:
        return
    a = parse_date(raw)
    if not a:
        error('Date not recognized. Example: 01-11-2026')
        return
    print(dim('  Enter for a single day'))
    raw = read_command('to> ')
    b = parse_date(raw) if raw else a
    if not b:
        error('Date not recognized. Example: 14-11-2026')
        return
    if b < a:
        error('The last day is before the first.')
        return
    schedule.save_vacations(list(vacations) + [(a, b)])


def _vacations_screen():
    while True:
        vacations = schedule.load().vacations
        today = date.today()
        clear_screen()
        print(dim('Settings > Schedule > Vacations'))
        print()
        if vacations:
            width = len(str(len(vacations)))
            for i, (a, b) in enumerate(vacations, 1):
                line = f'{i:>{width}}) {date_span(a, b):<28}'
                length = plural((b - a).days + 1, 'day')
                print(dim(line + length) if b < today else line + dim(length))
        else:
            print('No vacations.')
        print()
        if vacations:
            print(dim('  [+] add   [number] remove   [b] back'))
        else:
            print(dim('  [+] add   [b] back'))
        print()
        command = read_command('vacation> ')
        if is_back(command):
            return
        if command == '+':
            _add_vacation(vacations)
        elif command.isdigit() and 1 <= int(command) <= len(vacations):
            i = int(command) - 1
            if confirm(f'Remove {date_span(*vacations[i])}?'):
                schedule.save_vacations(vacations[:i] + vacations[i + 1:])


def _share_screen(sched):
    if not sched.weeks:
        error('Nothing to share yet. Add weeks first.')
        return
    code = schedule.share_code(sched)
    clear_screen()
    print(dim('Settings > Schedule > Share'))
    print()
    print(code)
    print()
    if copy_text(code):
        print(dim('Copied. Send it to someone with Holocron: Settings > Schedule > Import.'))
    else:
        print(dim('Copy the code and send it to someone with Holocron: Settings > Schedule > Import.'))
    pause()


def _import_screen():
    while True:
        clear_screen()
        print(dim('Settings > Schedule > Import'))
        print()
        print('Paste a schedule code.')
        print()
        print(dim('  [paste] code   [b] back'))
        print()
        raw = read_command('code> ')
        if not raw or is_back(raw):
            return
        sched = schedule.read_code(raw)
        if not sched:
            error('Code not recognized. Ask for a new one.')
            continue
        clear_screen()
        print(dim('Settings > Schedule > Import'))
        print()
        _print_weeks(sched.week_days())
        if len(sched.weeks) > 1:
            print()
            current = _current_week(sched)
            print(f'Current week: {_value(f"{current + 1} of {len(sched.weeks)}" if current is not None else "")}')
        print()
        print(dim('Your vacations stay as they are.'))
        print()
        if confirm('Replace your schedule?'):
            schedule.import_schedule(sched)
        return


def _toggle(sched):
    if sched.enabled:
        schedule.set_enabled(False)
        return
    issues = sched.problems()
    if issues:
        error('Cannot turn on: ' + ', '.join(issues) + '.')
        return
    schedule.set_enabled(True)


ZONE_PAGE = 15
_DROP_RE = re.compile(r'd\s*(\d+)')


def _zone_value(sched):
    if not sched.zone:
        return _value('')
    return _value(zones.label(sched.zone)) if zones.get(sched.zone) else red('not found')


def _zone_rows(found, page, now):
    start = page * ZONE_PAGE
    chunk = found[start:start + ZONE_PAGE]
    digits = len(str(len(found)))
    names = [n.replace('_', ' ') for n in chunk]
    col = max(len(n) for n in names)
    return [f'  {dim(str(i).rjust(digits))} {name.ljust(col)}   '
            f'{dim(zones.utc(zones.offset(n, now)))}   {dim(zones.clock(n, now))}'
            for i, (n, name) in enumerate(zip(chunk, names), start + 1)]


def _clock_rows(items, now):
    digits = len(str(len(items)))
    col = max(len(c['name']) for c in items)
    rows = []
    for i, c in enumerate(items, 1):
        info = (f'{dim(zones.utc(zones.offset(c["zone"], now)))}   {dim(zones.clock(c["zone"], now))}'
                if zones.get(c['zone']) else red('not found'))
        rows.append(f'  {dim(str(i).rjust(digits))} {c["name"].ljust(col)}   {info}')
    return rows


def _zone_frame(sched, items, query, found, page, now, adding):
    head = 'Settings > Schedule > Time zone' + (' > Add clock' if adding else '')
    head += f'   "{query}"' if found else ''
    lines = [dim(head), '']
    if found:
        pages = -(-len(found) // ZONE_PAGE)
        lines += _zone_rows(found, page, now)
        nav = [('number', 'choose', '#', 'choose')]
        if page + 1 < pages:
            nav.append(('n', 'next'))
        if page > 0:
            nav.append(('p', 'prev'))
        nav.append(('b', 'back'))
    else:
        mine = now.astimezone()
        lines.append(f'  This computer   {dim(zones.utc(mine.utcoffset()))}   {dim(f"{mine:%H:%M}")}')
        if sched.zone and zones.get(sched.zone):
            lines.append(f'  Schedule        {zones.label(sched.zone)}   '
                         f'{dim(zones.utc(zones.offset(sched.zone, now)))}   {dim(zones.clock(sched.zone, now))}')
        elif sched.zone:
            lines.append(f'  Schedule        {sched.zone}   {red("not found")}')
        else:
            lines.append(f'  Schedule        {dim("same as this computer")}')
        if items:
            lines += ['', 'Clocks', *_clock_rows(items, now)]
        nav = [('type', 'city or UTC offset', 'type', 'city/UTC'), ('a', 'add clock', 'a', 'clock')]
        if items:
            nav.append(('d number', 'remove', 'd#', 'remove'))
        if sched.zone:
            nav.append(('c', 'clear'))
        nav.append(('b', 'back'))
    lines += ['', dim(nav_line(nav)), '']
    return '\n'.join(lines)


def _add_clock(zone):
    print(dim(f'  Enter for {zones.label(zone)}'))
    clocks.add(zone, read_command('name> '))


def _search(text):
    if not zones.names():
        error('Time zones are not available on this system.')
        return []
    result = zones.find(text)
    if not result:
        error(f'No time zone {text}')
    return result


def _zone_screen():
    query, found, page, adding = '', [], 0, False
    while True:
        now = datetime.now(timezone.utc)
        items = clocks.load()
        pages = max(1, -(-len(found) // ZONE_PAGE))
        page = max(0, min(page, pages - 1))
        frame = _zone_frame(schedule.load(), items, query, found, page, now, adding)
        clear_screen()
        print(frame)
        command = read_command('zone> ')
        low = command.lower()
        if is_back(command):
            if not found:
                return
            query, found, adding = '', [], False
            continue
        if not command:
            continue
        if found and command.isdigit():
            n = int(command)
            if 1 <= n <= len(found):
                (_add_clock if adding else schedule.set_zone)(found[n - 1])
                query, found, adding = '', [], False
            continue
        if found and low in ('n', 'p'):
            page += 1 if low == 'n' else -1
            continue
        if not found:
            drop = _DROP_RE.fullmatch(low)
            if drop:
                clocks.remove(int(drop.group(1)))
                continue
            if low == 'c':
                schedule.set_zone('')
                continue
            if low == 'a':
                command, adding = read_command('city> '), True
                if not command:
                    adding = False
                    continue
        result = _search(command)
        if len(result) == 1:
            (_add_clock if adding else schedule.set_zone)(result[0])
            adding = False
        elif result:
            query, found, page = command, result, 0
        else:
            adding = False


def schedule_settings():
    while True:
        sched = schedule.load()
        current = _current_week(sched)
        n = len(sched.weeks)
        clear_screen()
        print(dim('Settings > Schedule'))
        print()
        print(f'1) Weeks          {_value(str(n) if n else "")}')
        print(f'2) Current week   {_value(f"{current + 1} of {n}" if current is not None else "")}')
        print(f'3) Vacations      {_value(_vacations_value(sched))}')
        print(f'4) Time zone      {_zone_value(sched)}')
        print(f'5) Enabled        {dim("on" if sched.enabled else "off")}')
        print('6) Share')
        print('7) Import')
        print()
        print(dim('  [number] open section   [b] back'))
        print()
        command = read_command('schedule> ')
        if is_back(command):
            return
        if command == '1':
            _weeks_screen()
        elif command == '2':
            _current_week_screen()
        elif command == '3':
            _vacations_screen()
        elif command == '4':
            _zone_screen()
        elif command == '5':
            _toggle(sched)
        elif command == '6':
            _share_screen(sched)
        elif command == '7':
            _import_screen()
