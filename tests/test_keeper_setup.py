import json
import os
import unittest
import urllib.error
from types import SimpleNamespace
from unittest import mock

from core import keeper
from screens import settings_screen as screen

LOCAL = {'slot': 'local', 'url': 'http://l', 'model': 'm'}
SERVER = {'slot': 'server', 'url': 'http://s', 'model': 'm'}
WIDE = os.terminal_size((200, 50))


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
             mock.patch.object(screen, 'haptic'), \
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

    def test_docker(self):
        out, _ = self.models('docker', [], os_name='Linux')
        self.assertIn('If it runs in Docker, start the container: docker start ollama', out)
        self.assertIn('https://docs.ollama.com/docker', out)
        self.assertIn('Not installed yet: https://docs.ollama.com/linux', out)
        self.assertNotIn('installed but not running', out)

    def test_stopped(self):
        out, _ = self.models('stopped', [], os_name='Linux')
        self.assertIn('installed but not running', out)
        self.assertIn('https://docs.ollama.com/linux', out)

    def test_server_off(self):
        out, _ = self.models('off', [], conn=SERVER)
        self.assertIn('http://s is not responding.', out)
        self.assertIn('https://docs.ollama.com/faq', out)
        self.assertIn('In Docker, publish the port: -p 11434:11434', out)

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


class Setup(unittest.TestCase):
    def setup(self, state, found=(), commands=('b',), model='', os_name='macOS', server_after=False, opened=True):
        conn = dict(LOCAL, model=model)
        with mock.patch.object(screen.keeper, 'connection', return_value=conn), \
             mock.patch.object(screen.keeper, 'status', return_value=(state, list(found))), \
             mock.patch.object(screen.keeper, 'reset'), \
             mock.patch.object(screen.keeper, 'has_server', return_value=server_after), \
             mock.patch.object(screen, 'wait', side_effect=lambda label, fn, *a: fn(*a)), \
             mock.patch.object(screen, 'clear_screen'), \
             mock.patch.object(screen, 'haptic'), \
             mock.patch.object(screen.system, 'OS', os_name), \
             mock.patch.object(screen.system, 'open_file', return_value=opened) as open_file, \
             mock.patch.object(screen, 'error') as error, \
             mock.patch.object(screen, 'update_keeper_model') as update, \
             mock.patch.object(screen, '_keeper_download') as download, \
             mock.patch.object(screen, '_server_screen') as server, \
             mock.patch.object(screen, 'read_command', side_effect=list(commands)) as read, \
             mock.patch('shutil.get_terminal_size', return_value=WIDE), \
             mock.patch('builtins.print') as printed:
            result = screen._keeper_setup()
        return SimpleNamespace(result=result, out=_printed(printed), open_file=open_file, error=error,
                               update=update, download=download, server=server, read=read, conn=conn)

    def test_ready_skips_screen(self):
        s = self.setup('ready', ['m'], commands=())
        self.assertTrue(s.result)
        s.read.assert_not_called()

    def test_current_step(self):
        for state, step in (('missing', 'Ollama installed'), ('stopped', 'Ollama running'), ('docker', 'Ollama running'),
                            ('foreign', 'Ollama running'), ('no_models', 'Model chosen'),
                            ('no_model', 'Model chosen'), ('model_missing', 'Model chosen')):
            with self.subTest(state=state):
                s = self.setup(state)
                self.assertIn(f'  → {step}', s.out)
                self.assertFalse(s.result)

    def test_done_and_next_steps(self):
        out = self.setup('stopped').out
        self.assertIn(f'  {screen.dim("✓")} Ollama installed', out)
        self.assertIn(screen.dim('  · Model chosen'), out)

    def test_guide_per_os(self):
        for os_name, url in (('macOS', 'https://docs.ollama.com/macos'), ('Windows', 'https://docs.ollama.com/windows'),
                             ('Linux', 'https://docs.ollama.com/linux'), ('Other', 'https://ollama.com/download')):
            with self.subTest(os_name=os_name):
                out = self.setup('missing', os_name=os_name).out
                self.assertIn(f'Guide: {url}', out)
                self.assertIn('[o] open the guide', out)

    def test_open_guide(self):
        s = self.setup('missing', commands=['o', 'b'], os_name='Linux')
        s.open_file.assert_called_once_with('https://docs.ollama.com/linux')
        s.error.assert_not_called()

    def test_guide_without_browser(self):
        s = self.setup('stopped', commands=['o', 'b'], opened=False)
        s.error.assert_called_once_with('Could not open a browser. The guide is at https://docs.ollama.com/macos')

    def test_start_hint_per_os(self):
        for os_name, text in (('macOS', 'Open Ollama from Applications, then press Enter.'),
                              ('Windows', 'Open Ollama from the Start menu, then press Enter.'),
                              ('Linux', 'Run ollama serve, then press Enter.')):
            with self.subTest(os_name=os_name):
                self.assertIn(text, self.setup('stopped', os_name=os_name).out)

    def test_docker_hint(self):
        out = self.setup('docker', os_name='Windows').out
        self.assertIn('docker start ollama', out)
        self.assertIn('Guide: https://docs.ollama.com/docker', out)
        self.assertIn('Not installed yet: https://docs.ollama.com/windows', out)
        self.assertIn('[o] open the guide', out)

    def test_open_docker_guide(self):
        s = self.setup('docker', commands=['o', 'b'])
        s.open_file.assert_called_once_with('https://docs.ollama.com/docker')

    def test_foreign_has_no_guide(self):
        s = self.setup('foreign', commands=['o', 'b'])
        self.assertIn('Another program is using this port.', s.out)
        self.assertNotIn('[o]', s.out)
        s.open_file.assert_not_called()

    def test_download_tested_model(self):
        s = self.setup('no_models', commands=['d', 'b'])
        self.assertIn(f'[d] download {keeper.RECOMMENDED}', s.out)
        self.assertIn(f'Keeper is tested on {keeper.RECOMMENDED}.', s.out)
        s.download.assert_called_once_with(s.conn)

    def test_no_download_when_present(self):
        s = self.setup('no_model', [keeper.RECOMMENDED], commands=['d', 'b'])
        self.assertNotIn('[d] download', s.out)
        s.download.assert_not_called()

    def test_no_download_before_ollama(self):
        s = self.setup('stopped', commands=['d', 'b'])
        self.assertNotIn('[d] download', s.out)
        s.download.assert_not_called()

    def test_select_model(self):
        s = self.setup('no_model', ['alpha:1b'], commands=['1', 'b'])
        s.update.assert_called_once_with('local', 'alpha:1b')

    def test_odd_digits_ignored(self):
        s = self.setup('no_model', ['alpha:1b'], commands=['²', '0', '2', 'b'])
        s.update.assert_not_called()

    def test_model_removed(self):
        self.assertIn('gone:1b is no longer in Ollama.', self.setup('model_missing', ['alpha:1b'], model='gone:1b').out)

    def test_server_added(self):
        s = self.setup('missing', commands=['s'], server_after=True)
        self.assertTrue(s.result)
        s.server.assert_called_once_with()

    def test_server_cancelled(self):
        s = self.setup('missing', commands=['s', 'b'])
        self.assertFalse(s.result)
        s.server.assert_called_once_with()

    def test_back(self):
        for word in ('b', 'back', 'B'):
            with self.subTest(word=word):
                self.assertFalse(self.setup('missing', commands=[word]).result)


class Status(unittest.TestCase):
    def status(self, state, where, docker=False, rows=(LOCAL,)):
        with mock.patch.object(screen.keeper, 'connections', return_value=list(rows)), \
             mock.patch.object(screen.keeper, 'docker', return_value=docker), \
             mock.patch.object(screen.keeper, 'has_server', return_value=SERVER in rows), \
             mock.patch.object(screen.keeper, 'reset'), \
             mock.patch.object(screen.keeper, 'statuses', return_value=[(state, ['m'])] * len(rows)), \
             mock.patch.object(screen.keeper, 'placement', return_value=where) as place, \
             mock.patch.object(screen, '_keeper_setup', return_value=True), \
             mock.patch.object(screen, 'wait', side_effect=lambda label, fn, *a: fn(*a)), \
             mock.patch.object(screen, 'clear_screen'), \
             mock.patch.object(screen, 'haptic'), \
             mock.patch.object(screen, 'read_command', side_effect=['b']), \
             mock.patch('builtins.print') as printed:
            screen.keeper_screen()
        return _printed(printed), place

    def test_cpu_hint(self):
        out, place = self.status('ready', 'CPU')
        self.assertIn('online · CPU', out)
        self.assertIn('replies are slow', out)
        self.assertIn('https://docs.ollama.com/gpu', out)
        self.assertNotIn('Docker', out)
        place.assert_called_once_with(LOCAL)

    def test_cpu_hint_with_local_docker(self):
        out, _ = self.status('ready', 'CPU', docker=True)
        self.assertIn('pass the GPU to the container: https://docs.ollama.com/docker', out)

    def test_cpu_hint_for_server(self):
        out, _ = self.status('ready', 'CPU', rows=(SERVER, LOCAL))
        self.assertIn('pass the GPU to the container', out)

    def test_docker_label(self):
        out, place = self.status('docker', 'CPU')
        place.assert_not_called()
        self.assertIn('Ollama not running', out)

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
