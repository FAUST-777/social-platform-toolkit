from __future__ import annotations

import json
from pathlib import Path

_DIR = Path(__file__).parent / ".tokens"


def save(name: str, data: dict) -> None:
    _DIR.mkdir(exist_ok=True)
    (_DIR / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  Token saved → .tokens/{name}.json")


def load(name: str) -> dict:
    path = _DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Token '{name}' not found. Run auth_{name}.py first."
        )
    return json.loads(path.read_text())
