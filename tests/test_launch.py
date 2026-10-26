import tempfile
import unittest
from pathlib import Path

from core import launch


class Parse(unittest.TestCase):
    def test_nothing(self):
        self.assertEqual(launch.parse([]), (None, None))

    def test_blank(self):
        for args in ([''], ['   '], ['', ' ']):
            with self.subTest(args):
                self.assertEqual(launch.parse(args), (None, None))

    def test_word(self):
        self.assertEqual(launch.parse(['nginx']), ('search', 'nginx'))

    def test_words_joined(self):
        self.assertEqual(launch.parse(['nginx', 'timeout']), ('search', 'nginx timeout'))

    def test_spaces_trimmed(self):
        self.assertEqual(launch.parse(['  nginx  ']), ('search', 'nginx'))

    def test_several_searches_in_quotes(self):
        self.assertEqual(launch.parse(['nginx; ERR504']), ('search', 'nginx; ERR504'))

    def test_cyrillic(self):
        self.assertEqual(launch.parse(['таймаут', 'ёлка']), ('search', 'таймаут ёлка'))

    def test_command_word(self):
        for word in ('schedule', 's', 'update', 'q'):
            with self.subTest(word):
                self.assertEqual(launch.parse([word]), ('search', word))

    def test_path_is_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp) / 'board.md'
            board.write_text('', encoding='utf-8')
            for text in (str(board), tmp, 'board.md', '~/board.md', './tests', 'tests'):
                with self.subTest(text):
                    self.assertEqual(launch.parse([text]), ('search', text))

    def test_help(self):
        for flag in ('-h', '--help'):
            with self.subTest(flag):
                self.assertEqual(launch.parse([flag]), ('help', None))
                self.assertEqual(launch.parse([flag, 'nginx']), ('help', None))

    def test_help_later_is_search(self):
        self.assertEqual(launch.parse(['nginx', '--help']), ('search', 'nginx --help'))

    def test_unknown_option(self):
        for flag in ('-x', '--version', '-', '-bash'):
            with self.subTest(flag):
                self.assertEqual(launch.parse([flag]), ('unknown', flag))
                self.assertEqual(launch.parse([flag, 'nginx']), ('unknown', flag))

    def test_dash_later_is_search(self):
        self.assertEqual(launch.parse(['nginx', '-v']), ('search', 'nginx -v'))

    def test_double_dash_searches_rest(self):
        self.assertEqual(launch.parse(['--', '-bash:', 'command', 'not', 'found']),
                         ('search', '-bash: command not found'))

    def test_double_dash_beats_flags(self):
        for flag in ('--help', '-h', '-x', '--'):
            with self.subTest(flag):
                self.assertEqual(launch.parse(['--', flag]), ('search', flag))

    def test_double_dash_alone(self):
        self.assertEqual(launch.parse(['--']), (None, None))
        self.assertEqual(launch.parse(['--', ' ']), (None, None))

    def test_double_dash_later_is_search(self):
        self.assertEqual(launch.parse(['nginx', '--', 'x']), ('search', 'nginx -- x'))

    def test_args_untouched(self):
        args = ['--', 'nginx']
        launch.parse(args)
        self.assertEqual(args, ['--', 'nginx'])

    def test_usage_covers_every_way(self):
        for text in ('holo words', 'holo schedule', 'holo "nginx; ERR504"', 'holo -- -words'):
            with self.subTest(text):
                self.assertIn(text, launch.USAGE)

    def test_usage_has_no_paths(self):
        self.assertNotIn('.md', launch.USAGE)
        self.assertNotIn('path', launch.USAGE)
