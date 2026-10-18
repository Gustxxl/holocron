import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import threading
import ssl


REPO = 'Gustxxl/holocron'
BRANCH = 'main'

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV_MARKER = os.path.join(APP_DIR, '.dev')

PRESERVE = {'data', '.git', 'venv', '.venv', '__pycache__', '.dev'}

API = f'https://api.github.com/repos/{REPO}/commits/{BRANCH}'
TREE = f'https://api.github.com/repos/{REPO}/git/trees/{{sha}}?recursive=1'
API_TARBALL = f'https://api.github.com/repos/{REPO}/tarball/{{sha}}'
TARBALL = f'https://github.com/{REPO}/archive/{{sha}}.tar.gz'

MIRRORS = [
    'https://gh-proxy.com/',
    'https://ghproxy.net/',
    'https://ghfast.top/',
    'https://gh.llkk.cc/',
]


def _mirrored(url):
    override = os.environ.get('HOLOCRON_MIRROR')
    prefixes = [p.strip() for p in override.split(',') if p.strip()] if override else MIRRORS
    return [p.rstrip('/') + '/' + url for p in prefixes]


def _get(urls, raw=False):
    errors = []
    for candidate in urls:
        try:
            req = urllib.request. Request(candidate, headers={
                'Accept': '*/*' if raw else 'application/vnd.github+json',
                'User-Agent': 'holocron',
            })
            with urllib.request.urlopen(req, timeout=15, context=_context()) as r:
                return r.read() if raw else json.load(r)
        except Exception as e:
            errors.append(f'{urllib.parse.urlsplit(candidate).netloc}: {e}')
    raise RuntimeError('; '.join(errors))


_CTX = None


def _context():
    global _CTX
    if _CTX is None:
        try:
            import truststore
            _CTX = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            _CTX = ssl.create_default_context()
    return _CTX


def _api(url):
    return _get([url])


def _download(sha):
    archive = TARBALL.format(sha=sha)
    return _get([API_TARBALL.format(sha=sha), archive, *_mirrored(archive)], raw=True)


def _is_dev():
    env = os.environ.get('HOLOCRON_DEV', '').strip().lower()
    if env not in ('', '0', 'false', 'no'):
        return True
    return os.path.exists(DEV_MARKER)


def _latest_sha():
    return _api(API)['sha']


def _check_path(path):
    parts = path.split('/')
    if path.startswith('/') or '\\' in path or any(p in ('', '.', '..') for p in parts):
        raise RuntimeError(f'unsafe path in tree: {path}')
    return parts


def _extract(tar, dest):
    if hasattr(tarfile, 'data_filter'):
        tar.extractall(dest, filter='data')
        return
    for member in tar.getmembers():
        if not (member.isfile() or member.isdir()):
            raise RuntimeError(f'unsafe entry in archive: {member.name}')
        _check_path(member.name.rstrip('/'))
    tar.extractall(dest)


def _tree(sha):
    data = _api(TREE.format(sha=sha))
    if data.get('truncated'):
        raise RuntimeError('tree listing truncated; integrity cannot be verified')
    blobs = []
    for e in data['tree']:
        if e.get('type') != 'blob':
            continue
        if _check_path(e['path'])[0] in PRESERVE:
            continue
        blobs.append(e)
    return blobs


def _remote_tree():
    sha = _latest_sha()
    return sha, _tree(sha)


def _git_blob_sha(path):
    h = hashlib.sha1()
    h.update(b'blob ' + str(os.path.getsize(path)).encode() + b'\0')
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _is_current(blobs):
    for entry in blobs:
        target = os.path.join(APP_DIR, entry['path'])
        if not os.path.isfile(target) or _git_blob_sha(target) != entry['sha']:
            return False
    return True


def _verify(root, blobs):
    expected = set()
    for entry in blobs:
        expected.add(entry['path'])
        target = os.path.join(root, entry['path'])
        if not os.path.isfile(target):
            raise RuntimeError(f"missing file in payload: {entry['path']}")
        if _git_blob_sha(target) != entry['sha']:
            raise RuntimeError(f"integrity mismatch: {entry['path']}")
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, '/')
            if rel.split('/')[0] in PRESERVE:
                continue
            if rel not in expected:
                raise RuntimeError(f'unexpected file in payload: {rel}')


class RollbackError(RuntimeError):
    pass

def _rollback(names, existed, moved, backup):
    failed = []
    for name in names:
        if name in existed and name not in moved:
            continue
        dst = os.path.join(APP_DIR, name)
        try:
            if os.path.isdir(dst) and not os.path.islink(dst):
                shutil.rmtree(dst)
            elif os.path.lexists(dst):
                os.remove(dst)
            if name in moved:
                shutil.move(os.path.join(backup, name), dst)
        except OSError:
            failed.append(name)
    return failed


def _apply(src_root):
    names = [n for n in os.listdir(src_root) if n not in PRESERVE]
    existed = [n for n in names if os.path.lexists(os.path.join(APP_DIR, n))]
    backup = tempfile.mkdtemp(prefix='.holocron_bak_', dir=os.path.dirname(APP_DIR))
    moved = []
    try:
        for name in existed:
            shutil.move(os.path.join(APP_DIR, name), os.path.join(backup, name))
            moved.append(name)
        for name in names:
            src = os.path.join(src_root, name)
            dst = os.path.join(APP_DIR, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
    except Exception:
        failed = _rollback(names, existed, moved, backup)
        if failed:
            raise RollbackError(f"{', '.join(failed)} not restored, previous build kept in {backup}")
        shutil.rmtree(backup, ignore_errors=True)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def _restart():
    if os.name == 'nt':
        completed = subprocess.run([sys.executable, *sys.argv])
        sys.exit(completed.returncode)
    os.execv(sys.executable, [sys.executable] + sys.argv)


def _file_changed(a, b):
    def read(p):
        try:
            with open(p, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return None
    return read(a) != read(b)


def update(restart=True):
    if _is_dev():
        print('Dev mode: auto-update disabled.')
        return False
    print('Checking the system...')
    try:
        sha, blobs = _remote_tree()
    except Exception as e:
        print(f'System unreachable: {e}')
        return False

    if _is_current(blobs):
        print(f'System is up to date — build {sha[:7]}.')
        return False

    print('Update found. Retrieving...')
    try:
        blob = _download(sha)
    except Exception as e:
        print(f'Retrieval failed: {e}')
        return False

    tmp = tempfile.mkdtemp(prefix='holocron_')
    try:
        try:
            with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
                _extract(tar, tmp)
            entries = os.listdir(tmp)
            if len(entries) != 1 or not os.path.isdir(os.path.join(tmp, entries[0])):
                raise RuntimeError('unexpected archive layout')
            root = os.path.join(tmp, entries[0])
            _verify(root, blobs)
        except Exception as e:
            print(f'Integrity check failed, update aborted: {e}')
            return False

        new_reqs = os.path.join(root, 'requirements.txt')
        old_reqs = os.path.join(APP_DIR, 'requirements.txt')
        reqs_changed = _file_changed(old_reqs, new_reqs)

        try:
            _apply(root)
        except RollbackError as e:
            print(f'Apply failed and the previous build could not be restored: {e}')
            return False
        except Exception as e:
            print(f'Apply failed, rolled back to previous build: {e}')
            return False

        if reqs_changed:
            print('Realigning dependencies...')
            subprocess.run([sys.executable, '-m', 'pip', 'install',
                            '-r', old_reqs], check=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print('System updated.')
    if restart:
        print('Restarting...')
        _restart()
    return True


def update_available():
    if _is_dev():
        return None
    try:
        sha, blobs = _remote_tree()
    except Exception:
        return None
    return None if _is_current(blobs) else sha


_update_sha = None
_update_thread = None


def check_update_async():
    global _update_thread

    def _run():
        global _update_sha
        _update_sha = update_available()

    _update_thread = threading.Thread(target=_run, daemon=True)
    _update_thread.start()


def pending_update(wait=0.0):
    if wait and _update_thread is not None:
        _update_thread.join(wait)
    return _update_sha


if __name__ == '__main__':
    update(restart=False)
