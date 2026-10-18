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


if __name__ == '__main__':
    unittest.main()
