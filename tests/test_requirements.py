import unittest

from core import check_requirements as req

LINES = ['colorama', 'lzstring', 'windows-curses; sys_platform == "win32"', 'tzdata; sys_platform == "win32"']


class Plan(unittest.TestCase):
    def test_split(self):
        required, optional = req.plan(LINES)
        self.assertEqual(required, ['colorama', 'lzstring', 'tzdata; sys_platform == "win32"'])
        self.assertEqual(optional, ['windows-curses; sys_platform == "win32"'])

    def test_skipped_not_retried(self):
        skipped = {req._key('windows-curses')}
        self.assertEqual(req.plan(LINES, skipped)[1], [])

    def test_other_version_retried(self):
        self.assertEqual(len(req.plan(LINES, {'windows-curses 2.0'})[1]), 1)

    def test_name(self):
        self.assertEqual(req._name('Windows_Curses>=2.3; sys_platform == "win32"'), 'windows-curses')
