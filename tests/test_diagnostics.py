import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import diagnostics

PROBE = '''
import unittest


class Probe(unittest.TestCase):
    def test_ok(self):
        print('noise')

    def test_bad(self):
        self.assertEqual(1, 2)

    def test_input(self):
        input()
'''


class Run(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        Path(tmp.name, 'test_diag_probe.py').write_text(PROBE, encoding='utf-8')
        self.addCleanup(sys.modules.pop, 'test_diag_probe', None)
        p = patch.object(diagnostics, 'TESTS', Path(tmp.name))
        p.start()
        self.addCleanup(p.stop)

    def test_report(self):
        calls, out = [], io.StringIO()
        path, stdin = list(sys.path), sys.stdin
        with patch('sys.stdout', out):
            report = diagnostics.run(lambda *a: calls.append(a))
        self.assertEqual((report['total'], report['passed'], report['skipped']), (3, 1, 0))
        self.assertEqual([label for label, _ in report['failed']],
                         ['diag_probe · Probe.test_bad', 'diag_probe · Probe.test_input'])
        self.assertIn('EOFError', report['failed'][1][1])
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1], (3, 3, 'diag_probe'))
        self.assertNotIn('noise', out.getvalue())
        self.assertEqual(sys.path, path)
        self.assertIs(sys.stdin, stdin)

    def test_available(self):
        self.assertTrue(diagnostics.available())
        with patch.object(diagnostics, 'TESTS', Path('/nonexistent/tests')):
            self.assertFalse(diagnostics.available())


class Reason(unittest.TestCase):
    def test_assertion_with_diff(self):
        tb = ('Traceback (most recent call last):\n'
              '  File "t.py", line 3, in test_x\n'
              '    self.assertEqual(a, b)\n'
              '    ~~~~~~~~~~~~~~~~^^^^^^\n'
              "AssertionError: 'a' != 'b'\n"
              '- a\n'
              '+ b\n'
              '? ^\n')
        self.assertEqual(diagnostics.reason(tb), "AssertionError: 'a' != 'b'")

    def test_import_error(self):
        tb = ('ImportError: Failed to import test module: test_x\n'
              'Traceback (most recent call last):\n'
              '  File "loader.py", line 1, in find\n'
              '    __import__(name)\n'
              "NameError: name 'x' is not defined\n")
        self.assertEqual(diagnostics.reason(tb), "NameError: name 'x' is not defined")

    def test_empty(self):
        self.assertEqual(diagnostics.reason(''), '')
