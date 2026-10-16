import re
from core import editor, waypoints
from core.sources import remindctl
from screens.help_screen import show_help
from ui.interface import clear_screen, confirm, dim, error, haptic, is_back, read_command, nav_line

_RADIUS_RE = re.compile(r'r\s*(\d+)')


def waypoints_screen():
    while True:
        points = waypoints.load()
        items = remindctl.items() or []
        frame = '\n'.join(_frame(points, waypoints.linked(items, points)))
        clear_screen()
        print(frame)
        command = read_command('waypoints> ').lower()
        if is_back(command):
            return
        if command in ('h', 'help'):
            show_help()
        elif command == 'a':
            _add()
        elif command.isdigit() and 1 <= int(command) <= len(points):
            _open(list(points), int(command), items)


def _frame(points, linked):
    lines = [dim('Waypoints'), '']
    if not points:
        lines += [dim('No waypoints'), '']
    width = max((len(name) for name in points), default=0) + 1
    digits = len(str(len(points)))
    for i, (name, point) in enumerate(points.items(), 1):
        count = len(linked[name])
        tail = dim(f'   {count} reminder' + ('' if count == 1 else 's')) if count else ''
        lines.append(f'  {dim(str(i).rjust(digits))} {("@" + name).ljust(width)}   {dim(point["address"])}{tail}')
    if points:
        lines.append('')
    nav = [('number', 'open', '#', 'open')] if points else []
    nav += [('a', 'add'), ('b', 'back'), ('h', 'help')]
    lines += [dim(nav_line(nav)), '']
    return lines


def _add():
    name = waypoints.norm(read_command('name> '))
    if not name:
        return
    if not waypoints.valid(name):
        error('Name must be one word')
        return
    if name in waypoints.load() and not confirm(f'@{name} exists. Replace the address?'):
        return
    address = read_command('address> ')
    if not address:
        return
    if waypoints.put(name, address):
        haptic('success')
    else:
        error('Could not save the waypoint')


def _open(names, number, items):
    while 1 <= number <= len(names):
        points = waypoints.load()
        name = names[number - 1]
        point = points.get(name)
        if point is None:
            return
        here = waypoints.linked(items, points)[name]
        frame = '\n'.join(_card(name, point, here, number, len(names)))
        clear_screen()
        print(frame)
        command = read_command('waypoint> ').lower()
        radius = _RADIUS_RE.fullmatch(command)
        if is_back(command):
            return
        if command in ('h', 'help'):
            show_help()
        elif command == 'e' and editor.available():
            names[number - 1] = _edit(name, point)
        elif command == 't':
            flip = 'leaving' if point['proximity'] == 'arriving' else 'arriving'
            waypoints.change(name, proximity=flip)
            haptic('toggle')
        elif radius and int(radius.group(1)) > 0:
            waypoints.change(name, radius=int(radius.group(1)))
            haptic('toggle')
        elif command == 'd':
            if confirm(f'Delete @{name}?'):
                waypoints.remove(name)
                haptic('success')
                return
        elif command == 'n' and number < len(names):
            number += 1
        elif command == 'p' and number > 1:
            number -= 1
        elif command.isdigit():
            number = int(command)


def _card(name, point, here, number, total):
    lines = [dim(f'── {number}/{total}  Waypoint ' + '─' * 20), '',
             f'@{name}', point['address'], dim(f'{point["proximity"]}   {point["radius"]} m')]
    if here:
        lines += ['', *(f'○ {t["title"]}' for t in here)]
    nav = [('e', 'edit')] if editor.available() else []
    nav += [('t', 'arrive / leave', 't', 'arrive/leave'),
            ('r number', 'radius', 'r#', 'radius'),
            ('d', 'delete')]
    if number < total:
        nav.append(('n', 'next'))
    if number > 1:
        nav.append(('p', 'prev'))
    nav += [('b', 'back'), ('h', 'help')]
    lines += ['', dim(nav_line(nav)), '']
    return lines


def _edit(name, point):
    text = editor.edit_text(f'{name}\n{point["address"]}')
    if text is None:
        error('Could not open the editor')
        return name
    new, address, problem = waypoints.parse_edit(text)
    if problem:
        error(problem)
        return name
    if new == name and address == point['address']:
        return name
    if new != name and not waypoints.rename(name, new):
        error(f'@{new} already exists')
        return name
    waypoints.put(new, address)
    haptic('success')
    return new
