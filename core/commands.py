import platform
from pathlib import Path
from typing import Callable, NamedTuple
from core import archives, diagnostics, editor, system
from core.settings import new_cases_path
from core.updater import update
from screens.help_screen import render_help
from screens.settings_screen import settings_screen
from ui.interface import clear_screen, pause
from core.sources import registry, remindctl
from core import keeper


HAS_CURSES = system.CURSES


class Command(NamedTuple):
    name: str
    run: Callable
    aliases: tuple = ()
    help: str = ''
    when: Callable = None

    @property
    def label(self):
        return f'{self.name} / {self.aliases[0]}' if self.aliases else self.name


class HelpEntry(NamedTuple):
    name: str
    help: str
    when: Callable = None


def _has_curses():
    return HAS_CURSES


def _can_write_note():
    folder = new_cases_path()
    return bool(folder) and Path(folder).is_dir() and editor.available()


def _ready(kind):
    source = registry.active(kind)
    return source is not None and source.available()


def _has_calendar():
    return _ready('events')


def _has_reminders():
    return _ready('tasks')


def _has_keeper():
    return bool(keeper.configured())


def _can_add_event():
    return _has_calendar() and hasattr(registry.active('events'), 'add')


def _can_edit_reminder():
    return _has_reminders() and editor.available()


def _cmd_settings(raw):
    settings_screen()


def _cmd_system(raw):
    print(f'{system.OS} {system.version()} ({platform.machine()})')
    pause()


def _cmd_update(raw):
    try:
        if update() is False:
            pause()
    except Exception as e:
        print(f'Update failed: {e}')
        pause(feedback='error')


def _cmd_help(raw):
    clear_screen()
    render_help(HELP_SECTIONS)
    pause(feedback=None)


def _cmd_list(raw):
    from screens.search_screen import search_screen
    search_screen('l')


def _cmd_note(raw):
    from screens.search_screen import create_case
    create_case()


def _cmd_tree(raw):
    from screens.tree_screen import tree_screen
    tree_screen()


def _cmd_keeper(raw):
    from screens.keeper_screen import keeper_screen
    keeper_screen()


def _cmd_schedule(raw):
    from screens.schedule_screen import schedule_screen
    schedule_screen()


def _cmd_favorites(raw):
    from screens.favorites_screen import favorites_screen
    favorites_screen()


def _cmd_hyperspace(raw):
    from ui.hyperspace import hyperspace
    hyperspace()


def _cmd_calendar(raw):
    from screens.events_screen import events_screen
    events_screen(registry.active('events'))


def _cmd_reminders(raw):
    from screens.tasks_screen import tasks_screen
    tasks_screen(registry.active('tasks'))


def _cmd_waypoints(raw):
    from screens.waypoints_screen import waypoints_screen
    waypoints_screen()


def _cmd_check(raw):
    from screens.diagnostics_screen import diagnostics_screen
    diagnostics_screen()



COMMANDS = [
    Command('keeper',     _cmd_keeper,     ('k', 'keep'), 'ask the archive in your own words', _has_keeper),
    Command('schedule',   _cmd_schedule,   ('sch',),      'shift schedule, week by week'),
    Command('calendar',   _cmd_calendar,   ('c', 'cal'),  'upcoming calendar events', _has_calendar),
    Command('reminders',  _cmd_reminders,  ('r',),        'open reminders', _has_reminders),
    Command('waypoints',  _cmd_waypoints,  ('wp',),       'places for location reminders', remindctl.available),
    Command('favorites',  _cmd_favorites,  ('f', 'fav'),  'pinned records'),
    Command('tree',       _cmd_tree,       (),            'browse the archive by folder', archives.is_loaded),
    Command('note',       _cmd_note,       (),            'write a new note', _can_write_note),
    Command('settings',   _cmd_settings,   ('s',),        'operator name / archives / schedule / Keeper'),
    Command('system',     _cmd_system,     ('sys',),      'show OS and version'),
    Command('check',      _cmd_check,      (),            'run diagnostics and tests', diagnostics.available),
    Command('update',     _cmd_update,     (),            'fetch and apply a pending update'),
    Command('hyperspace', _cmd_hyperspace, ('hy',),       'go to hyperspace (any key to return)', _has_curses),
    Command('list',       _cmd_list,       ('l',)),
    Command('help',       _cmd_help,       ('h',),        'show commands'),
]

HELP_SECTIONS = [
    ('Search', [
        HelpEntry('type word(s)', 'search the archive (approximate matching)'),
        HelpEntry('a; b',         'search for several things at once (s > Archive > Search separator)'),
        HelpEntry('[number]',     'open a case from the current list'),
        HelpEntry('n / p',        'next / previous page or case'),
        HelpEntry('nn / pp',      'last / first page or case'),
        HelpEntry('l / list',     'browse all cases'),
        HelpEntry('e',            'edit the open case', editor.available),
        HelpEntry('f',            'pin / unpin the open case'),
        HelpEntry('x number',     'check / uncheck a task in the open note'),
        HelpEntry('m',            'move the open kanban card to another list'),
        HelpEntry('a',            'add a card to the open kanban list or to the list of the open card', editor.available),
        HelpEntry('k', 'ask Keeper about this record', _has_keeper),
        HelpEntry('j number', 'jump to a linked note'),
    ]),
    ('Schedule', [
        HelpEntry('n / p',        'next / previous week'),
        HelpEntry('t',            'back to this week'),
        HelpEntry('+N / -N',      'jump N weeks ahead / back'),
        HelpEntry('type a date',  'open the week of that date, e.g. 14-11'),
    ]),
    ('Calendar', [
        HelpEntry('[number]', 'open an event', _has_calendar),
        HelpEntry('a',        'add an event: title, time, optional date and #calendar', _can_add_event),
    ]),
    ('Reminders', [
        HelpEntry('[number]',     'open a reminder', _has_reminders),
        HelpEntry('x number',     'mark a reminder done', _has_reminders),
        HelpEntry('e',            'edit the open reminder', _can_edit_reminder),
        HelpEntry('a',            'add a reminder; #list and @place are optional', _has_reminders),
    ]),
    ('Waypoints', [
        HelpEntry('a',              'add a waypoint', remindctl.available),
        HelpEntry('t',              'trigger on arrive / leave', remindctl.available),
        HelpEntry('r number',       'geofence radius in meters', remindctl.available),
    ]),
    ('Commands', [HelpEntry(c.label, c.help, c.when) for c in COMMANDS if c.help]),
    ('Navigation', [
        HelpEntry('b',     'back to previous screen'),
        HelpEntry('w',     'back to the main screen'),
        HelpEntry('Enter', 'refresh the current screen'),
        HelpEntry('q',     'quit'),
    ]),
]

_INDEX = {name: c for c in COMMANDS for name in (c.name, *c.aliases)}


def lookup(raw):
    command = _INDEX.get(raw.strip().lower())
    if command and (command.when is None or command.when()):
        return command
    return None
