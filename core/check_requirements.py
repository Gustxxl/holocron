import os
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

def _install_missing(root):
    try:
        from importlib.metadata import distributions
    except ImportError:
        from importlib_metadata import distributions

    req = root / "requirements.txt"
    if not req.exists():
        return

    installed = {d.metadata["Name"].lower() for d in distributions()}
    missing = []
    for line in req.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = line.split("==")[0].split(">=")[0].split("<=")[0]
        pkg = pkg.split(">")[0].split("<")[0].split("[")[0].split(";")[0].strip()
        if pkg and pkg.lower() not in installed:
            missing.append(line)

    if missing:
        print(f"Installing missing dependencies: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])

def ensure_environment():
    root = _project_root()
    venv_dir = root / ".venv"

    # Already running inside the project's venv: just top up missing packages.
    if Path(sys.prefix).resolve() == venv_dir.resolve():
        _install_missing(root)
        return

    # Not in the venv yet: create it if needed, then re-exec inside it.
    venv_python = _venv_python(venv_dir)
    if not venv_python.exists():
        print("Creating virtual environment (.venv)...")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

    os.execv(str(venv_python), [str(venv_python), *sys.argv])

ensure_environment()
