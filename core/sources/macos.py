import hashlib
import io
import json
import os
import platform
import ssl
import subprocess
import tarfile
import urllib.error
import urllib.request
import zipfile
from collections import deque
from core import system
from . import cli

UPDATE_URL = 'x-apple.systempreferences:com.apple.Software-Update-Settings.extension'
_CLT = 'Command Line Tools'
_API = 'https://api.github.com/repos/{}/releases/latest'
_ARCHIVES = ('.tar.gz', '.zip')
_ARCH_NAMES = {'arm64': ('arm64', 'aarch64'), 'x86_64': ('x86_64', 'amd64')}
_OTHER_OS = ('linux', 'windows', 'freebsd')
_CPU = {'arm64': 0x0100000c, 'x86_64': 0x01000007}

_TERMINALS = {'Apple_Terminal': 'Terminal', 'iTerm.app': 'iTerm', 'ghostty': 'Ghostty',
              'WezTerm': 'WezTerm', 'vscode': 'VS Code', 'WarpTerminal': 'Warp'}


def supported():
    return system.IS_MACOS


def status(program, version, authorized):
    major = platform.mac_ver()[0].split('.')[0]
    if not (major.isdigit() and int(major) >= version):
        return 'old_macos'
    if not cli.available(program):
        return 'missing'
    return 'ready' if authorized() else 'denied'


def terminal():
    return _TERMINALS.get(os.environ.get('TERM_PROGRAM', ''), 'your terminal app')


def install(formula):
    return _brew('install', formula)


def remove(program, formula):
    if cli.origin(program) == 'holocron':
        try:
            (cli.BIN / program).unlink(missing_ok=True)
        except OSError:
            return False
        return True
    return cli.available('brew') and _brew('uninstall', formula) == 'ok'


def _brew(action, formula):
    try:
        proc = subprocess.Popen([cli.which('brew'), action, formula], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, errors='replace')
        tail = deque(maxlen=50)
        for line in proc.stdout:
            print(line, end='', flush=True)
            tail.append(line)
        code = proc.wait()
    except KeyboardInterrupt:
        return 'failed'
    if code == 0:
        return 'ok'
    return 'clt' if _CLT in ''.join(tail) else 'failed'


def download(repo, program):
    try:
        release = json.loads(_fetch(_API.format(repo)))
        assets = {a['name']: a for a in release['assets']}
        name = _pick(assets, platform.machine())
        if name is None:
            return False
        want = _expected(assets, name)
        if want is None:
            return False
        data = _fetch(assets[name]['browser_download_url'])
        if hashlib.sha256(data).hexdigest() != want:
            return False
        blob = _extract(name, data, program)
    except (KeyboardInterrupt, Exception):
        return False
    if blob is None or _CPU.get(platform.machine()) not in _arches(blob):
        return False
    cli.BIN.mkdir(parents=True, exist_ok=True)
    target = cli.BIN / program
    tmp = target.with_suffix('.tmp')
    tmp.write_bytes(blob)
    tmp.chmod(0o755)
    os.replace(tmp, target)
    return True


def _pick(names, arch):
    other = _ARCH_NAMES['x86_64' if arch == 'arm64' else 'arm64']
    builds = [n for n in names if n.endswith(_ARCHIVES) and not any(w in n.lower() for w in _OTHER_OS + other)]
    return min(builds, key=lambda n: ('universal' not in n.lower(), n), default=None)


def _expected(assets, name):
    digest = assets[name].get('digest') or ''
    if digest.startswith('sha256:'):
        return digest.removeprefix('sha256:')
    sums = assets.get(name + '.sha256') or assets.get('checksums.txt')
    return _digest(_fetch(sums['browser_download_url']).decode(), name) if sums else None


def _arches(blob):
    if blob[:4] == b'\xca\xfe\xba\xbe':
        count = int.from_bytes(blob[4:8], 'big')
        return {int.from_bytes(blob[8 + i * 20:12 + i * 20], 'big') for i in range(count)}
    if blob[:4] == b'\xcf\xfa\xed\xfe':
        return {int.from_bytes(blob[4:8], 'little')}
    return set()


def _fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLError):
            raise
    out = subprocess.run(['curl', '-fsSL', url], capture_output=True, timeout=120)
    if out.returncode != 0:
        raise OSError(out.stderr.decode(errors='replace'))
    return out.stdout


def _digest(text, name):
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 1 or (len(parts) > 1 and parts[-1].lstrip('*') == name):
            return parts[0].lower()
    return None


def _extract(name, data, program):
    if name.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            found = [n for n in z.namelist() if n.rsplit('/', 1)[-1] == program]
            return z.read(found[0]) if found else None
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        for m in t.getmembers():
            if m.isfile() and m.name.rsplit('/', 1)[-1] == program:
                return t.extractfile(m).read()
    return None


def open_url(url):
    subprocess.call(['open', url])
