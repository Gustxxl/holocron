import os
import unittest
from unittest.mock import patch

from core import editor

ORIGINAL = 'Привет\nмир ✓'


class EditText(unittest.TestCase):
    def _run(self, write=None, ok=True, cmd=('fake-editor',), crash=None):
        seen = {}

        def attach(args):
            seen['path'] = args[-1]
            with open(args[-1], encoding='utf-8') as f:
                seen['before'] = f.read()
            if crash:
                raise crash
            if write is not None:
                with open(args[-1], 'w', encoding='utf-8') as f:
                    f.write(write)
            return ok

        with patch.object(editor.system, 'editor', return_value=list(cmd) if cmd else None), \
             patch.object(editor.system, 'attach', side_effect=attach) as attached:
            result = editor.edit_text(ORIGINAL)
        return result, seen, attached

    def test_returns_edited_text(self):
        result, _, _ = self._run(write='Новый текст')
        self.assertEqual(result, 'Новый текст')

    def test_editor_gets_original_in_utf8(self):
        _, seen, _ = self._run()
        self.assertEqual(seen['before'], ORIGINAL)

    def test_unchanged_text_comes_back_as_is(self):
        result, _, _ = self._run()
        self.assertEqual(result, ORIGINAL)

    def test_temp_file_removed(self):
        _, seen, _ = self._run(write='x')
        self.assertFalse(os.path.exists(seen['path']))

    def test_editor_failed(self):
        result, seen, _ = self._run(ok=False)
        self.assertIsNone(result)
        self.assertFalse(os.path.exists(seen['path']))

    def test_no_editor(self):
        result, _, attached = self._run(cmd=None)
        self.assertIsNone(result)
        attached.assert_not_called()

    def test_temp_file_removed_on_ctrl_c(self):
        with self.assertRaises(KeyboardInterrupt):
            self._run(crash=KeyboardInterrupt())
        leftovers = [n for n in os.listdir(editor.tempfile.gettempdir())
                     if n.endswith('.txt') and os.path.getsize(os.path.join(editor.tempfile.gettempdir(), n)) == len(ORIGINAL.encode())]
        self.assertEqual(leftovers, [])
