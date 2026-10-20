import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

from core.sources import registry
from screens import sources_screen


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
