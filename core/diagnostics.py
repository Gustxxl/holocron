import io
import platform
import shutil
import sys
import time
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent / 'tests'


def available():
    return TESTS.is_dir()


def _module(test):
    return test.id().split('.')[0].removeprefix('test_')


def _label(test):
    parts = test.id().split('.')
    if '_FailedTest' in parts:
        return f'{parts[-1].removeprefix("test_")} · import'
    return f'{_module(test)} · {".".join(parts[1:])}'


class _Result(unittest.TestResult):
    def __init__(self, progress):
        super().__init__()
        self.buffer = True
        self._progress = progress

    def stopTest(self, test):
        super().stopTest(test)
        self._progress(self.testsRun, _module(test))


def run(progress=lambda done, total, name: None):
    path, stdin = list(sys.path), sys.stdin
    sys.stdin = io.StringIO('')
    try:
        suite = unittest.TestLoader().discover(str(TESTS), top_level_dir=str(TESTS))
        total = suite.countTestCases()
        result = _Result(lambda done, name: progress(done, total, name))
        start = time.monotonic()
        suite.run(result)
        seconds = time.monotonic() - start
    finally:
        sys.path[:] = path
        sys.stdin = stdin
    failed = [(_label(t), tb) for t, tb in result.failures + result.errors]
    return {
        'total': total,
        'passed': result.testsRun - len(failed) - len(result.skipped),
        'skipped': len(result.skipped),
        'failed': failed,
        'seconds': seconds,
    }


def system_info():
    from core import archives, keeper, system
    from core.sources import remindctl
    editor = system.editor()
    clipboard = next((name for name, *_ in system.CLIPBOARDS if shutil.which(name)), None)
    conn = keeper.active(refresh=True)
    rows = [
        ('Editor', Path(editor[0]).stem if editor else None),
        ('Clipboard', clipboard),
        ('Reminders', remindctl.PROGRAM if remindctl.available() else None),
        ('Keeper', {'server': 'server', 'local': 'this computer'}.get(conn['slot']) if conn else None),
        ('Archive', f'{archives.count()} cases' if archives.is_loaded() else None),
    ]
    head = f'{system.OS} {system.version()} ({platform.machine()})   Python {platform.python_version()}'
    return head, rows


def reason(tb):
    lines = tb.rstrip().splitlines()
    start = max((i for i, ln in enumerate(lines) if ln.startswith('  File ')), default=-1)
    return next((ln for ln in lines[start + 1:] if ln.strip() and not ln.startswith(' ')),
                lines[-1] if lines else '')
