import json
import os
import tempfile
import unittest
from pathlib import Path

from core.excalidraw import (
    strip_emoji, clean, decompress_from_base64, compress_to_base64,
    update_text, SceneError, _validate_md, _backup,
)

BACKUPS = Path(__file__).resolve().parent.parent / 'data' / 'backups'


def _temp(test, suffix, text=''):
    fd, name = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text)
    path = Path(name)
    test.addCleanup(path.unlink, missing_ok=True)
    return path


class StripEmoji(unittest.TestCase):
    def test_plain_text(self):
        self.assertEqual(strip_emoji('hello world'), 'hello world')

    def test_with_emoji(self):
        result = strip_emoji('hello 🌍 world')
        self.assertIn('hello', result)
        self.assertIn('world', result)

    def test_preserves_newlines(self):
        self.assertEqual(strip_emoji('line1\nline2'), 'line1\nline2')

    def test_empty(self):
        self.assertEqual(strip_emoji(''), '')


class Clean(unittest.TestCase):
    def test_valid_utf8(self):
        self.assertEqual(clean('hello'), 'hello')

    def test_cyrillic(self):
        self.assertEqual(clean('привет'), 'привет')


class Compression(unittest.TestCase):
    def _round_trip(self, original):
        compressed = compress_to_base64(original)
        self.assertTrue(compressed)
        self.assertEqual(decompress_from_base64(compressed), original)

    def test_round_trip_ascii(self):
        self._round_trip('{"test": "hello world"}')

    def test_round_trip_cyrillic(self):
        self._round_trip('{"text": "привет мир"}')

    def test_round_trip_long(self):
        self._round_trip(json.dumps({'elements': [{'id': str(i), 'text': f'item {i}'} for i in range(100)]}))

    def test_empty(self):
        self.assertIsNotNone(compress_to_base64(''))
        self.assertIsNone(decompress_from_base64(''))


class UpdateText(unittest.TestCase):
    def _scene(self, elements):
        scene = {'type': 'excalidraw', 'version': 2, 'elements': elements, 'appState': {}, 'files': {}}
        return _temp(self, '.excalidraw', json.dumps(scene, ensure_ascii=False))

    def test_update_existing_element(self):
        path = self._scene([{'id': 'abc123', 'type': 'text', 'text': 'old text', 'originalText': 'old text'}])
        update_text(str(path), 'abc123', 'new text')
        el = json.loads(path.read_text(encoding='utf-8'))['elements'][0]
        self.assertEqual(el['text'], 'new text')
        self.assertEqual(el['originalText'], 'new text')

    def test_element_not_found(self):
        path = self._scene([{'id': 'abc123', 'type': 'text', 'text': 'old', 'originalText': 'old'}])
        with self.assertRaises(ValueError):
            update_text(str(path), 'nonexistent', 'new')

    def test_does_not_modify_non_text(self):
        path = self._scene([
            {'id': 'rect1', 'type': 'rectangle', 'x': 0, 'y': 0},
            {'id': 'txt1', 'type': 'text', 'text': 'keep', 'originalText': 'keep'},
        ])
        with self.assertRaises(ValueError):
            update_text(str(path), 'rect1', 'hack')
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['elements'][0]['type'], 'rectangle')


class ValidateMd(unittest.TestCase):
    def test_valid_json(self):
        _validate_md('## Drawing\n```json\n{}\n```')

    def test_valid_compressed(self):
        _validate_md('## Drawing\n```compressed-json\nABC\n```')

    def test_missing_drawing(self):
        with self.assertRaises(SceneError):
            _validate_md('```json\n{}\n```')

    def test_missing_data(self):
        with self.assertRaises(SceneError):
            _validate_md('## Drawing\nno code block')


class Backup(unittest.TestCase):
    def test_creates_backup(self):
        path = _temp(self, '.md', 'test content')
        bak = BACKUPS / path.name
        self.addCleanup(bak.unlink, missing_ok=True)
        _backup(str(path))
        self.assertTrue(bak.exists())
        self.assertEqual(bak.read_text(encoding='utf-8'), 'test content')
