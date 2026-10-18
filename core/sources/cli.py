import json
import os
import shutil
from datetime import date, datetime
from pathlib import Path
from core import config, system

TIMEOUT = 10
BIN = Path(config.DATA_DIR) / 'bin'
_PATHS = ('/opt/homebrew/bin', '/usr/local/bin')


def which(program):
    local = BIN / program
    if local.is_file():
        return str(local)
    return _system(program)


def _system(program):
    return shutil.which(program) or shutil.which(program, path=os.pathsep.join(_PATHS))


def origin(program):
    path = which(program)
    if path is None:
        return None
    if path == str(BIN / program):
        return 'holocron'
    return 'homebrew' if '/Cellar/' in os.path.realpath(path) else 'system'


def shadowed(program):
    return _system(program) if (BIN / program).is_file() else None


def available(program):
    return which(program) is not None


def _run(program, args, timeout):
    path = which(program)
    return system.run([path, *args], timeout=timeout) if path else None


def run_json(program, *args, timeout=TIMEOUT):
    out = _run(program, args, timeout)
    if out is None or out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except (TypeError, ValueError):
        return None


def run_ok(program, *args, timeout=TIMEOUT):
    out = _run(program, args, timeout)
    return out is not None and out.returncode == 0


def run_code(program, *args, timeout=TIMEOUT):
    out = _run(program, args, timeout)
    return out.returncode if out else None


def parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        if len(value) == 10:
            return datetime.combine(date.fromisoformat(value), datetime.min.time())
        moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return moment.astimezone().replace(tzinfo=None) if moment.tzinfo else moment
