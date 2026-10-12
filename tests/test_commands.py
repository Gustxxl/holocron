import tempfile
import unittest
from unittest.mock import patch

from core import commands


class Lookup(unittest.TestCase):
    def test_alias_and_case(self):
        self.assertEqual(commands.lookup(' S ').name, 'settings')

    def test_unknown(self):
        self.assertIsNone(commands.lookup('nginx'))


class Note(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def _found(self, folder, has_editor=True):
        with patch.object(commands, 'new_cases_path', return_value=folder), \
             patch.object(commands.editor, 'available', return_value=has_editor):
            return commands.lookup('note') is not None

    def test_available_with_folder_and_editor(self):
        self.assertTrue(self._found(self.dir))

    def test_hidden_without_folder(self):
        self.assertFalse(self._found(''))

    def test_hidden_when_folder_missing(self):
        self.assertFalse(self._found(self.dir + '/nope'))

    def test_hidden_without_editor(self):
        self.assertFalse(self._found(self.dir, has_editor=False))
