import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

from screens import settings_screen


class SourceSetupScreen(unittest.TestCase):
    def _source(self, state):
        return SimpleNamespace(
            NAME='Reminders', TAP='steipete/tap/remindctl',
            status=lambda: state, terminal=lambda: 'Terminal',
        )

    def _open(self, state):
        with mock.patch.object(settings_screen, 'clear_screen'), \
             mock.patch.object(settings_screen, 'read_command', return_value='b'), \
             redirect_stdout(io.StringIO()) as out:
            result = settings_screen.source_setup(self._source(state))
        return result, out.getvalue()

    def test_every_step_renders(self):
        for state in settings_screen._STEPS:
            with self.subTest(state=state):
                result, out = self._open(state)
                self.assertFalse(result)
                self.assertIn('Settings > Reminders', out)

    def test_ready_skips_screen(self):
        result, out = self._open('ready')
        self.assertTrue(result)
        self.assertEqual(out, '')

    def test_menu_label_has_no_mark_when_ready(self):
        self.assertEqual(settings_screen._source_label(self._source('ready')), 'Reminders')
