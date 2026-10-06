from collections import namedtuple
import platform
from ui.interface import clear_screen, pause
from core.os_info import user_os, os_version
from core.updater import update
from screens.settings_screen import settings_screen
from screens.help_screen import render_help

Command = namedtuple('Command', 'name help run aliases')
Command.__new__.__defaults__ = ((),)

HelpEntry = namedtuple('HelpEntry', 'name help')

HELP_SECTIONS = [
    ('Search', [
        HelpEntry('type word(s)',    'search the archive (approximate matching)'),
        HelpEntry('[number]',        'open a case from the current list'),
        HelpEntry('n / p',           'next / previous page or case'),
        HelpEntry('l / list',        'browse all cases'),
        HelpEntry('e',               'edit the open case'),
    ]),
    ('Commands', [
        HelpEntry('keeper / k',      'ask the archive in your own words'),
        HelpEntry('settings / s',    'operator name / archives / Keeper'),
        HelpEntry('system',          'show OS and version'),
        HelpEntry('update',          'fetch and apply a pending update'),
        HelpEntry('help / h',        'this help'),
    ]),
    ('Navigation', [
        HelpEntry('b',               'back to previous screen'),
        HelpEntry('Enter',           'refresh the current screen'),
        HelpEntry('q',               'quit'),
    ]),
]


def _cmd_settings(raw):
    clear_screen()
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
        pause()


def _cmd_help(raw):
    clear_screen()
    render_help(HELP_SECTIONS)
    pause()


def _cmd_list(raw):
    from screens.search_screen import search_screen
    search_screen('l')


def _cmd_keeper(raw):
    from screens.keeper_screen import keeper_screen
    keeper_screen()


COMMANDS = [
    Command('settings', 'settings', _cmd_settings, ('s',)),
    Command('system',   'system',   _cmd_system, ('sys',)),
    Command('update',   'update',   _cmd_update),
    Command('help',     'help',     _cmd_help, ('h',)),
    Command('list',     'list',     _cmd_list, ('l',)),
    Command('keeper',   'keeper',   _cmd_keeper, ('k', 'keep')),
]

_INDEX = {}
for _c in COMMANDS:
    for _name in (_c.name, *_c.aliases):
        _INDEX[_name] = _c
