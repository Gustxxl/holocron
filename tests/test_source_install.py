import hashlib
import io
import json
import ssl
import subprocess
import tarfile
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock

from core.sources import cli, macos
from screens import sources_screen


class _Proc:
    def __init__(self, lines, code):
        self.stdout = iter(lines)
        self.code = code

    def wait(self):
        return self.code


def _install(lines, code):
    with mock.patch.object(macos.cli, 'which', return_value='/x/brew'), \
         mock.patch.object(macos.subprocess, 'Popen', return_value=_Proc(lines, code)), \
         mock.patch('builtins.print'):
        return macos.install('sample/tap/tool')


class Install(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(_install(['done\n'], 0), 'ok')

    def test_clt_outdated(self):
        self.assertEqual(_install(['Error:\n', ' Your Command Line Tools are too outdated.\n'], 1), 'clt')

    def test_other_error(self):
        self.assertEqual(_install(['Error: no network\n'], 1), 'failed')

    def test_output_shown(self):
        with mock.patch.object(macos.cli, 'which', return_value='/x/brew'), \
             mock.patch.object(macos.subprocess, 'Popen', return_value=_Proc(['step one\n'], 0)), \
             mock.patch('builtins.print') as out:
            macos.install('sample/tap/tool')
        out.assert_any_call('step one\n', end='', flush=True)

    def test_interrupted(self):
        with mock.patch.object(macos.cli, 'which', return_value='/x/brew'), \
             mock.patch.object(macos.subprocess, 'Popen', side_effect=KeyboardInterrupt):
            self.assertEqual(macos.install('sample/tap/tool'), 'failed')


class _Source:
    NAME = 'Sample'
    PROGRAM = 'sampletool'
    TAP = 'sample/tap/sampletool'
    REPO = 'sample/sampletool'
    ABOUT = 'sample items'
    PRIVACY = 'Sample'
    MACOS = 14


    def status(self):
        return 'missing'


def _tar(name, data):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tf:
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _zip(name, data):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr(name, data)
    return buf.getvalue()


class Setup(unittest.TestCase):
    def run_setup(self, commands, result='failed', brew=True):
        with mock.patch.object(sources_screen, 'clear_screen'), \
             mock.patch.object(sources_screen, 'pause'), \
             mock.patch.object(sources_screen, 'read_command', side_effect=commands), \
             mock.patch.object(sources_screen.cli, 'available', return_value=brew), \
             mock.patch.object(sources_screen.macos, 'install', return_value=result) as self.install, \
             mock.patch.object(sources_screen.macos, 'download', return_value=False) as self.download, \
             mock.patch.object(sources_screen.macos, 'open_url') as self.opened, \
             mock.patch('builtins.print') as out:
            sources_screen.source_setup(_Source())
        return '\n'.join(str(c.args[0]) for c in out.call_args_list if c.args)

    def test_clt_hint_shown(self):
        self.assertIn('Command Line Tools', self.run_setup(['brew', 'b'], 'clt'))

    def test_no_hint_on_other_error(self):
        self.assertNotIn('Command Line Tools', self.run_setup(['brew', 'b']))

    def test_clt_skips_generic_error(self):
        self.assertNotIn('Installation did not finish', self.run_setup(['brew', 'b'], 'clt'))

    def test_open_software_update(self):
        self.run_setup(['brew', 'u', 'b'], 'clt')
        self.opened.assert_called_once_with(sources_screen.macos.UPDATE_URL)

    def test_u_ignored_without_clt(self):
        self.run_setup(['brew', 'u', 'b'])
        self.opened.assert_not_called()

    def test_i_downloads(self):
        self.run_setup(['i', 'b'])
        self.download.assert_called_once_with('sample/sampletool', 'sampletool')
        self.install.assert_not_called()

    def test_brew_shown_with_homebrew(self):
        self.assertIn('brew install sample/tap/sampletool', self.run_setup(['b']))

    def test_brew_hidden_without_homebrew(self):
        text = self.run_setup(['brew', 'b'], brew=False)
        self.assertNotIn('brew install', text)
        self.install.assert_not_called()


class Download(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bin = Path(tmp.name) / 'bin'
        patch = mock.patch.object(macos.cli, 'BIN', self.bin)
        patch.start()
        self.addCleanup(patch.stop)

    def serve(self, files):
        release = {'assets': [{'name': n, 'browser_download_url': f'https://x/{n}'} for n in files]}

        def urlopen(url, timeout=None):
            return io.BytesIO(json.dumps(release).encode() if 'api.github.com' in url else files[url[10:]])
        return mock.patch.object(macos.urllib.request, 'urlopen', side_effect=urlopen)

    def installed(self):
        path = self.bin / 'sampletool'
        return path.read_bytes() if path.exists() else None

    def test_tar(self):
        with self.serve({'sampletool-v1.tar.gz': _tar('sampletool', b'tool')}):
            self.assertTrue(macos.download('sample/sampletool', 'sampletool'))
        self.assertEqual(self.installed(), b'tool')

    def test_nested_zip(self):
        with self.serve({'sampletool-macos-universal.zip': _zip('dist/sampletool', b'tool')}):
            self.assertTrue(macos.download('sample/sampletool', 'sampletool'))
        self.assertEqual(self.installed(), b'tool')

    def test_checksum_ok(self):
        data = _tar('sampletool', b'tool')
        digest = hashlib.sha256(data).hexdigest().encode()
        with self.serve({'sampletool-v1.tar.gz': data, 'sampletool-v1.tar.gz.sha256': digest + b'  sampletool-v1.tar.gz\n'}):
            self.assertTrue(macos.download('sample/sampletool', 'sampletool'))

    def test_checksum_mismatch(self):
        with self.serve({'sampletool-v1.tar.gz': _tar('sampletool', b'tool'),
                         'sampletool-v1.tar.gz.sha256': b'0' * 64}):
            self.assertFalse(macos.download('sample/sampletool', 'sampletool'))
        self.assertIsNone(self.installed())

    def test_no_archive(self):
        with self.serve({'notes.txt': b''}):
            self.assertFalse(macos.download('sample/sampletool', 'sampletool'))

    def test_binary_missing_in_archive(self):
        with self.serve({'sampletool-v1.tar.gz': _tar('other', b'x')}):
            self.assertFalse(macos.download('sample/sampletool', 'sampletool'))
        self.assertIsNone(self.installed())

    def test_offline(self):
        with mock.patch.object(macos.urllib.request, 'urlopen', side_effect=OSError('offline')):
            self.assertFalse(macos.download('sample/sampletool', 'sampletool'))

    def test_checksums_file(self):
        data = _zip('sampletool', b'tool')
        digest = hashlib.sha256(data).hexdigest().encode()
        sums = b'abc  inventory.json\n' + digest + b'  sampletool-macos.zip\n'
        with self.serve({'sampletool-macos.zip': data, 'checksums.txt': sums}):
            self.assertTrue(macos.download('sample/sampletool', 'sampletool'))

    def test_checksums_file_mismatch(self):
        sums = b'0' * 64 + b'  sampletool-macos.zip\n'
        with self.serve({'sampletool-macos.zip': _zip('sampletool', b'tool'), 'checksums.txt': sums}):
            self.assertFalse(macos.download('sample/sampletool', 'sampletool'))
        self.assertIsNone(self.installed())

    def test_ssl_falls_back_to_curl(self):
        release = json.dumps({'assets': [{'name': 'sampletool-v1.tar.gz',
                                          'browser_download_url': 'https://x/sampletool-v1.tar.gz'}]}).encode()
        data = _tar('sampletool', b'tool')

        def curl(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, release if 'api.github.com' in cmd[-1] else data, b'')
        err = urllib.error.URLError(ssl.SSLCertVerificationError('bad cert'))
        with mock.patch.object(macos.urllib.request, 'urlopen', side_effect=err), \
             mock.patch.object(macos.subprocess, 'run', side_effect=curl):
            self.assertTrue(macos.download('sample/sampletool', 'sampletool'))
        self.assertEqual(self.installed(), b'tool')


class Which(unittest.TestCase):
    def test_local_copy_first(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(cli, 'BIN', Path(d)):
            (Path(d) / 'sampletool').write_bytes(b'')
            self.assertEqual(cli.which('sampletool'), str(Path(d) / 'sampletool'))


if __name__ == '__main__':
    unittest.main()
