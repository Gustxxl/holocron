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

# project root (folder containing main.py); core/ is one level down
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(APP_DIR, '.version')

# never overwritten on update: user data and local files
PRESERVE = {'.version', 'data', '.git', 'venv', '.venv', '__pycache__', }

API = f'https://api.github.com/repos/{REPO}/commits/{BRANCH}'
TARBALL = f'https://codeload.github.com/{REPO}/tar.gz/refs/heads/{BRANCH}'


def _get(url, raw=False):
    req = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'holocron',
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read() if raw else json.load(r)


def current_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE) as f:
            return f.read().strip()
    return None  # first run — no version recorded yet


def remote_version():
    return _get(API)['sha']


def _apply(src_root):
    '''Copy new code over the old, leaving PRESERVE entries untouched.'''
    for name in os.listdir(src_root):
        if name in PRESERVE:
            continue
        src = os.path.join(src_root, name)
        dst = os.path.join(APP_DIR, name)
        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def _restart():
    '''Relaunch with the same interpreter and arguments.'''
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
    except Exception as e:
        print(f'System unreachable: {e}')
        return False

    if current_version() == remote:
        print(f'System is up to date — build {remote[:7]}.')
        return False

    print('Update found. Retrieving...')
    try:
        blob = _get(TARBALL, raw=True)
    except Exception as e:
        print(f'Retrieval failed: {e}')
        return False

    tmp = tempfile.mkdtemp(prefix='holocron_')
    try:
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            tar.extractall(tmp, filter='data')
        # tarball unpacks into a single subfolder like holocron-<sha>/
        root = os.path.join(tmp, os.listdir(tmp)[0])

        new_reqs = os.path.join(root, 'requirements.txt')
        old_reqs = os.path.join(APP_DIR, 'requirements.txt')
        reqs_changed = _file_changed(old_reqs, new_reqs)

        _apply(root)

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
