import json
import unittest
import urllib.error
from unittest import mock

from core import keeper
from screens import settings_screen as screen

LOCAL = {'slot': 'local', 'url': 'http://l', 'model': 'm'}
SERVER = {'slot': 'server', 'url': 'http://s', 'model': 'm'}


def _printed(printed):
    return '\n'.join(str(c.args[0]) if c.args else '' for c in printed.call_args_list)


class Placement(unittest.TestCase):
    def place(self, models, model='m'):
        data = {'models': models}
        with mock.patch.object(keeper, '_get_json', return_value=data) as get:
            out = keeper.placement(dict(LOCAL, model=model))
        self.assertEqual(get.call_args.args[1], '/api/ps')
        self.assertEqual(get.call_args.kwargs['timeout'], keeper.PROBE_TIMEOUT)
        return out

    def test_gpu(self):
        self.assertEqual(self.place([{'name': 'm', 'size': 100, 'size_vram': 100}]), 'GPU')

    def test_cpu(self):
        self.assertEqual(self.place([{'name': 'm', 'size': 100, 'size_vram': 0}]), 'CPU')
        self.assertEqual(self.place([{'name': 'm', 'size': 100}]), 'CPU')

    def test_split(self):
        self.assertEqual(self.place([{'name': 'm', 'size': 100, 'size_vram': 40}]), 'GPU + CPU')

    def test_matched_by_model_field(self):
        self.assertEqual(self.place([{'model': 'm', 'size': 100, 'size_vram': 100}]), 'GPU')

    def test_other_model_loaded(self):
        self.assertIsNone(self.place([{'name': 'other', 'size': 100, 'size_vram': 100}]))

    def test_not_loaded(self):
        self.assertIsNone(self.place([]))

    def test_garbage(self):
        for models in ([{'name': 'm'}], [{'name': 'm', 'size': 'x'}], [{'name': 'm', 'size': 0}], 'x', [None]):
            with self.subTest(models=models):
                self.assertIsNone(self.place(models))

    def test_not_a_dict(self):
        with mock.patch.object(keeper, '_get_json', return_value=['x']):
            self.assertIsNone(keeper.placement(LOCAL))

    def test_offline(self):
        for exc in (urllib.error.URLError('down'), OSError('down'), json.JSONDecodeError('x', 'x', 0)):
            with self.subTest(exc=exc), mock.patch.object(keeper, '_get_json', side_effect=exc):
                self.assertIsNone(keeper.placement(LOCAL))


class Models(unittest.TestCase):
    def models(self, state, found, conn=LOCAL, commands=('b',), os_name='macOS'):
        with mock.patch.object(screen.keeper, 'connection', return_value=conn), \
             mock.patch.object(screen.keeper, 'status', return_value=(state, found)), \
             mock.patch.object(screen.keeper, 'reset'), \
             mock.patch.object(screen, 'wait', side_effect=lambda label, fn, *a: fn(*a)), \
             mock.patch.object(screen, 'clear_screen'), \
             mock.patch.object(screen.system, 'OS', os_name), \
             mock.patch.object(screen, 'update_keeper_model') as update, \
             mock.patch.object(screen, 'read_command', side_effect=list(commands)), \
             mock.patch('builtins.print') as printed:
            screen._keeper_models_screen(conn['slot'])
        return _printed(printed), update

    def test_links_for_this_system(self):
        self.assertIn(screen.system.OS, screen._OLLAMA_DOCS)

    def test_missing_links_per_os(self):
        for os_name, url in (('macOS', 'https://docs.ollama.com/macos'), ('Windows', 'https://docs.ollama.com/windows'),
                             ('Linux', 'https://docs.ollama.com/linux'), ('Other', 'https://ollama.com/download')):
            with self.subTest(os_name=os_name):
                out, _ = self.models('missing', [], os_name=os_name)
                self.assertIn(f'Install it: {url}', out)
                self.assertNotIn('curl', out)

    def test_stopped(self):
        out, _ = self.models('stopped', [], os_name='Linux')
        self.assertIn('installed but not running', out)
        self.assertIn('https://docs.ollama.com/linux', out)

    def test_server_off(self):
        out, _ = self.models('off', [], conn=SERVER)
        self.assertIn('http://s is not responding.', out)
        self.assertIn('https://docs.ollama.com/faq', out)

    def test_foreign(self):
        hints = {'server': '  Check the address and port.', 'local': '  Another program is using this port.'}
        for conn in (SERVER, LOCAL):
            with self.subTest(slot=conn['slot']):
                out, update = self.models('foreign', [], conn=conn)
                self.assertIn(f'  {conn["url"]} answers, but it is not Ollama.', out)
                self.assertIn(hints[conn['slot']], out)
                other = hints['local' if conn['slot'] == 'server' else 'server']
                self.assertNotIn(other, out)
                self.assertNotIn('not responding', out)
                self.assertNotIn('[number] select', out)
                self.assertNotIn('[d] download', out)
                update.assert_not_called()

    def test_lists_models_with_warning(self):
        out, update = self.models('no_model', ['other:1b', keeper.RECOMMENDED], commands=['1'])
        self.assertIn('other:1b', out)
        self.assertIn(f'{keeper.RECOMMENDED}\033[2m  tested', out)
        self.assertIn('Larger models often answer better, smaller ones worse.', out)
        update.assert_called_once_with('local', 'other:1b')

    def test_tested_and_current(self):
        out, _ = self.models('ready', [keeper.RECOMMENDED], conn=dict(LOCAL, model=keeper.RECOMMENDED))
        self.assertIn('tested · current', out)

    def test_no_warning_for_tested_only(self):
        out, _ = self.models('no_model', [keeper.RECOMMENDED])
        self.assertIn(keeper.RECOMMENDED, out)
        self.assertNotIn('Other models', out)

    def test_bad_number_ignored(self):
        _, update = self.models('no_model', ['other:1b'], commands=['9', 'x', 'b'])
        update.assert_not_called()


class Status(unittest.TestCase):
    def status(self, state, where):
        with mock.patch.object(screen.keeper, 'connections', return_value=[LOCAL]), \
             mock.patch.object(screen.keeper, 'has_server', return_value=False), \
             mock.patch.object(screen.keeper, 'reset'), \
             mock.patch.object(screen.keeper, 'statuses', return_value=[(state, ['m'])]), \
             mock.patch.object(screen.keeper, 'placement', return_value=where) as place, \
             mock.patch.object(screen, 'wait', side_effect=lambda label, fn, *a: fn(*a)), \
             mock.patch.object(screen, 'clear_screen'), \
             mock.patch.object(screen, 'read_command', side_effect=['b']), \
             mock.patch('builtins.print') as printed:
            screen.keeper_screen()
        return _printed(printed), place

    def test_cpu_hint(self):
        out, place = self.status('ready', 'CPU')
        self.assertIn('online · CPU', out)
        self.assertIn('replies are slow', out)
        self.assertIn('https://docs.ollama.com/gpu', out)
        place.assert_called_once_with(LOCAL)

    def test_gpu(self):
        out, _ = self.status('ready', 'GPU')
        self.assertIn('online · GPU', out)
        self.assertNotIn('replies are slow', out)

    def test_split_has_no_hint(self):
        out, _ = self.status('ready', 'GPU + CPU')
        self.assertIn('online · GPU + CPU', out)
        self.assertNotIn('replies are slow', out)

    def test_not_loaded(self):
        out, _ = self.status('ready', None)
        self.assertIn('online', out)
        self.assertNotIn('online · ', out)

    def test_not_ready_skips_placement(self):
        out, place = self.status('stopped', 'CPU')
        place.assert_not_called()
        self.assertIn('Ollama not running', out)
        self.assertNotIn('replies are slow', out)

    def test_foreign_label(self):
        out, place = self.status('foreign', 'CPU')
        place.assert_not_called()
        self.assertIn('not Ollama', out)


if __name__ == '__main__':
    unittest.main()
