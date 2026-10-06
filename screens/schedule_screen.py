from datetime import datetime, timedelta
from core import schedule
from screens.schedule_settings_screen import schedule_settings
from ui.format import day_label, duration, time_range
from ui.interface import bold, clear_screen, dim, is_back, read_command, red

DAYS_VIEW = 14
BAR_WIDTH = 10
BAR_FILL = '▓'
BAR_EMPTY = '░'


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


def _upcoming(sched, now):
    today = now.date()
    lines, shown, last_week = [], set(), None
    for i in range(DAYS_VIEW):
        d = today + timedelta(days=i)
        label = day_label(d, today).ljust(10)
        away = sched.vacation_on(d)
        if away:
            if away not in shown:
                shown.add(away)
                lines.append(dim(f'{label}   vacation through {day_label(away[1], today)}'))
            continue
        week = sched.week_of(d)
        for sh in sched.shifts_on(d):
            line = f'{label}   {time_range(sh.start, sh.end)}'
            if week != last_week:
                line += dim(f'      week {week + 1}')
                last_week = week
            if sh.end <= now:
                line = dim(line)
            elif sh.start <= now:
                line = bold(line)
            lines.append(line)
    return lines or [dim(f'No shifts in the next {DAYS_VIEW} days.')]


def schedule_screen():
    while True:
        sched = schedule.load()
        now = datetime.now()
        clear_screen()
        title = 'Schedule'
        if sched.ready:
            title += f' · week {sched.week_of(now.date()) + 1} of {len(sched.weeks)}'
        print(dim(title))
        print()
        if sched.ready:
            line = duty_line(now, sched)
            if line:
                print(line)
                print()
            for ln in _upcoming(sched, now):
                print(ln)
        elif not sched.weeks:
            print('No schedule yet.')
        elif not sched.enabled:
            print('Schedule is off.')
        else:
            print('Schedule is incomplete: ' + ', '.join(sched.problems()) + '.')
        print()
        print(dim('  [s] settings   [b] back'))
        print()
        command = read_command('schedule> ').lower()
        if is_back(command):
            return
        if command in ('s', 'settings'):
            schedule_settings()
