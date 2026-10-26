from datetime import datetime
from core import dates, events, sources
from screens.help_screen import show_help
from screens.sources_screen import lists_screen, source_setup, unreadable
from ui.format import day_label, time_range
from ui.interface import clear_screen, dim, error, haptic, hyperlink, is_back, pause, read_command, nav_line, underline


def events_screen(source):
    if not source_setup(source):
        return
    while True:
        lists = source.lists()
        found = source.items() if lists is not None else None
        if found is None:
            unreadable(source)
            return
        now = datetime.now()
        chosen = sources.selected(source.KEY)
        flat = events.upcoming(found, chosen, now)
        frame = '\n'.join(_frame(source, chosen, flat, now))
        clear_screen()
        print(frame)
        low = read_command(f'{source.NAME.lower()}> ').lower()
        if is_back(low):
            return
        if low in ('h', 'help'):
            show_help()
        elif low in ('s', 'settings'):
            lists_screen(source)
        elif low == 'a' and hasattr(source, 'add'):
            text = read_command('text> ')
            if text:
                _add(source, text, lists, chosen)
        elif low.isdigit() and 1 <= int(low) <= len(flat):
            _open(flat, int(low))


def agenda(source, now=None):
    chosen = sources.selected(source.KEY)
    limit = sources.option(source.KEY, 'shown', source.SHOWN)
    if not chosen or not limit or not source.available():
        return []
    found = source.items()
    if not found:
        return []
    now = now or datetime.now()
    ahead = sources.option(source.KEY, 'ahead', source.AHEAD)
    shown = [e for e in events.upcoming(found, chosen, now) if dates.within(e['start'], now, ahead)]
    lines = []
    for event in shown[:limit]:
        lines.append(f'◇ {event['title']}' + dim(f' · {_when(event, now)} #{event['list_name']}'))
        link = events.meeting(event)
        if link:
            lines.append(f'  {dim(underline(hyperlink(link, 'link')))}')
    if len(shown) > limit:
        lines.append(dim(f'+{len(shown) - limit} more'))
    return lines


def _frame(source, chosen, flat, now):
    lines = [dim(source.NAME), '']
    if not chosen:
        lines += [dim(f'No {source.LISTS} selected'), '']
    elif not flat:
        lines += [dim('No upcoming events'), '']
    digits = len(str(len(flat)))
    n = 0
    for day, items in events.by_day(flat, now):
        lines.append(dim(day_label(day, now.date())))
        for event in items:
            n += 1
            lines.append(f'  {dim(str(n).rjust(digits))} {_time(event, now).ljust(11)}  {event["title"]}')
            link = events.meeting(event)
            if link:
                lines.append(f'  {" " * digits} {" " * 11}  {dim(underline(link))}')
        lines.append('')
    nav = [('number', 'open', '#', 'open')] if n else []
    nav += [('a', 'add')] if hasattr(source, 'add') else []
    nav += [('s', source.LISTS), ('b', 'back'), ('h', 'help')]
    lines += [dim(nav_line(nav)), '']
    return lines


def _open(flat, number):
    while 1 <= number <= len(flat):
        event = flat[number - 1]
        frame = '\n'.join(_card(event, number, len(flat), datetime.now()))
        clear_screen()
        print(frame)
        command = read_command('event> ').lower()
        if is_back(command):
            return
        if command in ('h', 'help'):
            show_help()
        elif command == 'n' and number < len(flat):
            number += 1
        elif command == 'p' and number > 1:
            number -= 1
        elif command == 'nn':
            number = len(flat)
        elif command == 'pp':
            number = 1
        elif command.isdigit() and 1 <= int(command) <= len(flat):
            number = int(command)


def _card(event, number, total, now):
    lines = [dim(f'── {number}/{total}  #{event['list_name']} ' + '─' * 20), '', event['title'], _when(event, now)]
    if event['place']:
        lines.append(dim(event['place']))
    link = events.link(event)
    if link and link != event['place']:
        lines.append(dim(underline(link)))
    if event['notes']:
        lines += ['', event['notes']]
    nav = []
    if number < total:
        nav.append(('n', 'next'))
    if number > 1:
        nav.append(('p', 'prev'))
    nav += [('b', 'back'), ('h', 'help')]
    lines += ['', dim(nav_line(nav)), '']
    return lines


def _add(source, text, lists, chosen):
    draft, problem = events.parse_add(text, lists, sources.default(source.KEY, lists))
    if problem:
        error(problem)
        return
    if not source.add(draft['title'], draft['list'], draft['start'], draft['end']):
        error('Could not add the event')
        return
    if draft['list'] in chosen:
        haptic('success')
        return
    name = next((l['title'] for l in lists if l['id'] == draft['list']), '')
    clear_screen()
    print(dim(f'Added to #{name} — hidden in settings'))
    pause()


def _time(event, now):
    if event['all_day']:
        return 'all day'
    if event['start'] <= now:
        return f'now – {event["end"]:%H:%M}'
    return time_range(event['start'], event['end'])


def _when(event, now):
    if event['start'] <= now and not event['all_day']:
        return _time(event, now)
    return f'{day_label(max(event["start"].date(), now.date()), now.date())} {_time(event, now)}'
