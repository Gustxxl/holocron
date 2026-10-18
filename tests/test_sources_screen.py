import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

from screens import sources_screen


class SourceSetupScreen(unittest.TestCase):
    def _source(self, state):
        return SimpleNamespace(
            NAME='Reminders', TAP='steipete/tap/remindctl', PROGRAM='remindctl', MACOS=14,
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


class ListsScreen(unittest.TestCase):
    def _source(self):
        return SimpleNamespace(
            NAME='Reminders', PROGRAM='remindctl', TAP='steipete/tap/remindctl', KEY='reminders',
            LISTS='lists', SHOWN=3, AHEAD=1, lists=lambda: [{'id': 'a', 'title': 'Work'}],
        )

    def _open(self, commands, where, after=None, shadowed=None, agreed=True):
        state = {'where': where}

        def remove(program, formula):
            state['where'] = after
            return True

        with mock.patch.object(sources_screen, 'clear_screen'), \
             mock.patch.object(sources_screen, 'pause'), \
             mock.patch.object(sources_screen, 'haptic'), \
             mock.patch.object(sources_screen, 'read_command', side_effect=commands), \
             mock.patch.object(sources_screen, 'confirm', return_value=agreed), \
             mock.patch.object(sources_screen, 'sources') as stored, \
             mock.patch.object(sources_screen.cli, 'origin', side_effect=lambda program: state['where']), \
             mock.patch.object(sources_screen.cli, 'available', side_effect=lambda program: state['where'] is not None), \
             mock.patch.object(sources_screen.cli, 'which', return_value='/x/remindctl'), \
             mock.patch.object(sources_screen.cli, 'shadowed', return_value=shadowed), \
             mock.patch.object(sources_screen.macos, 'remove', side_effect=remove) as self.remove, \
             redirect_stdout(io.StringIO()) as out:
            stored.selected.return_value = []
            stored.default.return_value = None
            stored.option.side_effect = lambda key, name, default: default
            sources_screen.lists_screen(self._source())
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
