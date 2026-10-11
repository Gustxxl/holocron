import importlib.util
import platform
from typing import Callable, NamedTuple
from core.os_info import os_version, user_os
from core.updater import update
from screens.help_screen import render_help
from screens.settings_screen import settings_screen
from ui.interface import clear_screen, pause


HAS_CURSES = importlib.util.find_spec('_curses') is not None


class Command(NamedTuple):
    name: str
    run: Callable
    aliases: tuple = ()
    help: str = ''

    @property
    def label(self):
        return f'{self.name} / {self.aliases[0]}' if self.aliases else self.name


class HelpEntry(NamedTuple):
    name: str
    help: str


def _cmd_settings(raw):
    settings_screen()


def _cmd_system(raw):
    print(f'{user_os()} {os_version()} ({platform.machine()})')
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


COMMANDS = [
    Command('keeper',    _cmd_keeper,    ('k', 'keep'), 'ask the archive in your own words'),
    Command('schedule',  _cmd_schedule,  ('sch',),      'shift schedule, week by week'),
    Command('favorites', _cmd_favorites, ('f', 'fav'),  'pinned records'),
    Command('settings',  _cmd_settings,  ('s',),        'operator name / archives / schedule / Keeper'),
    Command('system',    _cmd_system,    ('sys',),      'show OS and version'),
    Command('update',    _cmd_update,    (),            'fetch and apply a pending update'),
    *([Command('hyperspace', _cmd_hyperspace, ('hy',), 'go to hyperspace (any key to return)')]
      if HAS_CURSES else []),
    Command('list',      _cmd_list,      ('l',)),
    Command('help',      _cmd_help,      ('h',),        'this help'),
]

HELP_SECTIONS = [
    ('Search', [
        HelpEntry('type word(s)', 'search the archive (approximate matching)'),
        HelpEntry('[number]',     'open a case from the current list'),
        HelpEntry('n / p',        'next / previous page or case'),
        HelpEntry('l / list',     'browse all cases'),
        HelpEntry('e',            'edit the open case'),
        HelpEntry('f',            'pin / unpin the open case'),
        HelpEntry('x number',     'check / uncheck a task in the open note'),
    ]),
    ('Schedule', [
        HelpEntry('n / p',        'next / previous week'),
        HelpEntry('t',            'back to this week'),
        HelpEntry('+N / -N',      'jump N weeks ahead / back'),
        HelpEntry('type a date',  'open the week of that date, e.g. 14-11'),
    ]),
    ('Commands', [HelpEntry(c.label, c.help) for c in COMMANDS if c.help]),
    ('Navigation', [
        HelpEntry('b',     'back to previous screen'),
        HelpEntry('Enter', 'refresh the current screen'),
        HelpEntry('q',     'quit'),
    ]),
]

_INDEX = {name: c for c in COMMANDS for name in (c.name, *c.aliases)}
