import re
from datetime import datetime, timedelta
from core import schedule
from core.commands import HELP_SECTIONS
from core.dates import monday, parse_date
from screens.help_screen import render_help
from screens.schedule_settings_screen import schedule_settings
from ui.format import day_label, duration, plural, time_range, week_span
from ui.interface import bold, clear_screen, dim, error, is_back, pause, read_command, red

BAR_WIDTH = 10
BAR_FILL = '▓'
BAR_EMPTY = '░'
LABEL = 6
MAX_OFFSET = 520

_JUMP_RE = re.compile(r'[+-]\d+')


def _bar(fraction):
    filled = min(BAR_WIDTH, max(0, round(fraction * BAR_WIDTH)))
    return dim(BAR_FILL * filled + BAR_EMPTY * (BAR_WIDTH - filled))


def duty_line(now=None, sched=None):
    now = now or datetime.now()
    sched = sched or schedule.load()
    st = sched.status(now)
    if not st:
        return None
    if st.on:
        sh = st.shift
        fraction = (now - sh.start) / (sh.end - sh.start)
        rest = dim(f'{fraction:.0%} · {duration(sh.end - now)} left')
        return f'{red("● ON DUTY")}  {_bar(fraction)}  {rest}'
    if st.vacation:
        end = st.vacation[1]
        tail = 'last day' if end == now.date() else f'through {day_label(end, now.date())}'
        return dim(f'● ON LEAVE · {tail}')
    if st.shift:
        sh = st.shift
        when = day_label(sh.start.date(), now.date())
        return dim(f'● OFF DUTY · next {when} {time_range(sh.start, sh.end)} · in {duration(sh.start - now)}')
    return None


def _hours(delta):
    h, m = divmod(int(delta.total_seconds() // 60), 60)
    return f'{h}h{m:02d}' if m else f'{h}h'


def _relative(offset):
    if offset == 0:
        return 'this week'
    if offset == 1:
        return 'next week'
    if offset == -1:
        return 'last week'
    return f'in {offset} weeks' if offset > 0 else f'{-offset} weeks ago'


def _week(sched, first, now):
    today = now.date()
    lines, count, total = [], 0, timedelta()
    for i in range(7):
        d = first + timedelta(days=i)
        label = ('today' if d == today else f'{d:%a %d}').ljust(LABEL)
        head = dim(label) if d < today else label
        if sched.vacation_on(d):
            lines.append(f'{head}   ' + dim('vacation'))
            continue
        found = sched.shifts_on(d)
        if not found:
            lines.append(f'{head}   ' + dim('—'))
            continue
        for sh in found:
            count += 1
            total += sh.end - sh.start
            line = f'{label}   {time_range(sh.start, sh.end)}'
            if sh.end <= now:
                line = dim(line)
            elif sh.start <= now:
                line = bold(line)
            lines.append(line)
            label = ' ' * LABEL
    summary = f'{plural(count, "shift")} · {_hours(total)}' if count else 'No shifts.'
    return lines, summary


def _show_week(sched, now, offset):
    first = monday(now.date()) + timedelta(weeks=offset)
    head = week_span(first)
    if len(sched.weeks) > 1:
        head = f'Week {sched.week_of(first) + 1} of {len(sched.weeks)}   {head}'
    print(head + dim(f'   {_relative(offset)}'))
    print()
    lines, summary = _week(sched, first, now)
    for ln in lines:
        print(ln)
    print()
    print(dim(summary))


def _clamp(offset):
    return max(-MAX_OFFSET, min(MAX_OFFSET, offset))


def schedule_screen():
    offset = 0
    while True:
        sched = schedule.load()
        now = datetime.now()
        clear_screen()
        print(dim('Schedule'))
        print()
        if sched.ready:
            line = duty_line(now, sched)
            if line:
                print(line)
                print()
            _show_week(sched, now, offset)
        elif not sched.weeks:
            print('No schedule yet.')
        elif not sched.enabled:
            print('Schedule is off.')
        else:
            print('Schedule is incomplete: ' + ', '.join(sched.problems()) + '.')
        print()
        nav = '  '
        if sched.ready:
            nav += '[n] next   [p] prev   '
            nav += '[t] this week   ' if offset else ''
        nav += '[b] back   [h] help'
        print(dim(nav))
        print()
        command = read_command('schedule> ').lower()
        if is_back(command):
            return
        if command in ('h', 'help'):
            clear_screen()
            render_help(HELP_SECTIONS)
            pause()
            continue
        if command in ('s', 'settings'):
            schedule_settings()
            continue
        if not command or not sched.ready:
            continue
        if command == 'n':
            offset = _clamp(offset + 1)
        elif command == 'p':
            offset = _clamp(offset - 1)
        elif command == 't':
            offset = 0
        elif _JUMP_RE.fullmatch(command):
            offset = _clamp(offset + int(command))
        else:
            d = parse_date(command)
            if not d:
                error('Date not recognized. Example: 14-11')
                continue
            offset = _clamp((monday(d) - monday(now.date())).days // 7)
