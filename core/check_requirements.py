import os
import re
import sys
import subprocess
from pathlib import Path

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

    if missing:
        print(f"Installing missing dependencies: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])

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
