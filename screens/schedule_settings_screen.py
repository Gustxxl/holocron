from datetime import date

from core import schedule
from core.dates import DAYS, monday, parse_date, parse_periods
from ui.format import date_span, day_runs, days_summary, periods, plural, week_span
from ui.interface import clear_screen, confirm, dim, error, is_back, read_command


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
        if weeks:
            width = len(str(len(weeks)))
            for i, days in enumerate(weeks, 1):
                print(f'{i:>{width}}) Week {i:<{width}}   {_value(days_summary(days))}')
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
        current = _current_week(sched)
        clear_screen()
        print(dim('Settings > Schedule > Current week'))
        print()
        print(f'This week: {week_span(monday(date.today()))}')
        print()
        if weeks:
            width = len(str(len(weeks)))
            for i, days in enumerate(weeks, 1):
                mark = dim('  ✓') if i - 1 == current else ''
                print(f'{i:>{width}}) Week {i:<{width}}   {_value(days_summary(days))}{mark}')
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


def _toggle(sched):
    if sched.enabled:
        schedule.set_enabled(False)
        return
    issues = sched.problems()
    if issues:
        error('Cannot turn on: ' + ', '.join(issues) + '.')
        return
    schedule.set_enabled(True)


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
        print(f'4) Enabled        {dim("on" if sched.enabled else "off")}')
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
            _toggle(sched)
