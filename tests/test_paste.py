import io
import os
import unittest
from unittest import mock

from screens import keeper_screen, main_screen, search_screen
from ui import interface


class Tty(io.StringIO):
    def isatty(self):
        return True


def _size(cols):
    return mock.patch.object(interface.shutil, 'get_terminal_size', return_value=os.terminal_size((cols, 24)))


def _printed(printed):
    return '\n'.join(str(c.args[0]) if c.args else '' for c in printed.call_args_list)


class Paste(unittest.TestCase):
    def read(self, first, extra, prompt='Keeper> ', cols=20, tty=True):
        out = Tty() if tty else io.StringIO()
        with mock.patch('builtins.input', return_value=first), \
             mock.patch.object(interface, '_drain', return_value=extra), \
             _size(cols), mock.patch.object(interface.sys, 'stdout', out):
            line = interface.read_command(prompt)
        return line, out.getvalue()

    def test_single_line_not_redrawn(self):
        self.assertEqual(self.read('  alpha beta  ', ''), ('alpha beta', ''))

    def test_paste_redrawn_as_one_line(self):
        line, out = self.read('-----', 'Tool\n---\nOK\n')
        self.assertEqual(line, '----- Tool --- OK')
        self.assertEqual(out, '\033[1A\r\033[JKeeper> ----- Tool --- OK\n')

    def test_long_first_line_wrapped(self):
        _, out = self.read('x' * 30, 'tail')
        self.assertTrue(out.startswith('\033[2A\r\033[J'))

    def test_exact_width_is_one_row(self):
        _, out = self.read('x' * 12, 'tail')
        self.assertTrue(out.startswith('\033[1A'))

    def test_trailing_spaces_count(self):
        _, out = self.read('x' * 10 + ' ' * 5, 'tail')
        self.assertTrue(out.startswith('\033[2A'))

    def test_empty_first_line(self):
        self.assertEqual(self.read('', 'Alpha'), ('Alpha', '\033[1A\r\033[JKeeper> Alpha\n'))

    def test_colored_prompt(self):
        _, out = self.read('x' * 17, 'tail', prompt=interface.dim('> '))
        self.assertTrue(out.startswith('\033[1A'))

    def test_cyrillic(self):
        line, out = self.read('Сумма 1 280.18', 'не равна 1 280.2')
        self.assertEqual(line, 'Сумма 1 280.18 не равна 1 280.2')
        self.assertEqual(out, '\033[2A\r\033[JKeeper> Сумма 1 280.18 не равна 1 280.2\n')

    def test_wide_characters(self):
        self.assertTrue(self.read('界' * 6, 'tail')[1].startswith('\033[1A'))
        self.assertTrue(self.read('界' * 7, 'tail')[1].startswith('\033[2A'))

    def test_not_a_terminal(self):
        self.assertEqual(self.read('-----', 'Tool', tty=False), ('----- Tool', ''))


class Lines(unittest.TestCase):
    read = Paste.read

    def keep(self, first, extra, cols=20):
        out = Tty()
        with mock.patch('builtins.input', return_value=first), \
             mock.patch.object(interface, '_drain', return_value=extra), \
             _size(cols), mock.patch.object(interface.sys, 'stdout', out):
            line = interface.read_command('Keeper> ', lines=True)
        return line, out.getvalue()

    def test_paste_keeps_lines(self):
        line, out = self.keep('-----', 'Tool\n---\nOK   \n')
        self.assertEqual(line, '-----\nTool\n---\nOK')
        self.assertEqual(out, '\033[1A\r\033[JKeeper> -----\n        Tool\n        ---\n        OK\n')

    def test_inner_blank_lines_kept_edges_dropped(self):
        self.assertEqual(self.keep('', '\n\nAlpha\n\nBeta\n\n')[0], 'Alpha\n\nBeta')

    def test_crlf(self):
        self.assertEqual(self.keep('Alpha', 'Beta\r\nGamma\r\n')[0], 'Alpha\nBeta\nGamma')

    def test_cyrillic(self):
        line, out = self.keep('Сумма 1 280.18', 'не равна 1 280.2')
        self.assertEqual(line, 'Сумма 1 280.18\nне равна 1 280.2')
        self.assertEqual(out, '\033[2A\r\033[JKeeper> Сумма 1 280.18\n        не равна 1 280.2\n')

    def test_single_line_not_redrawn(self):
        self.assertEqual(self.keep('  alpha beta  ', ''), ('alpha beta', ''))

    def test_lines_from_readline(self):
        self.assertEqual(self.keep('Alpha\nBeta', '')[0], 'Alpha\nBeta')
        self.assertEqual(self.read('Alpha\nBeta', '')[0], 'Alpha Beta')

    def test_quit_still_works(self):
        with mock.patch.object(interface, 'quit_app', side_effect=SystemExit) as quit_app:
            with self.assertRaises(SystemExit):
                self.keep('q', '')
        quit_app.assert_called_once_with()


class Block(unittest.TestCase):
    def test_single_line(self):
        self.assertEqual(interface.input_block('> ', 'alpha'), '> alpha')

    def test_lines_aligned_under_text(self):
        self.assertEqual(interface.input_block('Keeper> ', 'a\nb'), 'Keeper> a\n        b')

    def test_colored_prompt(self):
        self.assertEqual(interface.input_block(interface.dim('> '), 'a\nb'), interface.dim('> ') + 'a\n  b')

    def test_empty_lines(self):
        self.assertEqual(interface.input_block('> ', 'a\n\nb'), '> a\n  \n  b')
        self.assertEqual(interface.input_block('> ', ''), '> ')

    def test_rows(self):
        with _size(10):
            self.assertEqual(interface.input_rows('> ', 'alpha'), 1)
            self.assertEqual(interface.input_rows('> ', 'a\nb\nc'), 3)
            self.assertEqual(interface.input_rows('> ', 'a\n' + 'x' * 15), 3)
            self.assertEqual(interface.input_rows('> ', '界' * 5), 2)

    def test_one_line(self):
        self.assertEqual(interface.one_line(' a \n\n b  c \n'), 'a b  c')
        self.assertEqual(interface.one_line(''), '')


class Screens(unittest.TestCase):
    def test_keeper_redraws_block(self):
        with _size(40), mock.patch('builtins.print') as printed:
            keeper_screen._drop_nav('a\nb', 1)
        up = 2 + keeper_screen.NAV_ROWS + 1
        printed.assert_called_once_with(f'\033[{up}A\033[JKeeper> a\n        b')

    def test_keeper_history_keeps_lines(self):
        out = io.StringIO()
        with mock.patch.object(keeper_screen, '_print_answer'), mock.patch.object(keeper_screen, '_nav'), \
             mock.patch('sys.stdout', out):
            keeper_screen._draw([{'question': 'a\nb'}], [], None, 'c\nd', {'slot': 'local'})
        self.assertIn('Keeper> a\n        b\n', out.getvalue())
        self.assertIn('Keeper> c\n        d\n', out.getvalue())

    def test_keeper_reads_lines(self):
        with mock.patch.object(keeper_screen, '_redraw', return_value=('local', 0)), \
             mock.patch.object(keeper_screen, 'read_command', side_effect=['b']) as read:
            keeper_screen.keeper_screen()
        read.assert_called_once_with('Keeper> ', lines=True)

    def test_search_reads_lines(self):
        with mock.patch.object(search_screen.archives, 'cases', return_value=[{'text': 'Alpha'}]), \
             mock.patch.object(search_screen, 'clear_screen'), mock.patch('builtins.print'), \
             mock.patch.object(search_screen, 'read_command', side_effect=['b']) as read:
            search_screen.search_screen()
        read.assert_called_once_with('search> ', lines=True)

    def test_asked(self):
        self.assertEqual(search_screen._asked('Alpha\nBeta', 40), '   Alpha\n   Beta')
        self.assertEqual(search_screen._asked('Alpha\nBeta', 40, indent=''), '   Alpha\n   Beta')
        self.assertEqual(search_screen._asked('Alpha', 40, indent=''), '"Alpha"')

    def test_case_head(self):
        lines = search_screen._case_head('1/2  ', 'note', 'Vault', '', 'Alpha\nBeta', 60)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith('── 1/2  note (Vault)'))
        self.assertNotIn('Alpha', lines[0])
        self.assertEqual(lines[1], '   Alpha\n   Beta')

    def test_list_header(self):
        with _size(80), mock.patch.object(search_screen, 'clear_screen'), \
             mock.patch.object(search_screen, 'list_rows', return_value=['row']), \
             mock.patch('builtins.print') as printed:
            search_screen.show_list([(0, {'text': 'Alpha'})], 0, 'Alpha\nBeta')
        out = _printed(printed)
        self.assertIn('   Alpha\n   Beta', out)
        self.assertNotIn('Search: "', out)

    def test_nothing_found(self):
        with _size(80), mock.patch.object(search_screen.archives, 'cases', return_value=[{'text': 'Alpha'}]), \
             mock.patch.object(search_screen, '_too_short', return_value=False), \
             mock.patch.object(search_screen, '_run', return_value=([], None, 'Gamma\nDelta', False)), \
             mock.patch.object(search_screen, '_suggest', return_value=[]), \
             mock.patch.object(search_screen, 'clear_screen'), mock.patch.object(search_screen, 'error_haptic'), \
             mock.patch.object(search_screen, 'read_command', side_effect=['b']), \
             mock.patch('builtins.print') as printed:
            search_screen.search_screen('Gamma\nDelta')
        self.assertIn('Nothing found for:\n   Gamma\n   Delta', _printed(printed))

    def test_main_reads_lines(self):
        with mock.patch.object(main_screen, 'main_frame', return_value=''), \
             mock.patch.object(main_screen, 'clear_screen'), mock.patch('builtins.print'), \
             mock.patch.object(main_screen, 'read_command', side_effect=SystemExit) as read:
            with self.assertRaises(SystemExit):
                main_screen.main_screen()
        read.assert_called_once_with('system> ', lines=True)

    def test_main_commands_get_one_line(self):
        command = mock. Mock()
        with mock.patch.object(main_screen, 'lookup', return_value=command) as lookup:
            main_screen._handle('note\nalpha')
        lookup.assert_called_once_with('note alpha')
        command.run.assert_called_once_with('note alpha')

    def test_main_search_keeps_lines(self):
        with mock.patch.object(main_screen, 'lookup', return_value=None), \
             mock.patch.object(main_screen.archives, 'is_loaded', return_value=True), \
             mock.patch.object(main_screen, 'search_screen') as search:
            main_screen._handle('Alpha\nBeta')
        search.assert_called_once_with('Alpha\nBeta')


class Rows(unittest.TestCase):
    def rows(self, text, cols=10):
        with _size(cols):
            return interface.screen_rows(text)

    def test_bounds(self):
        self.assertEqual([self.rows('x' * n) for n in (0, 1, 10, 11, 20, 21)], [1, 1, 1, 2, 2, 3])

    def test_escape_codes_ignored(self):
        self.assertEqual(self.rows(interface.dim('x' * 10)), 1)

    def test_zero_width_terminal(self):
        self.assertEqual(self.rows('xxx', cols=0), 3)


if __name__ == '__main__':
    unittest.main()
