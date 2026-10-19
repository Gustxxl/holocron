import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from core import excalidraw

from core.archives import excalidraw_plain
from core.excalidraw import load_cases
from screens import search_screen
from core import backups


def setUpModule():
    tmp = tempfile.TemporaryDirectory()
    patch = mock.patch.object(backups, 'DIR', Path(tmp.name))
    patch.start()
    unittest.addModuleCleanup(patch.stop)
    unittest.addModuleCleanup(tmp.cleanup)

BACKUPS = Path(__file__).resolve().parent.parent / 'data' / 'backups'
TEXT = '🔥 Prod down'
SCENE = {'type': 'excalidraw', 'elements': [
    {'id': 'a1', 'type': 'text', 'x': 0, 'y': 0, 'text': TEXT, 'originalText': TEXT},
]}
DRAWING = '---\nexcalidraw-plugin: parsed\n---\n\n## Drawing\n```json\n' + json.dumps(SCENE, ensure_ascii=False) + '\n```\n'
BOARD = {'type': 'excalidraw', 'elements': [
    {'id': 'a1', 'type': 'text', 'x': 0, 'y': 0, 'text': TEXT, 'originalText': TEXT},
    {'id': 'b2', 'type': 'text', 'x': 0, 'y': 100, 'text': '🚀 Deploy', 'originalText': '🚀 Deploy'},
]}
COMPRESSED = ('---\nexcalidraw-plugin: parsed\n---\n\n## Text Elements\n'
              f'{TEXT} ^a1\n\n🚀 Deploy ^b2\n\n%%\n## Drawing\n```compressed-json\n'
              + excalidraw.compress_to_base64(json.dumps(BOARD, ensure_ascii=False)) + '\n```\n%%\n')
FENCE = 'Use\n\n```json\n{"a": 1}\n```'
FENCED = ('## Text Elements\n' f'{FENCE} ^a1\n\n%%\n## Drawing\n```json\n'
          + json.dumps({'type': 'excalidraw', 'elements': [
              {'id': 'a1', 'type': 'text', 'x': 0, 'y': 0, 'text': FENCE, 'originalText': FENCE}]})
          + '\n```\n%%\n')


def _temp(test, suffix, text):
    fd, name = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text)
    path = Path(name)
    test.addCleanup(path.unlink, missing_ok=True)
    test.addCleanup((BACKUPS / path.name).unlink, missing_ok=True)
    return path


class Raw(unittest.TestCase):
    def test_obsidian_keeps_raw(self):
        case = load_cases(_temp(self, '.md', DRAWING))[0]
        self.assertEqual((case['text'], case['raw']), ('Prod down', TEXT))

    def test_plain_keeps_raw(self):
        case = excalidraw_plain._load_scene(_temp(self, '.excalidraw', json.dumps(SCENE, ensure_ascii=False)))[0]
        self.assertEqual((case['text'], case['raw']), ('Prod down', TEXT))


class Edit(unittest.TestCase):
    def edit(self, path, change):
        case = load_cases(path)[0]
        with mock.patch.object(search_screen, 'show_case', return_value=[]), \
             mock.patch.object(search_screen, 'read_command', side_effect=['e', 'b']), \
             mock.patch.object(search_screen, '_refresh', side_effect=lambda results, *a, **k: results), \
             mock.patch.object(search_screen, 'haptic'), \
             mock.patch.object(search_screen.editor, 'available', return_value=True), \
             mock.patch.object(search_screen.editor, 'edit_text', side_effect=change) as edit:
            search_screen.open_case([(0, case)], 1, '')
        return case, edit

    def test_editor_gets_raw_text(self):
        _, edit = self.edit(_temp(self, '.md', DRAWING), lambda t: t.replace('down', 'up'))
        edit.assert_called_once_with(TEXT)

    def test_emoji_kept_on_board(self):
        path = _temp(self, '.md', DRAWING)
        self.edit(path, lambda t: t.replace('down', 'up'))
        self.assertEqual(load_cases(path)[0]['raw'], '🔥 Prod up')

    def test_case_updated_after_save(self):
        case, _ = self.edit(_temp(self, '.md', DRAWING), lambda t: t.replace('down', 'up'))
        self.assertEqual((case['text'], case['raw']), ('Prod up', '🔥 Prod up'))

    def test_unchanged_text_not_saved(self):
        path = _temp(self, '.md', DRAWING)
        before = path.read_text(encoding='utf-8')
        self.edit(path, lambda t: t)
        self.assertEqual(path.read_text(encoding='utf-8'), before)

    def test_conflict_keeps_disk_and_copies_text(self):
        path = _temp(self, '.md', DRAWING)

        def change(_):
            excalidraw.update_text_obsidian(str(path), 'a1', 'from elsewhere')
            return 'mine'

        with mock.patch.object(search_screen, 'error') as err, \
             mock.patch.object(search_screen, 'copy_text', return_value=True) as copy:
            self.edit(path, change)
        self.assertEqual(load_cases(path)[0]['raw'], 'from elsewhere')
        copy.assert_called_once_with('mine')
        self.assertIn('copied', err.call_args[0][0])


class Compressed(unittest.TestCase):
    def test_utf16_pairs(self):
        self.assertEqual(excalidraw._to_utf16('🔥a'), '\ud83d\udd25a')
        self.assertEqual(excalidraw._from_utf16('\ud83d\udd25a'), '🔥a')

    def test_roundtrip(self):
        s = json.dumps(BOARD, ensure_ascii=False)
        self.assertEqual(excalidraw.decompress_from_base64(excalidraw.compress_to_base64(s)), s)

    def test_loads_emoji(self):
        cases = load_cases(_temp(self, '.md', COMPRESSED))
        self.assertEqual([c['raw'] for c in cases], [TEXT, '🚀 Deploy'])

    def test_edit_keeps_other_blocks(self):
        path = _temp(self, '.md', COMPRESSED)
        excalidraw.update_text_obsidian(str(path), 'a1', '🔥 Prod up')
        self.assertEqual([c['raw'] for c in load_cases(path)], ['🔥 Prod up', '🚀 Deploy'])

    def test_paragraphs_do_not_grow(self):
        path = _temp(self, '.md', COMPRESSED)
        excalidraw.update_text_obsidian(str(path), 'a1', 'Title\n\nBody one')
        excalidraw.update_text_obsidian(str(path), 'a1', 'Title\n\nBody two')
        md = path.read_text(encoding='utf-8')
        self.assertEqual(md.count('Title'), 1)
        self.assertIn('Title\n\nBody two ^a1\n\n🚀 Deploy ^b2', md)
        self.assertEqual([c['raw'] for c in load_cases(path)], ['Title\n\nBody two', '🚀 Deploy'])

    def test_paragraphs_in_second_block(self):
        path = _temp(self, '.md', COMPRESSED)
        excalidraw.update_text_obsidian(str(path), 'b2', 'Head\n\nOne')
        excalidraw.update_text_obsidian(str(path), 'b2', 'Head\n\nTwo')
        md = path.read_text(encoding='utf-8')
        self.assertIn(f'{TEXT} ^a1\n\nHead\n\nTwo ^b2', md)
        self.assertEqual(md.count('Head'), 1)

    def test_similar_id_untouched(self):
        md = '## Text Elements\nfirst ^a12\n\nsecond ^a1\n\n## Drawing\n'
        out = excalidraw._replace_text_element(md, 'a1', 'new')
        self.assertEqual(out, '## Text Elements\nfirst ^a12\n\nnew ^a1\n\n## Drawing\n')


class Safety(unittest.TestCase):
    def test_expected_matches(self):
        path = _temp(self, '.md', COMPRESSED)
        excalidraw.update_text_obsidian(str(path), 'a1', 'new', expected=TEXT)
        self.assertEqual(load_cases(path)[0]['raw'], 'new')

    def test_changed_on_disk(self):
        path = _temp(self, '.md', COMPRESSED)
        excalidraw.update_text_obsidian(str(path), 'a1', 'other')
        with self.assertRaises(ValueError):
            excalidraw.update_text_obsidian(str(path), 'a1', 'mine', expected=TEXT)
        self.assertEqual(load_cases(path)[0]['raw'], 'other')
        self.assertIn('other ^a1', path.read_text(encoding='utf-8'))

    def test_plain_changed_on_disk(self):
        path = _temp(self, '.excalidraw', json.dumps(SCENE, ensure_ascii=False))
        excalidraw.update_text(str(path), 'a1', 'other')
        with self.assertRaises(ValueError):
            excalidraw.update_text(str(path), 'a1', 'mine', expected=TEXT)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['elements'][0]['text'], 'other')

    def test_no_temp_left(self):
        path = _temp(self, '.md', COMPRESSED)
        excalidraw.update_text_obsidian(str(path), 'a1', 'new')
        self.assertFalse(path.with_name(f'.{path.name}.tmp').exists())

    def test_failed_write_keeps_file(self):
        path = _temp(self, '.md', COMPRESSED)
        before = path.read_text(encoding='utf-8')
        with mock.patch.object(excalidraw.os, 'replace', side_effect=OSError):
            with self.assertRaises(OSError):
                excalidraw.update_text_obsidian(str(path), 'a1', 'new')
        self.assertEqual(path.read_text(encoding='utf-8'), before)
        self.assertFalse(path.with_name(f'.{path.name}.tmp').exists())

    def test_json_fence_in_block(self):
        path = _temp(self, '.md', FENCED)
        self.assertEqual(load_cases(path)[0]['raw'], FENCE)
        excalidraw.update_text_obsidian(str(path), 'a1', 'Use\n\nplain')
        self.assertEqual(load_cases(path)[0]['raw'], 'Use\n\nplain')
        self.assertNotIn('{"a": 1}', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
