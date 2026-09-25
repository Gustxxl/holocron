import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import threading


REPO = 'Gustxxl/holocron'
BRANCH = 'main'

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV_MARKER = os.path.join(APP_DIR, '.dev')

PRESERVE = {'data', '.git', 'venv', '.venv', '__pycache__', '.dev'}

API = f'https://api.github.com/repos/{REPO}/commits/{BRANCH}'
TREE = f'https://api.github.com/repos/{REPO}/git/trees/{{sha}}?recursive=1'
TARBALL = f'https://github.com/{REPO}/archive/{{sha}}.tar.gz'

MIRRORS = [
    'https://gh-proxy.com/',
    'https://ghproxy.net/',
    'https://ghfast.top/',
    'https://gh.llkk.cc/',
]


def _candidates(url):
    yield url
    override = os.environ.get('HOLOCRON_MIRROR')
    prefixes = [p.strip() for p in override.split(',') if p.strip()] if override else MIRRORS
    for p in prefixes:
        yield p.rstrip('/') + '/' + url


def _get(url, raw=False):
    last = None
    for candidate in _candidates(url):
        try:
            req = urllib.request.Request(candidate, headers={
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'holocron',
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read() if raw else json.load(r)
        except Exception as e:
            last = e
            continue
    raise last


def _is_dev():
    env = os.environ.get('HOLOCRON_DEV', '').strip().lower()
    if env not in ('', '0', 'false', 'no'):
        return True
    return os.path.exists(DEV_MARKER)


def _latest_sha():
    return _get(API)['sha']


def _tree(sha):
    data = _get(TREE.format(sha=sha))
    if data.get('truncated'):
        raise RuntimeError('tree listing truncated; integrity cannot be verified')
    return [e for e in data['tree'] if e.get('type') == 'blob']


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
    for entry in blobs:
        target = os.path.join(root, entry['path'])
        if not os.path.isfile(target):
            raise RuntimeError(f"missing file in payload: {entry['path']}")
        if _git_blob_sha(target) != entry['sha']:
            raise RuntimeError(f"integrity mismatch: {entry['path']}")


def _apply(src_root):
    names = [n for n in os.listdir(src_root) if n not in PRESERVE]
    backup = tempfile.mkdtemp(prefix='.holocron_bak_', dir=os.path.dirname(APP_DIR))
    try:
        for name in names:
            dst = os.path.join(APP_DIR, name)
            if os.path.lexists(dst):
                shutil.move(dst, os.path.join(backup, name))
        for name in names:
            src = os.path.join(src_root, name)
            dst = os.path.join(APP_DIR, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
    except Exception:
        for name in names:
            dst = os.path.join(APP_DIR, name)
            if os.path.isdir(dst) and not os.path.islink(dst):
                shutil.rmtree(dst, ignore_errors=True)
            elif os.path.lexists(dst):
                os.remove(dst)
            saved = os.path.join(backup, name)
            if os.path.lexists(saved):
                shutil.move(saved, os.path.join(APP_DIR, name))
        raise
    finally:
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
        blob = _get(TARBALL.format(sha=sha), raw=True)
    except Exception as e:
        print(f'Retrieval failed: {e}')
        return False

    tmp = tempfile.mkdtemp(prefix='holocron_')
    try:
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            tar.extractall(tmp, filter='data')
        root = os.path.join(tmp, os.listdir(tmp)[0])

        try:
            _verify(root, blobs)
        except Exception as e:
            print(f'Integrity check failed, update aborted: {e}')
            return False

        new_reqs = os.path.join(root, 'requirements.txt')
        old_reqs = os.path.join(APP_DIR, 'requirements.txt')
        reqs_changed = _file_changed(old_reqs, new_reqs)

        try:
            _apply(root)
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
