import os
import unittest
from unittest import mock

from screens import search_screen
from ui.note import drop_title


class DropTitle(unittest.TestCase):
    def test_first_line_like_note_writes_it(self):
        self.assertEqual(drop_title('Alpha plan\nStep one', 'Alpha plan'), 'Step one')

    def test_heading(self):
        self.assertEqual(drop_title('# Alpha plan\n\nStep one', 'Alpha plan'), 'Step one')

    def test_case_ignored(self):
        self.assertEqual(drop_title('## alpha PLAN\nStep', 'Alpha plan'), 'Step')

    def test_unsafe_characters(self):
        self.assertEqual(drop_title('Alpha: plan?\nStep', 'Alpha plan'), 'Step')

    def test_cyrillic(self):
        self.assertEqual(drop_title('# План Альфа\nШаг', 'План Альфа'), 'Шаг')

    def test_front_matter(self):
        self.assertEqual(drop_title('---\ntags: x\n---\n# Alpha plan\nStep', 'Alpha plan'), 'Step')

    def test_windows_line_ends(self):
        self.assertEqual(drop_title('Alpha plan\r\nStep\r\nMore', 'Alpha plan'), 'Step\nMore')

    def test_only_title(self):
        self.assertEqual(drop_title('# Alpha plan', 'Alpha plan'), '')

    def test_other_first_line_kept(self):
        text = 'Beta\nAlpha plan'
        self.assertEqual(drop_title(text, 'Alpha plan'), text)

    def test_longer_line_kept(self):
        text = 'Alpha plan for today\nStep'
        self.assertEqual(drop_title(text, 'Alpha plan'), text)

    def test_numbered_copy_kept(self):
        text = 'Alpha plan\nStep'
        self.assertEqual(drop_title(text, 'Alpha plan 2'), text)

    def test_empty(self):
        self.assertEqual(drop_title('', 'Alpha'), '')
        self.assertEqual(drop_title('\n\n', 'Alpha'), '\n\n')


class Screen(unittest.TestCase):
    def test_title_shown_once(self):
        case = {'text': '# Alpha plan\n\nStep one', 'filename': 'Alpha plan', 'archive': 'Vault'}
        with mock.patch('shutil.get_terminal_size', return_value=os.terminal_size((80, 24))), \
             mock.patch.object(search_screen.archives, 'cases', return_value=[]), \
             mock.patch.object(search_screen.favorites, 'is_pinned', return_value=False), \
             mock.patch.object(search_screen.editor, 'available', return_value=False), \
             mock.patch.object(search_screen.keeper, 'configured', return_value=[]), \
             mock.patch.object(search_screen, 'clear_screen'), \
             mock.patch('builtins.print') as printed:
            search_screen.show_case(case)
        out = '\n'.join(str(c.args[0]) if c.args else '' for c in printed.call_args_list)
        self.assertEqual(out.count('Alpha plan'), 1)
        self.assertIn('Step one', out)
