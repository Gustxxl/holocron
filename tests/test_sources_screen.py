import io
import os
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

from core.sources import registry
from screens import settings_screen, sources_screen

WIDE = os.terminal_size((200, 50))


class SourceSetupScreen(unittest.TestCase):
    def _source(self, state):
        return SimpleNamespace(
            NAME='Reminders', SETUP='macos', TAP='steipete/tap/remindctl', PROGRAM='remindctl', MACOS=14,
            ABOUT='Apple Reminders', PRIVACY='Reminders', status=lambda: state,
        )

    def _open(self, state):
        with mock.patch.object(sources_screen, 'clear_screen'), \
             mock.patch.object(sources_screen, 'read_command', return_value='b'), \
             redirect_stdout(io.StringIO()) as out:
            result = sources_screen.source_setup(self._source(state))
        return result, out.getvalue()

    def test_every_step_renders(self):
        for state in sources_screen._STEPS:
            with self.subTest(state=state):
                result, out = self._open(state)
                self.assertFalse(result)
                self.assertIn('Settings > Reminders', out)
                self.assertIn('remindctl', out)

    def test_ready_skips_screen(self):
        result, out = self._open('ready')
        self.assertTrue(result)
        self.assertEqual(out, '')

    def test_back_word_closes(self):
        for word in ('b', 'back', 'B', 'Back'):
            with self.subTest(word), \
                 mock.patch.object(sources_screen, 'clear_screen'), \
                 mock.patch.object(sources_screen, 'read_command', side_effect=[word]), \
                 redirect_stdout(io.StringIO()):
                self.assertFalse(sources_screen.source_setup(self._source('denied')))


class Setups(unittest.TestCase):
    def test_every_source_has_setup(self):
        for source in registry.ALL:
            with self.subTest(source.NAME):
                self.assertIn(source.SETUP, sources_screen._SETUPS)

    def test_macos_setup_registered(self):
        self.assertIs(sources_screen._SETUPS['macos'], sources_screen._macos_setup)

    def test_setup_picked_by_source(self):
        called = []
        source = SimpleNamespace(SETUP='sample')
        with mock.patch.dict(sources_screen._SETUPS, {'sample': lambda s: called.append(s) or True}):
            self.assertTrue(sources_screen.source_setup(source))
        self.assertEqual(called, [source])

    def test_setup_result_passed_back(self):
        with mock.patch.dict(sources_screen._SETUPS, {'sample': lambda s: False}):
            self.assertFalse(sources_screen.source_setup(SimpleNamespace(SETUP='sample')))

    def test_swiftbar_setup_registered(self):
        self.assertIs(sources_screen._SETUPS['swiftbar'], sources_screen._swiftbar_setup)


class BarSetupScreen(unittest.TestCase):
    def _open(self, state, commands=('b',), brew=False, made='ok'):
        self.source = SimpleNamespace(
            NAME='Menu bar', SETUP='swiftbar', APP='SwiftBar', TAP='swiftbar', MACOS=12, FILE='holocron.1m.sh',
            HOME='~/SwiftBar', RELEASES='https://example.com/releases', status=lambda: state,
            folder=lambda: '/Альфа/Plugins', app=lambda: '/Applications/SwiftBar.app',
            add=mock.Mock(return_value=True), create=mock.Mock(return_value=made),
        )
        with mock.patch.object(sources_screen, 'clear_screen'), \
             mock.patch.object(sources_screen, 'error') as self.error, \
             mock.patch.object(sources_screen, 'wait', side_effect=lambda text, fn, *a: fn(*a)), \
             mock.patch.object(sources_screen, 'pause'), \
             mock.patch.object(sources_screen, 'haptic'), \
             mock.patch.object(sources_screen, 'read_command', side_effect=list(commands)), \
             mock.patch.object(sources_screen.cli, 'available', return_value=brew), \
             mock.patch.object(sources_screen.macos, 'open_url') as self.opened, \
             mock.patch.object(sources_screen.macos, 'install', return_value='ok') as self.installed, \
             mock.patch('shutil.get_terminal_size', return_value=WIDE), \
             redirect_stdout(io.StringIO()) as out:
            result = sources_screen.source_setup(self.source)
        return result, out.getvalue()

    def test_every_step_renders(self):
        for state in sources_screen._BAR_STEPS:
            with self.subTest(state=state):
                result, out = self._open(state)
                self.assertFalse(result)
                self.assertIn('Settings > Menu bar', out)
                self.assertIn('SwiftBar', out)

    def test_ready_skips_screen(self):
        self.assertEqual(self._open('ready'), (True, ''))

    def test_add_only_by_key(self):
        _, out = self._open('off', ['a', 'b'])
        self.assertIn('/Альфа/Plugins', out)
        self.source.add.assert_called_once_with()
        self._open('no_folder', ['a', 'b'])
        self.source.add.assert_not_called()
        self._open('off')
        self.source.add.assert_not_called()

    def test_create_folder_by_key(self):
        _, out = self._open('no_folder', ['f', 'b'])
        self.assertIn('~/SwiftBar', out)
        self.source.create.assert_called_once_with()
        self._open('off', ['f', 'b'])
        self.source.create.assert_not_called()

    def test_create_reports_open_app(self):
        self._open('no_folder', ['f', 'b'], made='running')
        self.error.assert_called_once_with('SwiftBar did not quit. Quit it, then press f again')

    def test_download_page(self):
        self._open('missing', ['o', 'b'])
        self.opened.assert_called_once_with('https://example.com/releases')

    def test_open_app_for_folder(self):
        self._open('no_folder', ['o', 'b'])
        self.opened.assert_called_once_with('/Applications/SwiftBar.app')

    def test_brew_only_with_homebrew(self):
        _, out = self._open('missing', ['brew', 'b'])
        self.assertNotIn('install with Homebrew', out)
        self.installed.assert_not_called()
        _, out = self._open('missing', ['brew', 'b'], brew=True)
        self.assertIn('install with Homebrew', out)
        self.installed.assert_called_once_with('swiftbar')


class PluginScreen(unittest.TestCase):
    def _open(self, commands, agreed=True, owned=False):
        self.state = 'ready'

        def remove():
            self.state = 'off'
            return True

        self.source = SimpleNamespace(NAME='Menu bar', APP='SwiftBar', KEY='swiftbar', status=lambda: self.state,
                                      owned=lambda: owned, folder=lambda: '/Альфа/SwiftBar',
                                      plugin=lambda: '/Альфа/SwiftBar/holocron.1m.sh', remove=mock.Mock(side_effect=remove),
                                      shortcut=lambda: '', keys=registry.swiftbar.keys, refresh=mock.Mock())
        with mock.patch.object(sources_screen, 'clear_screen'), \
             mock.patch.object(sources_screen, 'error') as self.error, \
             mock.patch.object(sources_screen.sources, 'set_option') as self.stored, \
             mock.patch.object(sources_screen, 'haptic'), \
             mock.patch.object(sources_screen, 'wait', side_effect=lambda text, fn, *a: fn(*a)), \
             mock.patch.object(sources_screen, 'read_command', side_effect=commands), \
             mock.patch.object(sources_screen, 'confirm', return_value=agreed) as self.asked, \
             mock.patch('shutil.get_terminal_size', return_value=WIDE), \
             redirect_stdout(io.StringIO()) as out:
            sources_screen.plugin_screen(self.source)
        return out.getvalue()

    def test_shows_plugin(self):
        out = self._open(['b'])
        self.assertIn('/Альфа/SwiftBar/holocron.1m.sh', out)
        self.assertIn('remove from the menu bar', out)

    def test_remove_asks_first(self):
        self._open(['d', 'b'], agreed=False)
        self.source.remove.assert_not_called()

    def test_shortcut_set(self):
        out = self._open(['k', 'Option+R', 'b'])
        self.assertIn('New reminder shortcut', out)
        self.stored.assert_called_once_with('swiftbar', 'shortcut', 'option+r')
        self.source.refresh.assert_called_once_with()

    def test_shortcut_off(self):
        self._open(['k', 'off', 'b'])
        self.stored.assert_called_once_with('swiftbar', 'shortcut', '')

    def test_bad_shortcut_saves_nothing(self):
        self._open(['k', 'shift+r', 'k', '', 'b'])
        self.stored.assert_not_called()
        self.error.assert_called_once_with('Type keys like option+r, or off')

    def test_remove_closes_screen(self):
        self._open(['d'])
        self.source.remove.assert_called_once_with()
        self.asked.assert_called_once_with('Remove Holocron from the menu bar?')

    def test_confirm_names_own_folder(self):
        self._open(['d'], owned=True)
        self.asked.assert_called_once_with('Remove Holocron from the menu bar, quit SwiftBar and delete /Альфа/SwiftBar?')


class OpenSource(unittest.TestCase):
    def _open(self, source, ready=True):
        with mock.patch.object(settings_screen, 'source_setup', return_value=ready), \
             mock.patch.object(settings_screen, 'lists_screen') as self.lists, \
             mock.patch.object(settings_screen, 'plugin_screen') as self.plugin:
            settings_screen._open_source(source)

    def test_lists_for_list_source(self):
        source = SimpleNamespace(LISTS='lists')
        self._open(source)
        self.lists.assert_called_once_with(source)
        self.plugin.assert_not_called()

    def test_plugin_without_lists(self):
        source = SimpleNamespace()
        self._open(source)
        self.plugin.assert_called_once_with(source)
        self.lists.assert_not_called()

    def test_nothing_until_ready(self):
        self._open(SimpleNamespace(), ready=False)
        self.lists.assert_not_called()
        self.plugin.assert_not_called()


class ListsScreen(unittest.TestCase):
    def _source(self, tool=True):
        source = SimpleNamespace(
            NAME='Reminders', KEY='reminders', LISTS='lists', SHOWN=3, AHEAD=1,
            lists=lambda: [{'id': 'a', 'title': 'Work'}], available=lambda: self.state['where'] is not None,
        )
        if tool:
            source.PROGRAM, source.TAP = 'remindctl', 'steipete/tap/remindctl'
        return source

    def _open(self, commands, where, after=None, shadowed=None, agreed=True, tool=True):
        self.state = {'where': where}

        def remove(program, formula):
            self.state['where'] = after
            return True

        with mock.patch.object(sources_screen, 'clear_screen'), \
             mock.patch.object(sources_screen, 'pause'), \
             mock.patch.object(sources_screen, 'haptic'), \
             mock.patch.object(sources_screen, 'read_command', side_effect=commands), \
             mock.patch.object(sources_screen, 'confirm', return_value=agreed), \
             mock.patch.object(sources_screen, 'sources') as self.stored, \
             mock.patch.object(sources_screen.cli, 'origin', side_effect=lambda program: self.state['where']) as self.origin, \
             mock.patch.object(sources_screen.cli, 'which', return_value='/x/remindctl'), \
             mock.patch.object(sources_screen.cli, 'shadowed', return_value=shadowed), \
             mock.patch.object(sources_screen.macos, 'remove', side_effect=remove) as self.remove, \
             mock.patch('shutil.get_terminal_size', return_value=WIDE), \
             redirect_stdout(io.StringIO()) as out:
            self.stored.selected.return_value = []
            self.stored.default.return_value = None
            self.stored.option.side_effect = lambda key, name, default: default
            sources_screen.lists_screen(self._source(tool))
        return out.getvalue()

    def test_lists_screen_stays_clean(self):
        out = self._open(['b'], 'holocron')
        self.assertNotIn('downloaded by Holocron', out)
        self.assertNotIn('delete', out)

    def test_card_shows_origin(self):
        out = self._open(['i', 'b', 'b'], 'homebrew')
        self.assertIn('installed with Homebrew', out)

    def test_card_shows_paths(self):
        out = self._open(['i', 'b', 'b'], 'holocron', shadowed='/opt/homebrew/bin/remindctl')
        self.assertIn('/x/remindctl', out)
        self.assertIn('/opt/homebrew/bin/remindctl', out)
        self.assertIn('delete', out)

    def test_system_copy_not_removable(self):
        out = self._open(['i', 'd', 'b', 'b'], 'system')
        self.assertIn('installed separately', out)
        self.assertNotIn('[d] delete', out)
        self.remove.assert_not_called()

    def test_remove_asks_first(self):
        self._open(['i', 'd', 'b', 'b'], 'holocron', agreed=False)
        self.remove.assert_not_called()

    def test_remove_closes_screens(self):
        self._open(['i', 'd'], 'holocron')
        self.remove.assert_called_once_with('remindctl', 'steipete/tap/remindctl')

    def test_remove_switches_to_homebrew(self):
        out = self._open(['i', 'd', 'b', 'b'], 'holocron', after='homebrew')
        self.assertIn('installed with Homebrew', out)

    def test_closes_when_source_gone(self):
        self.assertEqual(self._open([], None), '')

    def test_info_with_tool(self):
        self.assertIn('info', self._open(['b'], 'holocron'))

    def test_no_info_without_tool(self):
        out = self._open(['i', 'b'], 'holocron', tool=False)
        self.assertNotIn('info', out)
        self.origin.assert_not_called()

    def test_lists_work_without_tool(self):
        self._open(['1', 'm 4', 't 3', 'd 1', 'b'], 'holocron', tool=False)
        self.stored.toggle_list.assert_called_once_with('reminders', 'a')
        self.stored.set_option.assert_has_calls([mock.call('reminders', 'shown', 4),
                                                 mock.call('reminders', 'ahead', 3)])
        self.stored.set_default.assert_called_once_with('reminders', 'a')
