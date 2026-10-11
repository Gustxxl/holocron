import os
import unittest
from unittest.mock import patch

from core import editor, system


def _env(**values):
    env = {k: v for k, v in os.environ.items() if k not in ('VISUAL', 'EDITOR')}
    return patch.dict(os.environ, {**env, **values}, clear=True)


def _which(*found):
    return patch('core.system.shutil.which', side_effect=lambda name: f'/bin/{name}' if name in found else None)


class Command(unittest.TestCase):
    def test_with_arguments(self):
        with _which('code'):
            self.assertEqual(system.command('code --wait'), ['/bin/code', '--wait'])

    def test_missing(self):
        with _which():
            self.assertIsNone(system.command('code --wait'))

    def test_broken_quotes(self):
        with _which('code'):
            self.assertIsNone(system.command('"code'))

    def test_empty(self):
        self.assertIsNone(system.command(''))


class Editor(unittest.TestCase):
    def test_visual_first(self):
        with _env(VISUAL='micro', EDITOR='code --wait'), _which('micro', 'code'):
            self.assertEqual(system.editor(), ['/bin/micro'])

    def test_editor_with_arguments(self):
        with _env(EDITOR='code --wait'), _which('code'):
            self.assertEqual(system.editor(), ['/bin/code', '--wait'])

    def test_missing_env_falls_back(self):
        fallback = system.EDITORS[0]
        with _env(EDITOR='nothing-here'), _which(fallback):
            self.assertEqual(system.editor(), [f'/bin/{fallback}'])

    def test_none_found(self):
        with _env(), _which():
            self.assertIsNone(system.editor())
            self.assertFalse(editor.available())


class EditText(unittest.TestCase):
    def test_no_editor(self):
        with patch('core.editor.system.editor', return_value=None):
            self.assertIsNone(editor.edit_text('abc'))

    def test_editor_failed(self):
        with patch('core.editor.system.editor', return_value=['ed']), \
             patch('core.editor.system.attach', return_value=False):
            self.assertIsNone(editor.edit_text('abc'))

    def test_returns_file_text(self):
        def write(args):
            with open(args[-1], 'w', encoding='utf-8') as f:
                f.write('новый текст')
            return True

        with patch('core.editor.system.editor', return_value=['ed']), \
             patch('core.editor.system.attach', side_effect=write):
            self.assertEqual(editor.edit_text('abc'), 'новый текст')


class Run(unittest.TestCase):
    def test_missing_program(self):
        self.assertIsNone(system.run(['holocron-no-such-program']))

    def test_attach_missing_program(self):
        self.assertFalse(system.attach(['holocron-no-such-program']))


class Clipboard(unittest.TestCase):
    def test_first_working(self):
        ok = type('R', (), {'returncode': 0})()
        with _which('xclip'), patch('core.system.run', return_value=ok) as run:
            self.assertTrue(system.copy_text('текст'))
            self.assertEqual(run.call_args.args[0], ['/bin/xclip', '-selection', 'clipboard'])
            self.assertEqual(run.call_args.kwargs['input'], 'текст'.encode('utf-8'))

    def test_windows_clip_gets_utf16(self):
        ok = type('R', (), {'returncode': 0})()
        with _which('clip'), patch('core.system.run', return_value=ok) as run:
            system.copy_text('текст')
            self.assertEqual(run.call_args.kwargs['input'], 'текст'.encode('utf-16'))

    def test_none_available(self):
        with _which():
            self.assertFalse(system.copy_text('x'))


if __name__ == '__main__':
    unittest.main()
