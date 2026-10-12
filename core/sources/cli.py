import json
import shutil
from datetime import date, datetime
from core import system

TIMEOUT = 10


def available(program):
    return shutil.which(program) is not None


def _run(program, args, timeout):
    path = shutil.which(program)
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
