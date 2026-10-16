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
