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


REPO = 'Gustxxl/holocron'
BRANCH = 'main'

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(APP_DIR, '.version')

PRESERVE = {'.version', 'data', '.git', 'venv', '.venv', '__pycache__'}

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


def current_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE) as f:
            return f.read().strip()
    return None


def remote_version():
    return _get(API)['sha']


def _tree(sha):
    data = _get(TREE.format(sha=sha))
    if data.get('truncated'):
        raise RuntimeError('tree listing truncated; integrity cannot be verified')
    return [e for e in data['tree'] if e.get('type') == 'blob']


def _git_blob_sha(path):
    h = hashlib.sha1()
    h.update(b'blob ' + str(os.path.getsize(path)).encode() + b'\0')
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


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
    os.execv(sys.executable, [sys.executable] + sys.argv)


def _file_changed(a, b):
    def read(p):
        try:
            with open(p, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return None
    return read(a) != read(b)


def update():
    print('Checking the system...')
    try:
        remote = remote_version()
        blobs = _tree(remote)
    except Exception as e:
        print(f'System unreachable: {e}')
        return False

    if current_version() == remote:
        print(f'System is up to date — build {remote[:7]}.')
        return False

    print('Update found. Retrieving...')
    try:
        blob = _get(TARBALL.format(sha=remote), raw=True)
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

    with open(VERSION_FILE, 'w') as f:
        f.write(remote)

    print('System updated. Restarting...')
    _restart()
