import json
import shutil
from datetime import date, datetime
from core import system

TIMEOUT = 10


def available(program):
    return shutil.which(program) is not None


def run_json(program, *args, timeout=TIMEOUT):
    path = shutil.which(program)
    if not path:
        return None
    out = system.run([path, *args], timeout=timeout)
    if out is None or out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except (TypeError, ValueError):
        return None


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
