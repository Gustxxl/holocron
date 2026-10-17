import json
import os
from pathlib import Path
from core import backups

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
CONFIG = Path(DATA_DIR) / "config.json"

DEFAULTS = {
    "operator_name": "",
    "excalidraw_obsidian_path": "",
}

broken = None
last = None


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load():
    global broken, last
    ensure_data_dir()
    cfg = dict(DEFAULTS)
    if CONFIG.exists():
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not an object")
            cfg.update(data)
            last = dict(cfg)
        except Exception:
            if broken is None:
                broken = str(backups.save(CONFIG))
            if last is not None:
                save(last)
                broken = None
                return dict(last)
    return cfg


def save(cfg):
    ensure_data_dir()
    tmp = CONFIG.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, CONFIG)
    except Exception as e:
        tmp.unlink(missing_ok=True)
        print(f"\033[31mFailed to save config: {e}\033[0m")
