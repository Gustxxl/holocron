import os
import stat
import sys
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import install


class Remove(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.launcher = self.root / 'holo'
        self.tools = self.root / 'data' / 'bin'
        self.brew = self.root / 'brew'
        for patch in (mock.patch.object(install, '_posix_target', return_value=self.launcher),
                      mock.patch.object(install, '_windows_target', return_value=self.launcher),
                      mock.patch.object(install, 'TOOLS', self.tools),
                      mock.patch.object(install, 'BREW', (str(self.brew),))):
            patch.start()
            self.addCleanup(patch.stop)

    def run_remove(self):
        with redirect_stdout(io. StringIO()) as out:
            install.remove()
        return out.getvalue()

    def file(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'')
        return path

    def test_downloaded_tools_removed(self):
        self.file(self.launcher)
        tool = self.file(self.tools / 'remindctl')
        out = self.run_remove()
        self.assertFalse(self.launcher.exists())
        self.assertFalse(tool.exists())
        self.assertIn(f'Removed: {tool}', out)

    def test_data_kept(self):
        config = self.file(self.root / 'data' / 'config.json')
        self.file(self.tools / 'ekctl')
        self.run_remove()
        self.assertTrue(config.exists())

    def test_homebrew_tools_kept(self):
        cellar = self.file(self.root / 'Cellar' / 'remindctl' / '0.3.8' / 'bin' / 'remindctl')
        self.brew.mkdir()
        (self.brew / 'remindctl').symlink_to(cellar)
        out = self.run_remove()
        self.assertTrue(cellar.exists())
        self.assertIn('brew uninstall remindctl', out)

    def test_nothing_to_remove(self):
        self.assertIn('Nothing to remove.', self.run_remove())


class Launcher(unittest.TestCase):
    @unittest.skipIf(os.name == 'nt', 'POSIX launcher')
    def test_posix_keeps_start_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'bin' / 'holo'
            with mock.patch.object(install, '_posix_target', return_value=target):
                path, _ = install._install_posix()
            self.assertEqual(path, target)
            self.assertEqual(target.read_text(encoding='utf-8').split('\n'), [
                '#!/bin/sh',
                'export HOLO_CWD="$PWD"',
                f'cd "{install.APP_DIR}" && exec "{sys.executable}" "{install.MAIN}" "$@"',
                '',
            ])
            self.assertTrue(target.stat().st_mode & stat.S_IXUSR)

    def test_windows_keeps_start_folder(self):
        target = mock.Mock()
        with mock.patch.object(install, '_windows_target', return_value=target):
            self.assertEqual(install._install_windows(), (target, True))
        self.assertEqual(target.write_text.call_args.args[0].split('\r\n'), [
            '@echo off',
            'setlocal',
            'set "HOLO_CWD=%CD%"',
            f'cd /d "{install.APP_DIR}"',
            f'"{sys.executable}" "{install.MAIN}" %*',
            '',
        ])
        self.assertEqual(target.write_text.call_args.kwargs, {'encoding': 'oem'})


if __name__ == '__main__':
    unittest.main()
