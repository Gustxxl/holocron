import unittest
from unittest import mock

from core import settings
from screens import settings_screen as screen

LOCAL = {'slot': 'local', 'url': 'http://l', 'model': 'm'}
SERVER = {'slot': 'server', 'url': 'http://s', 'model': 'm'}


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


class Address(unittest.TestCase):
    def run_screen(self, answers, has_server=True, update=None):
        rows = [SERVER, LOCAL] if has_server else [LOCAL]
        states = [('off', []), ('stopped', [])] if has_server else [('stopped', [])]
        with mock.patch.object(screen.keeper, 'connections', return_value=rows), \
             mock.patch.object(screen.keeper, 'has_server', return_value=has_server), \
             mock.patch.object(screen.keeper, 'reset'), \
             mock.patch.object(screen.keeper, 'statuses', return_value=states), \
             mock.patch.object(screen, 'wait', side_effect=lambda label, fn, *a: fn(*a)), \
             mock.patch.object(screen, 'clear_screen'), \
             mock.patch.object(screen, 'update_keeper_server', side_effect=update) as store, \
             mock.patch.object(screen, 'error') as error, \
             mock.patch.object(screen, 'read_command', side_effect=['a', *answers, 'b']), \
             mock.patch('builtins.print') as printed:
            screen.keeper_screen()
        return _printed(printed), store, error

    def test_back_keeps_server(self):
        for answer in ('b', 'back', 'B', ''):
            with self.subTest(answer=answer):
                _, store, error = self.run_screen([answer])
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
                _, store, error = self.run_screen([answer], has_server=False)
                store.assert_called_once_with(answer)
                error.assert_not_called()

    def test_bad_address(self):
        _, _, error = self.run_screen(['alpha beta'], update=ValueError('alpha beta'))
        error.assert_called_once_with('Type an address like server-ip:11434')

    def test_bad_address_not_saved(self):
        with mock.patch.object(settings, 'load', return_value={}), \
             mock.patch.object(settings, 'save') as save:
            _, _, error = self.run_screen(['alpha beta'], update=settings.update_keeper_server)
        save.assert_not_called()
        error.assert_called_once()

    def test_hints(self):
        out, _, _ = self.run_screen(['b'])
        self.assertIn('  [c] clear   [b] back', out)
        self.assertNotIn('x to remove', out)
        out, _, _ = self.run_screen(['b'], has_server=False)
        self.assertIn('for example server-ip:11434', out)
        self.assertNotIn('[c] clear', out)


if __name__ == '__main__':
    unittest.main()
