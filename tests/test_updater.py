import hashlib
import io
import os
import shutil
import ssl
import sys
import tarfile
import tempfile
import unittest
import urllib.parse
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from core import updater


def _sha(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def _make(root, files):
    for path, data in files.items():
        full = os.path.join(root, *path.split('/'))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as f:
            f.write(data)


def _read(root, path):
    with open(os.path.join(root, *path.split('/')), 'rb') as f:
        return f.read()


def _tarball(files, root='holocron-abc'):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for path, data in files.items():
            info = tarfile.TarInfo(f'{root}/{path}' if root else path)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)


class CheckPath(unittest.TestCase):
    def test_safe(self):
        self.assertEqual(updater._check_path('core/x.py'), ['core', 'x.py'])

    def test_unsafe(self):
        for path in ('/etc/passwd', '../x', 'a/../b', 'a//b', './a', 'a\\b'):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                updater._check_path(path)


class BlobSha(Tmp):
    def test_matches_git(self):
        _make(self.tmp, {'empty': b'', 'hello': b'hello\n'})
        self.assertEqual(updater._git_blob_sha(os.path.join(self.tmp, 'empty')),
                         'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391')
        self.assertEqual(updater._git_blob_sha(os.path.join(self.tmp, 'hello')),
                         'ce013625030ba8dba906f756967f9e9ca394464a')


class Verify(Tmp):
    def setUp(self):
        super().setUp()
        _make(self.tmp, {'main.py': b'good', 'core/a.py': b'a'})
        self.blobs = [{'path': 'main.py', 'sha': _sha(b'good')}, {'path': 'core/a.py', 'sha': _sha(b'a')}]

    def test_ok(self):
        updater._verify(self.tmp, self.blobs)

    def test_tampered(self):
        _make(self.tmp, {'main.py': b'evil'})
        with self.assertRaisesRegex(RuntimeError, 'integrity mismatch'):
            updater._verify(self.tmp, self.blobs)

    def test_missing(self):
        os.remove(os.path.join(self.tmp, 'core', 'a.py'))
        with self.assertRaisesRegex(RuntimeError, 'missing file'):
            updater._verify(self.tmp, self.blobs)

    def test_extra_file(self):
        _make(self.tmp, {'core/backdoor.py': b'x'})
        with self.assertRaisesRegex(RuntimeError, 'unexpected file'):
            updater._verify(self.tmp, self.blobs)

    def test_preserved_dirs_ignored(self):
        _make(self.tmp, {'data/user.json': b'{}'})
        updater._verify(self.tmp, self.blobs)


class Apply(Tmp):
    def setUp(self):
        super().setUp()
        self.app = os.path.join(self.tmp, 'app')
        self.src = os.path.join(self.tmp, 'src')
        _make(self.app, {'main.py': b'old', 'core/a.py': b'old', 'data/user.json': b'mine'})
        _make(self.src, {'main.py': b'new', 'core/a.py': b'new', 'core/b.py': b'new'})
        patcher = patch.object(updater, 'APP_DIR', self.app)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_replaces_code_keeps_data(self):
        updater._apply(self.src)
        self.assertEqual(_read(self.app, 'main.py'), b'new')
        self.assertEqual(_read(self.app, 'core/b.py'), b'new')
        self.assertEqual(_read(self.app, 'data/user.json'), b'mine')
        self.assertFalse([n for n in os.listdir(self.tmp) if n.startswith('.holocron_bak_')])

    def test_rollback_on_failure(self):
        with patch.object(updater.shutil, 'copy2', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                updater._apply(self.src)
        self.assertEqual(_read(self.app, 'main.py'), b'old')
        self.assertEqual(_read(self.app, 'core/a.py'), b'old')
        self.assertFalse(os.path.exists(os.path.join(self.app, 'core', 'b.py')))
        self.assertEqual(_read(self.app, 'data/user.json'), b'mine')

    def test_rollback_keeps_names_never_moved(self):
        real = shutil.move

        def busy(src, dst):
            if os.path.basename(src) == 'main.py' and '.holocron_bak_' in dst:
                raise OSError('busy')
            return real(src, dst)

        with patch.object(updater.shutil, 'move', side_effect=busy):
            with self.assertRaises(OSError):
                updater._apply(self.src)
        self.assertEqual(_read(self.app, 'main.py'), b'old')
        self.assertEqual(_read(self.app, 'core/a.py'), b'old')
        self.assertFalse(os.path.exists(os.path.join(self.app, 'core', 'b.py')))
        self.assertEqual(_read(self.app, 'data/user.json'), b'mine')
        self.assertFalse([n for n in os.listdir(self.tmp) if n.startswith('.holocron_bak_')])

    def test_backup_kept_when_rollback_fails(self):
        real = shutil.move

        def stuck(src, dst):
            if '.holocron_bak_' in src:
                raise OSError('locked')
            return real(src, dst)

        with patch.object(updater.shutil, 'copy2', side_effect=OSError('disk full')), \
                patch.object(updater.shutil, 'move', side_effect=stuck):
            with self.assertRaises(updater.RollbackError):
                updater._apply(self.src)
        self.assertTrue([n for n in os.listdir(self.tmp) if n.startswith('.holocron_bak_')])

    def _blobs(self):
        return [{'path': p, 'sha': ''} for p in ('main.py', 'core/a.py', 'core/b.py')]

    def test_removes_files_deleted_upstream(self):
        _make(self.app, {'old.py': b'old', 'tools/x.py': b'old', 'core/gone.py': b'old',
                         '.manifest': b'main.py\nold.py\ntools/x.py\ncore/a.py\ncore/gone.py\n'})
        updater._apply(self.src, self._blobs())
        for path in ('old.py', 'tools', 'core/gone.py'):
            self.assertFalse(os.path.exists(os.path.join(self.app, *path.split('/'))))
        self.assertEqual(_read(self.app, '.manifest'), b'core/a.py\ncore/b.py\nmain.py\n')
        self.assertEqual(_read(self.app, 'data/user.json'), b'mine')

    def test_keeps_files_not_in_manifest(self):
        _make(self.app, {'mine.txt': b'mine'})
        updater._apply(self.src, self._blobs())
        self.assertEqual(_read(self.app, 'mine.txt'), b'mine')

    def test_rollback_restores_deleted(self):
        _make(self.app, {'old.py': b'old', '.manifest': b'main.py\nold.py\n'})
        with patch.object(updater.shutil, 'copy2', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                updater._apply(self.src, self._blobs())
        self.assertEqual(_read(self.app, 'old.py'), b'old')
        self.assertEqual(_read(self.app, '.manifest'), b'main.py\nold.py\n')


class Stale(Tmp):
    def setUp(self):
        super().setUp()
        patcher = patch.object(updater, 'APP_DIR', self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)
        _make(self.tmp, {'main.py': b'good', 'old.py': b'x',
                         '.manifest': b'main.py\nold.py\ndata/user.json\n../evil\n'})
        self.blobs = [{'path': 'main.py', 'sha': _sha(b'good')}]

    def test_installed_skips_preserved_and_unsafe(self):
        self.assertEqual(updater._installed(), {'main.py', 'old.py'})

    def test_deleted_upstream_means_update(self):
        self.assertFalse(updater._is_current(self.blobs))
        os.remove(os.path.join(self.tmp, 'old.py'))
        self.assertTrue(updater._is_current(self.blobs))

    def test_no_manifest(self):
        os.remove(os.path.join(self.tmp, '.manifest'))
        self.assertTrue(updater._is_current(self.blobs))


class Update(unittest.TestCase):
    GOOD = {'main.py': b'good'}
    BLOBS = [{'path': 'main.py', 'sha': _sha(b'good')}]

    def _update(self, tarball=None, remote=None):
        remote = remote or Mock(return_value=('a' * 40, self.BLOBS))
        with patch.object(updater, '_is_dev', return_value=False), \
             patch.object(updater, '_remote_tree', remote), \
             patch.object(updater, '_is_current', return_value=False), \
             patch.object(updater, '_download', return_value=tarball) as download, \
             patch.object(updater, '_file_changed', return_value=False), \
             patch.object(updater, '_apply') as apply, \
             patch.object(updater, '_restart') as restart, \
             patch('builtins.print'):
            result = updater.update(restart=False)
        return result, apply, download, restart

    def test_installs_verified_build(self):
        result, apply, _, restart = self._update(_tarball(self.GOOD))
        self.assertTrue(result)
        apply.assert_called_once()
        self.assertTrue(apply.call_args.args[0].endswith('holocron-abc'))
        restart.assert_not_called()

    def test_tampered_archive_not_installed(self):
        result, apply, _, _ = self._update(_tarball({'main.py': b'evil'}))
        self.assertFalse(result)
        apply.assert_not_called()

    def test_extra_file_not_installed(self):
        result, apply, _, _ = self._update(_tarball({**self.GOOD, 'core/backdoor.py': b'x'}))
        self.assertFalse(result)
        apply.assert_not_called()

    def test_path_traversal_not_installed(self):
        result, apply, _, _ = self._update(_tarball({'../evil.py': b'x'}, root=''))
        self.assertFalse(result)
        apply.assert_not_called()

    def test_offline(self):
        result, apply, download, _ = self._update(remote=Mock(side_effect=RuntimeError('offline')))
        self.assertFalse(result)
        download.assert_not_called()
        apply.assert_not_called()

    def test_offline_names_api_host(self):
        with patch.object(updater, '_is_dev', return_value=False), \
             patch.object(updater, '_remote_tree', side_effect=RuntimeError('offline')), \
             patch('builtins.print') as out:
            self.assertFalse(updater.update(restart=False))
        self.assertIn('api.github.com', out.call_args.args[0])


class Sources(unittest.TestCase):
    @staticmethod
    def _hosts(urls):
        return [urllib.parse.urlsplit(u).netloc for u in urls]

    def test_hashes_never_come_from_mirrors(self):
        with patch.dict(os.environ, {'HOLOCRON_MIRROR': 'https://m.example/'}), \
                patch.object(updater, '_get', return_value={'sha': 'a' * 40, 'tree': []}) as get:
            updater._latest_sha()
            updater._tree('a' * 40)
        self.assertEqual(get.call_count, 2)
        for call in get.call_args_list:
            self.assertEqual(self._hosts(call.args[0]), ['api.github.com'])

    def test_archive_tries_github_before_mirrors(self):
        with patch.dict(os.environ, {'HOLOCRON_MIRROR': 'https://m.example/'}), \
                patch.object(updater, '_get', return_value=b'tar') as get:
            updater._download('a' * 40)
        urls = get.call_args.args[0]
        self.assertEqual(self._hosts(urls), ['api.github.com', 'github.com', 'm.example'])
        self.assertTrue(urls[-1].startswith('https://m.example/https://github.com/'))
        self.assertTrue(get.call_args.kwargs['raw'])

    def test_mirror_override(self):
        with patch.dict(os.environ, {'HOLOCRON_MIRROR': ' https://a.example/ , https://b.example'}):
            self.assertEqual(updater._mirrored('https://github.com/x'),
                             ['https://a.example/https://github.com/x',
                              'https://b.example/https://github.com/x'])


class Get(unittest.TestCase):
    @staticmethod
    def _response(data):
        r = MagicMock()
        r.__enter__.return_value = io.BytesIO(data)
        return r

    def test_falls_back_to_next_url_with_ssl(self):
        with patch.object(updater.urllib.request, 'urlopen',
                          side_effect=[OSError('blocked'), self._response(b'tar')]) as urlopen:
            data = updater._get(['https://a.example/x', 'https://b.example/x'], raw=True)
        self.assertEqual(data, b'tar')
        for call in urlopen.call_args_list:
            self.assertIsNotNone(call.kwargs.get('context'))

    def test_all_failed_names_hosts(self):
        with patch.object(updater.urllib.request, 'urlopen', side_effect=OSError('nope')):
            with self.assertRaises(RuntimeError) as caught:
                updater._get(['https://a.example/x', 'https://b.example/x'])
        self.assertIn('a.example', str(caught.exception))
        self.assertIn('b.example', str(caught.exception))


class Context(unittest.TestCase):
    def test_default_verifies_certificates(self):
        with patch.object(updater, '_CTX', None), patch.dict(sys.modules, {'truststore': None}):
            ctx = updater._context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)

    def test_prefers_truststore(self):
        fake = SimpleNamespace(SSLContext=Mock(return_value='system'))
        with patch.object(updater, '_CTX', None), patch.dict(sys.modules, {'truststore': fake}):
            self.assertEqual(updater._context(), 'system')
            self.assertEqual(updater._context(), 'system')
        fake.SSLContext.assert_called_once_with(ssl.PROTOCOL_TLS_CLIENT)


class DevMode(unittest.TestCase):
    def test_env(self):
        missing = os.path.join(tempfile.gettempdir(), 'no-such-holocron-marker')
        with patch.object(updater, 'DEV_MARKER', missing):
            for value, expected in (('1', True), ('yes', True), ('', False), ('0', False), ('false', False)):
                with self.subTest(value=value), patch.dict(os.environ, {'HOLOCRON_DEV': value}):
                    self.assertEqual(updater._is_dev(), expected)
