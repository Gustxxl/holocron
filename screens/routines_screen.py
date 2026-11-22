from datetime import datetime
from core import editor, routines, schedule, sources, zones
from screens.help_screen import show_help
from screens.sources_screen import source_setup, unreadable
from ui.format import day_label
from ui.interface import clear_screen, confirm, dim, error, haptic, is_back, nav_line, pause, pick, read_command

RULES = {'shift': 'on shift', 'daily': 'every day', 'manual': 'by hand'}


def routines_screen(source):
    if not source_setup(source):
        return
    lists = source.lists()
    if lists is None:
        unreadable(source)
        return
    while True:
        items = routines.load()
        frame = '\n'.join(_frame(items))
        clear_screen()
        print(frame)
        low = read_command('routines> ').lower()
        if is_back(low):
            return
        if low in ('h', 'help'):
            show_help()
        elif low == 'a':
            text = read_command('text> ')
            if text:
                _add(source, text, lists)
        elif pick(low, len(items)):
            _open(source, lists, int(low))


def _frame(items):
    lines = [dim('Routines'), '']
    if not items:
        lines += [dim('No routines'), '']
    width = max((len(r['title']) for r in items), default=0)
    digits = len(str(len(items)))
    for i, r in enumerate(items, 1):
        lines.append(f'  {dim(str(i).rjust(digits))} {r["title"].ljust(width)}   {dim(_when(r) + " · " + RULES[r["rule"]])}')
    if items:
        lines.append('')
    nav = [('number', 'open', '#', 'open')] if items else []
    nav += [('a', 'add'), ('b', 'back'), ('h', 'help')]
    lines += [dim(nav_line(nav)), '']
    return lines


def _open(source, lists, number):
    while True:
        items = routines.load()
        if not 1 <= number <= len(items):
            return
        routine, sched, now = items[number - 1], schedule.load(), datetime.now()
        frame = '\n'.join(_card(routine, number, len(items), now, sched, lists))
        clear_screen()
        print(frame)
        command = read_command('routine> ').lower()
        if is_back(command):
            return
        if command in ('h', 'help'):
            show_help()
        elif command == 'r':
            _remind(source, number, now)
        elif command == 't':
            routines.change(number, rule=routines.next_rule(routine['rule']))
            haptic('toggle')
        elif command == 'z' and sched.zone:
            routines.change(number, zone='' if routine['zone'] else sched.zone)
            haptic('toggle')
        elif command == 'e' and editor.available():
            _edit(number, routine, lists)
        elif command == 'd':
            if confirm(f'Delete {routine["title"]}?'):
                routines.remove(number)
                haptic('success')
                return
        elif command == 'n' and number < len(items):
            number += 1
        elif command == 'p' and number > 1:
            number -= 1
        elif pick(command, len(items)):
            number = int(command)


def _card(routine, number, total, now, sched, lists):
    lines = [dim(f'── {number}/{total}  Routine ' + '─' * 20), '', routine['title']]
    when = _when(routine)
    if routine['zone'] and zones.differs(routine['zone']):
        when += f' · {routines.soonest(routine, now):%H:%M} here'
    lines += [when, dim(_rule(routine, now, sched))]
    name = _list_name(lists, routine['list'])
    if name:
        lines.append(dim(f'#{name}'))
    nav = [('r', 'remind now'), ('t', 'on shift / every day / by hand', 't', 'rule')]
    if sched.zone:
        nav.append(('z', 'team / my time', 'z', 'zone'))
    if editor.available():
        nav.append(('e', 'edit'))
    nav.append(('d', 'delete'))
    if number < total:
        nav.append(('n', 'next'))
    if number > 1:
        nav.append(('p', 'prev'))
    nav += [('b', 'back'), ('h', 'help')]
    lines += ['', dim(nav_line(nav)), '']
    return lines


def _when(routine):
    return f'{routine["time"]} {zones.label(routine["zone"])}' if routine['zone'] else routine['time']


def _rule(routine, now, sched):
    if routine['rule'] == 'manual':
        return RULES['manual']
    moment = routines.upcoming(routine, now, sched)
    if moment is None:
        return f'{RULES[routine["rule"]]} · schedule not set'
    return f'{RULES[routine["rule"]]} · next {day_label(moment.date(), now.date())} {moment:%H:%M}'


def _list_name(lists, list_id):
    return next((l['title'] for l in lists if l['id'] == list_id), '')


def _remind(source, number, now):
    moment, problem = routines.remind(source, number, now)
    if moment is None:
        error(problem)
        return
    clear_screen()
    print(dim(f'{problem or "Set"} for {day_label(moment.date(), now.date())} {moment:%H:%M}'))
    pause(feedback='warning' if problem else 'success')


def _add(source, text, lists):
    draft, problem = routines.parse(text, lists, sources.default(source.KEY, lists))
    if problem:
        error(problem)
        return
    if routines.add(draft['title'], draft['time'], draft['list'], schedule.load().zone or ''):
        haptic('success')
    else:
        error('Could not save the routine')


def _edit(number, routine, lists):
    name = _list_name(lists, routine['list'])
    text = editor.edit_text(f'{routine["title"]} {routine["time"]}' + (f' #{name}' if name else ''))
    if text is None:
        error('Could not open the editor')
        return
    draft, problem = routines.parse(' '.join(text.split()), lists, routine['list'])
    if problem:
        error(problem)
        return
    found = {key: value for key, value in draft.items() if value != routine[key]}
    if found:
        routines.change(number, **found)
        haptic('success')
