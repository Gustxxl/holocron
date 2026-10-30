import unittest
from unittest import mock

from screens import keeper_screen as screen

CONN = {'slot': 'local'}


class Open(unittest.TestCase):
    def open(self, woken, commands=('b',)):
        with mock.patch.object(screen, '_wake', side_effect=list(woken)) as wake, \
             mock.patch('screens.settings_screen.keeper_screen') as settings, \
             mock.patch.object(screen, '_SESSION', {'turns': [], 'records': []}), \
             mock.patch.object(screen, '_redraw', return_value=('local', 0)) as redraw, \
             mock.patch.object(screen, 'read_command', side_effect=list(commands)) as read:
            screen.keeper_screen()
        return wake, settings, redraw, read

    def test_offline_opens_settings(self):
        wake, settings, redraw, read = self.open([None, None])
        settings.assert_called_once_with()
        self.assertEqual(wake.call_args_list, [mock.call(), mock.call(True)])
        redraw.assert_not_called()
        read.assert_not_called()

    def test_fixed_in_settings_opens_keeper(self):
        _, settings, redraw, read = self.open([None, CONN])
        settings.assert_called_once_with()
        redraw.assert_called_once()
        read.assert_called_once_with('ask> ', lines=True)

    def test_online_skips_settings(self):
        _, settings, redraw, _ = self.open([CONN])
        settings.assert_not_called()
        redraw.assert_called_once()


class Wake(unittest.TestCase):
    def wake(self, configured, cached, refresh=False):
        with mock.patch.object(screen.keeper, 'configured', return_value=configured), \
             mock.patch.object(screen.keeper, 'cached', return_value=cached), \
             mock.patch.object(screen.keeper, 'active', return_value=CONN) as self.active, \
             mock.patch.object(screen, 'clear_screen'), mock.patch('builtins.print'), \
             mock.patch.object(screen, 'wait') as wait:
            return screen._wake(refresh), wait

    def test_checks_when_not_cached(self):
        conn, wait = self.wake(True, False)
        self.assertEqual(conn, CONN)
        wait.assert_called_once_with(screen.LINES['connecting'], self.active, True)

    def test_refresh_checks_again(self):
        self.wake(True, True, refresh=True)[1].assert_called_once()

    def test_cached_skips_check(self):
        self.wake(True, True)[1].assert_not_called()

    def test_not_configured_skips_check(self):
        self.wake(False, False)[1].assert_not_called()
