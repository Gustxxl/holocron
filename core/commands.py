import platform
from pathlib import Path
from typing import Callable, NamedTuple
from core import editor, system
from core.settings import new_cases_path
from core.updater import update
from screens.help_screen import render_help
from screens.settings_screen import settings_screen
from ui.interface import clear_screen, pause
from core.sources import remindctl


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


def _can_edit_reminder():
    return remindctl.available() and editor.available()


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


def _cmd_reminders(raw):
    from screens.tasks_screen import tasks_screen
    tasks_screen(remindctl)


def _cmd_waypoints(raw):
    from screens.waypoints_screen import waypoints_screen
    waypoints_screen()


COMMANDS = [
    Command('keeper',     _cmd_keeper,     ('k', 'keep'), 'ask the archive in your own words'),
    Command('schedule',   _cmd_schedule,   ('sch',),      'shift schedule, week by week'),
    Command('reminders',  _cmd_reminders,  ('r',),        'tasks from Apple Reminders', remindctl.available),
    Command('waypoints',  _cmd_waypoints,  ('wp',),       'places for location reminders', remindctl.available),
    Command('favorites',  _cmd_favorites,  ('f', 'fav'),  'pinned records'),
    Command('note',       _cmd_note,       (),            'write a new note', _can_write_note),
    Command('settings',   _cmd_settings,   ('s',),        'operator name / archives / schedule / Keeper'),
    Command('system',     _cmd_system,     ('sys',),      'show OS and version'),
    Command('update',     _cmd_update,     (),            'fetch and apply a pending update'),
    Command('hyperspace', _cmd_hyperspace, ('hy',),       'go to hyperspace (any key to return)', _has_curses),
    Command('list',       _cmd_list,       ('l',)),
    Command('help',       _cmd_help,       ('h',),        'this help'),
]

HELP_SECTIONS = [
    ('Search', [
        HelpEntry('type word(s)', 'search the archive (approximate matching)'),
        HelpEntry('[number]',     'open a case from the current list'),
        HelpEntry('n / p',        'next / previous page or case'),
        HelpEntry('l / list',     'browse all cases'),
        HelpEntry('e',            'edit the open case', editor.available),
        HelpEntry('f',            'pin / unpin the open case'),
        HelpEntry('x number',     'check / uncheck a task in the open note'),
    ]),
    ('Schedule', [
        HelpEntry('n / p',        'next / previous week'),
        HelpEntry('t',            'back to this week'),
        HelpEntry('+N / -N',      'jump N weeks ahead / back'),
        HelpEntry('type a date',  'open the week of that date, e.g. 14-11'),
    ]),
    ('Reminders', [
        HelpEntry('[number]',     'open a reminder', remindctl.available),
        HelpEntry('x number',     'mark a reminder done', remindctl.available),
        HelpEntry('e',            'edit the open reminder', _can_edit_reminder),
        HelpEntry('a',            'add a reminder; #list and @place are optional', remindctl.available),
    ]),
    ('Waypoints', [
        HelpEntry('a',              'add a waypoint', remindctl.available),
        HelpEntry('t',              'trigger on arrive / leave', remindctl.available),
        HelpEntry('r number',       'geofence radius in meters', remindctl.available),
    ]),
    ('Commands', [HelpEntry(c.label, c.help, c.when) for c in COMMANDS if c.help]),
    ('Navigation', [
        HelpEntry('b',     'back to previous screen'),
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
