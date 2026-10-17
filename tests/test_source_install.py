import unittest
from unittest import mock

from core.sources import macos
from screens import sources_screen


class _Proc:
    def __init__(self, lines, code):
        self.stdout = iter(lines)
        self.code = code

    def wait(self):
        return self.code


def _install(lines, code):
    with mock.patch.object(macos.cli, 'which', return_value='/x/brew'), \
         mock.patch.object(macos.subprocess, 'Popen', return_value=_Proc(lines, code)), \
         mock.patch('builtins.print'):
        return macos.install('sample/tap/tool')


class Install(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(_install(['done\n'], 0), 'ok')

    def test_clt_outdated(self):
        self.assertEqual(_install(['Error:\n', ' Your Command Line Tools are too outdated.\n'], 1), 'clt')

    def test_other_error(self):
        self.assertEqual(_install(['Error: no network\n'], 1), 'failed')

    def test_output_shown(self):
        with mock.patch.object(macos.cli, 'which', return_value='/x/brew'), \
             mock.patch.object(macos.subprocess, 'Popen', return_value=_Proc(['step one\n'], 0)), \
             mock.patch('builtins.print') as out:
            macos.install('sample/tap/tool')
        out.assert_any_call('step one\n', end='', flush=True)

    def test_interrupted(self):
        with mock.patch.object(macos.cli, 'which', return_value='/x/brew'), \
             mock.patch.object(macos.subprocess, 'Popen', side_effect=KeyboardInterrupt):
            self.assertEqual(macos.install('sample/tap/tool'), 'failed')


class _Source:
    NAME = 'Sample'
    PROGRAM = 'sampletool'
    TAP = 'sample/tap/sampletool'
    ABOUT = 'sample items'
    PRIVACY = 'Sample'
    MACOS = 14

    def status(self):
        return 'missing'


class Setup(unittest.TestCase):
    def run_setup(self, result, commands):
        with mock.patch.object(sources_screen, 'clear_screen'), \
             mock.patch.object(sources_screen, 'pause'), \
             mock.patch.object(sources_screen, 'read_command', side_effect=commands), \
             mock.patch.object(sources_screen.macos, 'install', return_value=result), \
             mock.patch.object(sources_screen.macos, 'open_url') as opened, \
             mock.patch('builtins.print') as out:
            sources_screen.source_setup(_Source())
        text = '\n'.join(str(c.args[0]) for c in out.call_args_list if c.args)
        return text, opened

    def test_clt_hint_shown(self):
        text, _ = self.run_setup('clt', ['i', 'b'])
        self.assertIn('Command Line Tools', text)

    def test_no_hint_on_other_error(self):
        text, _ = self.run_setup('failed', ['i', 'b'])
        self.assertNotIn('Command Line Tools', text)

    def test_open_software_update(self):
        _, opened = self.run_setup('clt', ['i', 'u', 'b'])
        opened.assert_called_once_with(sources_screen.macos.UPDATE_URL)

    def test_u_ignored_without_clt(self):
        _, opened = self.run_setup('failed', ['i', 'u', 'b'])
        opened.assert_not_called()


if __name__ == '__main__':
    unittest.main()
