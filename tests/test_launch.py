import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import launch, system


class Parse(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.board = self.file('board.md')

    def file(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return path

    def parse(self, *args, cwd=True):
        return launch.parse(list(args), str(self.root) if cwd else None)

    def test_nothing(self):
        self.assertEqual(self.parse(), (None, None))

    def test_blank(self):
        for text in ('', '   '):
            with self.subTest(repr(text)):
                self.assertEqual(self.parse(text), (None, None))

    def test_word(self):
        self.assertEqual(self.parse('nginx'), ('search', 'nginx'))

    def test_words_joined(self):
        self.assertEqual(self.parse('nginx', 'timeout'), ('search', 'nginx timeout'))

    def test_several_searches_in_quotes(self):
        self.assertEqual(self.parse('nginx; ERR504'), ('search', 'nginx; ERR504'))

    def test_command_word(self):
        self.assertEqual(self.parse('schedule'), ('search', 'schedule'))

    def test_folder_name_is_search(self):
        (self.root / 'tests').mkdir()
        self.assertEqual(self.parse('tests'), ('search', 'tests'))

    def test_folder_path_is_search(self):
        (self.root / 'logs').mkdir()
        for text in ('./logs', str(self.root / 'logs'), str(self.root)):
            with self.subTest(text):
                self.assertEqual(self.parse(text), ('search', text))

    def test_other_file_is_search(self):
        self.file('notes.txt')
        self.assertEqual(self.parse('notes.txt'), ('search', 'notes.txt'))

    def test_board(self):
        self.assertEqual(self.parse('board.md'), ('board', str(self.board)))

    def test_board_in_subfolder(self):
        board = self.file('work/errors.md')
        self.assertEqual(self.parse('work/errors.md'), ('board', str(board)))
        self.assertEqual(self.parse('./work/errors.md'), ('board', str(board)))

    def test_board_path_resolved(self):
        self.file('work/x.md')
        self.assertEqual(self.parse('work/../board.md'), ('board', str(self.board)))

    def test_board_suffix_any_case(self):
        board = self.file('Errors.MD')
        self.assertEqual(self.parse('Errors.MD'), ('board', str(board)))

    def test_absolute_board(self):
        self.assertEqual(self.parse(str(self.board), cwd=False), ('board', str(self.board)))

    def test_home_board(self):
        with mock.patch.dict(os.environ, {'HOME': str(self.root), 'USERPROFILE': str(self.root)}):
            self.assertEqual(self.parse('~/board.md', cwd=False), ('board', str(self.board)))

    def test_quoted_board(self):
        for text in ('"board.md"', "'board.md'", '  board.md  '):
            with self.subTest(text):
                self.assertEqual(self.parse(text), ('board', str(self.board)))

    @unittest.skipIf(system.IS_WINDOWS, 'backslash is a separator on Windows')
    def test_escaped_space(self):
        board = self.file('My Board.md')
        self.assertEqual(self.parse('My\\ Board.md'), ('board', str(board)))

    def test_result_is_absolute(self):
        _, path = self.parse('board.md')
        self.assertTrue(Path(path).is_absolute())

    def test_missing_board_is_search(self):
        self.assertEqual(self.parse('nope.md'), ('search', 'nope.md'))

    def test_folder_named_like_board(self):
        (self.root / 'notes.md').mkdir()
        self.assertEqual(self.parse('notes.md'), ('search', 'notes.md'))

    def test_board_with_more_words_is_search(self):
        self.assertEqual(self.parse('board.md', 'nginx'), ('search', 'board.md nginx'))

    def test_relative_needs_start_folder(self):
        self.assertEqual(self.parse('board.md', cwd=False), ('search', 'board.md'))

    def test_start_folder_not_process_folder(self):
        with tempfile.TemporaryDirectory() as other:
            (Path(other) / 'README.md').write_text('', encoding='utf-8')
            here = os.getcwd()
            self.addCleanup(os.chdir, here)
            os.chdir(other)
            self.assertEqual(self.parse('README.md'), ('search', 'README.md'))
            self.assertEqual(self.parse('README.md', cwd=False), ('search', 'README.md'))

    def test_help(self):
        for flag in ('-h', '--help'):
            with self.subTest(flag):
                self.assertEqual(self.parse(flag), ('help', None))
                self.assertEqual(self.parse(flag, 'nginx'), ('help', None))

    def test_unknown_option(self):
        for flag in ('-x', '--version', '-', '--'):
            with self.subTest(flag):
                self.assertEqual(self.parse(flag), ('unknown', flag))

    def test_dash_inside_is_search(self):
        self.assertEqual(self.parse('nginx', '-v'), ('search', 'nginx -v'))

    def test_usage_covers_every_way(self):
        for text in ('holo words', 'holo schedule', 'holo "nginx; ERR504"', 'holo path/board.md'):
            self.assertIn(text, launch.USAGE)


if __name__ == '__main__':
    unittest.main()
