import os
import unittest
from unittest import mock

from core import settings
from screens import settings_screen as screen

LOCAL = {'slot': 'local', 'url': 'http://l', 'model': 'm'}
SERVER = {'slot': 'server', 'url': 'http://s', 'model': 'm'}
WIDE = os.terminal_size((200, 50))


def _printed(printed):
    return '\n'.join(str(c.args[0]) if c.args else '' for c in printed.call_args_list)


class Normalize(unittest.TestCase):
    def test_valid(self):
        for raw, url in (
            ('alpha', 'http://alpha:11434'),
            ('alpha:8080', 'http://alpha:8080'),
            ('  alpha:8080/  ', 'http://alpha:8080'),
            ('alpha:1', 'http://alpha:1'),
            ('alpha:65535', 'http://alpha:65535'),
            ('10.0.0.5', 'http://10.0.0.5:11434'),
            ('alpha/ollama', 'http://alpha:11434/ollama'),
            ('[::1]', 'http://[::1]:11434'),
            ('[::1]:8080', 'http://[::1]:8080'),
            ('альфа.рф', 'http://альфа.рф:11434'),
            ('http://alpha', 'http://alpha'),
            ('https://alpha.example/ollama/', 'https://alpha.example/ollama'),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(settings.normalize_server(raw), url)

    def test_invalid(self):
        for raw in ('', '   ', 'alpha beta', 'альфа бета', 'alpha:', 'alpha:0', 'alpha:65536', 'alpha:port',
                    'alpha:11434:1', 'ftp://alpha', 'http://', 'http://:11434', 'user:secret@alpha', '@alpha',
                    'alpha?x=1', 'alpha#top', '[::1'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                settings.normalize_server(raw)


class Read(unittest.TestCase):
    def test_values(self):
        for value, url in ((None, ''), ('', ''), (5, ''), ('alpha beta', ''), ('alpha', 'http://alpha:11434'),
                           ('http://alpha', 'http://alpha'), (' http://alpha/ ', 'http://alpha')):
            with self.subTest(value=value), \
                 mock.patch.object(settings, 'load', return_value={'keeper_server_url': value}):
                self.assertEqual(settings.keeper_server(), url)

    def test_missing(self):
        with mock.patch.object(settings, 'load', return_value={}):
            self.assertEqual(settings.keeper_server(), '')


class Store(unittest.TestCase):
    CFG = {'keeper_server_url': 'http://alpha:11434', 'keeper_server_model': 'm', 'keeper_local_model': 'n'}

    def store(self, url, cfg=CFG):
        with mock.patch.object(settings, 'load', return_value=dict(cfg)), \
             mock.patch.object(settings, 'save') as save:
            settings.update_keeper_server(url)
        return save

    def test_new_address_resets_model(self):
        self.store('beta').assert_called_once_with(
            {'keeper_server_url': 'http://beta:11434', 'keeper_server_model': '', 'keeper_local_model': 'n'})

    def test_same_address_keeps_model(self):
        self.store('alpha').assert_called_once_with(self.CFG)

    def test_clear(self):
        for url in ('', '   '):
            with self.subTest(url=url):
                self.store(url).assert_called_once_with(
                    {'keeper_server_url': '', 'keeper_server_model': '', 'keeper_local_model': 'n'})

    def test_invalid_not_saved(self):
        with mock.patch.object(settings, 'load', return_value=dict(self.CFG)) as load, \
             mock.patch.object(settings, 'save') as save, self.assertRaises(ValueError):
            settings.update_keeper_server('alpha beta')
        save.assert_not_called()
        load.assert_not_called()


class Server(unittest.TestCase):
    def run_screen(self, answers, has_server=True, update=None, state='off'):
        with mock.patch.object(screen.keeper, 'connection', return_value=SERVER if has_server else None), \
             mock.patch.object(screen.keeper, 'reset'), \
             mock.patch.object(screen.keeper, 'status', return_value=(state, [])), \
             mock.patch.object(screen, 'wait', side_effect=lambda label, fn, *a: fn(*a)), \
             mock.patch.object(screen, 'clear_screen'), \
             mock.patch.object(screen, '_keeper_models_screen') as models, \
             mock.patch.object(screen, 'update_keeper_server', side_effect=update) as store, \
             mock.patch.object(screen, 'error') as error, \
             mock.patch.object(screen, 'read_command', side_effect=[*answers, 'b']), \
             mock.patch('shutil.get_terminal_size', return_value=WIDE), \
             mock.patch('builtins.print') as printed:
            screen._server_screen()
        return _printed(printed), store, error, models

    def test_back_keeps_server(self):
        for answer in ('b', 'back', 'B', ''):
            with self.subTest(answer=answer):
                _, store, error, _ = self.run_screen([answer])
                store.assert_not_called()
                error.assert_not_called()

    def test_clear(self):
        for answer in ('c', 'C'):
            with self.subTest(answer=answer):
                self.run_screen([answer])[1].assert_called_once_with('')

    def test_clear_without_server(self):
        self.run_screen(['c'], has_server=False)[1].assert_not_called()

    def test_x_no_longer_removes(self):
        self.run_screen(['x'])[1].assert_called_once_with('x')

    def test_new_address(self):
        for answer in ('alpha:8080', 'альфа.рф'):
            with self.subTest(answer=answer):
                _, store, error, _ = self.run_screen([answer], has_server=False)
                store.assert_called_once_with(answer)
                error.assert_not_called()

    def test_bad_address(self):
        _, _, error, _ = self.run_screen(['alpha beta'], update=ValueError('alpha beta'))
        error.assert_called_once_with('Type an address like server-ip:11434')

    def test_bad_address_not_saved(self):
        with mock.patch.object(settings, 'load', return_value={}), \
             mock.patch.object(settings, 'save') as save:
            _, _, error, _ = self.run_screen(['alpha beta'], update=settings.update_keeper_server)
        save.assert_not_called()
        error.assert_called_once()

    def test_model(self):
        _, store, _, models = self.run_screen(['m'])
        models.assert_called_once_with('server')
        store.assert_not_called()

    def test_model_without_server(self):
        _, store, _, models = self.run_screen(['m'], has_server=False)
        models.assert_not_called()
        store.assert_not_called()

    def test_status_under_address(self):
        out, _, _, _ = self.run_screen([])
        self.assertIn('  Address   s', out)
        self.assertIn(f'  Status    {screen.dim("off")}', out)
        self.assertIn('https://docs.ollama.com/faq', out)
        self.assertIn('In Docker, publish the port: -p 11434:11434', out)
        self.assertIn('[c] clear', out)

    def test_foreign(self):
        out, _, _, _ = self.run_screen([], state='foreign')
        self.assertIn('Check the address and port.', out)
        self.assertNotIn('https://docs.ollama.com/faq', out)

    def test_not_set(self):
        out, _, _, _ = self.run_screen([], has_server=False)
        self.assertIn('server-ip:11434', out)
        self.assertNotIn('[c] clear', out)
        self.assertNotIn('[m] model', out)


class Main(unittest.TestCase):
    def open(self, commands, has_server=True, ready=True):
        with mock.patch.object(screen.keeper, 'has_server', return_value=has_server), \
             mock.patch.object(screen.keeper, 'connections', return_value=[SERVER, LOCAL]), \
             mock.patch.object(screen.keeper, 'statuses', return_value=[('off', []), ('stopped', [])]), \
             mock.patch.object(screen.keeper, 'reset'), \
             mock.patch.object(screen, 'wait', side_effect=lambda label, fn, *a: fn(*a)), \
             mock.patch.object(screen, 'clear_screen'), \
             mock.patch.object(screen, '_keeper_setup', return_value=ready) as setup, \
             mock.patch.object(screen, '_server_screen') as server, \
             mock.patch.object(screen, 'read_command', side_effect=commands) as read, \
             mock.patch('builtins.print'):
            screen.keeper_screen()
        return setup, server, read

    def test_server_skips_setup(self):
        setup, _, _ = self.open(['b'])
        setup.assert_not_called()

    def test_setup_back_closes(self):
        setup, _, read = self.open([], has_server=False, ready=False)
        setup.assert_called_once_with()
        read.assert_not_called()

    def test_server_key(self):
        _, server, _ = self.open(['s', 'b'])
        server.assert_called_once_with()

    def test_a_no_longer_opens_server(self):
        _, server, _ = self.open(['a', 'b'])
        server.assert_not_called()


if __name__ == '__main__':
    unittest.main()
