import json
import os
from pathlib import Path


CONFIG_PATH = Path("data/config.json")

DEFAULTS = {
    "operator_name": ""
}


def load():
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg.update(saved)
        except Exception:
            print("error")
    return cfg

def save(cfg):
    try:
        CONFIG_PATH.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        print(f"\033[31mFailed to save config: {e}\033[0m")
