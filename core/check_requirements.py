import os
import re
import sys
import time
import subprocess
from pathlib import Path

OPTIONAL = {"windows-curses"}
SKIPPED = "holocron-skipped.txt"
RETRY_DAYS = 7


def _project_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / "requirements.txt").exists():
            return parent
    return Path(__file__).resolve().parent


def _venv_python(venv_dir):
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _name(line):
    spec = line.partition(";")[0].strip()
    return _normalize(re.split(r"[<>=!~\[\s]", spec, maxsplit=1)[0])


def _marker_ok(marker):
    if not marker:
        return True
    try:
        from packaging.markers import Marker
    except ImportError:
        try:
            from pip._vendor.packaging.markers import Marker
        except ImportError:
            return True
    try:
        return Marker(marker).evaluate()
    except Exception:
        return True


def _key(line):
    return f"{_name(line)} {sys.version_info[0]}.{sys.version_info[1]}"


def _skipped():
    path = Path(sys.prefix) / SKIPPED
    try:
        if time.time() - path.stat().st_mtime > RETRY_DAYS * 86400:
            return set()
        return set(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return set()


def _remember(keys):
    try:
        (Path(sys.prefix) / SKIPPED).write_text("\n".join(sorted(keys)) + "\n", encoding="utf-8")
    except OSError:
        pass


def plan(missing, skipped=frozenset()):
    required = [m for m in missing if _name(m) not in OPTIONAL]
    optional = [m for m in missing if _name(m) in OPTIONAL and _key(m) not in skipped]
    return required, optional


def _install_missing(root):
    try:
        from importlib.metadata import distributions
    except ImportError:
        from importlib_metadata import distributions

    req = root / "requirements.txt"
    if not req.exists():
        return

    installed = {_normalize(d.metadata["Name"]) for d in distributions() if d.metadata["Name"]}
    missing = []
    for line in req.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        spec, _, marker = line.partition(";")
        if not _marker_ok(marker.strip()):
            continue
        pkg = re.split(r"[<>=!~\[\s]", spec.strip(), maxsplit=1)[0]
        if pkg and _normalize(pkg) not in installed:
            missing.append(line)

    skipped = _skipped()
    required, optional = plan(missing, skipped)
    if not required and not optional:
        return
    print(f"Installing missing dependencies: {', '.join(required + optional)}")
    if required:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *required])
    failed = [m for m in optional
              if subprocess.call([sys.executable, "-m", "pip", "install", m],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0]
    if failed:
        names = ", ".join(_name(m) for m in failed)
        print(f"Skipped {names}: not available for Python {sys.version_info[0]}.{sys.version_info[1]} yet.")
        _remember(skipped | {_key(m) for m in failed})


def ensure_environment():
    root = _project_root()
    venv_dir = root / ".venv"

    if Path(sys.prefix).resolve() == venv_dir.resolve():
        _install_missing(root)
        return

    venv_python = _venv_python(venv_dir)
    if not venv_python.exists():
        print("Creating virtual environment (.venv)...")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

    if os.name == "nt":
        completed = subprocess.run([str(venv_python), *sys.argv])
        sys.exit(completed.returncode)

    os.execv(str(venv_python), [str(venv_python), *sys.argv])


if __name__ == "__main__":
    _install_missing(_project_root())
