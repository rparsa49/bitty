"""Sprite sheet + JSON manifest loader. Swap art by editing data, not code.

Manifest:
  {"image": "blob.png", "frame_size": [32, 32],
   "states": {"idle": {"row": 0, "frames": 4, "fps": 4, "loop": true},
              "happy": {"row": 5, "frames": 4, "fps": 6, "loop": false, "next": "idle"}}}
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QPixmap


class SpriteSheet:
    def __init__(self, manifest_path: str | Path) -> None:
        p = Path(manifest_path)
        m = json.loads(p.read_text())
        self.fw, self.fh = m["frame_size"]
        self.states: dict[str, dict] = m["states"]
        self.sheet = QPixmap(str(p.parent / m["image"]))
        if self.sheet.isNull():
            raise FileNotFoundError(f"Could not load sprite image next to {p}")
        self._cache: dict[tuple[str, int], QPixmap] = {}

    def resolve(self, state: str) -> str:
        """'working:search' -> 'working' if there is no dedicated animation; unknown -> 'idle'."""
        if state in self.states:
            return state
        base = state.split(":")[0]
        return base if base in self.states else "idle"

    def spec(self, state: str) -> dict:
        return self.states[self.resolve(state)]

    def frame(self, state: str, i: int) -> QPixmap:
        name = self.resolve(state)
        key = (name, i)
        if key not in self._cache:
            row = self.states[name]["row"]
            self._cache[key] = self.sheet.copy(i * self.fw, row * self.fh, self.fw, self.fh)
        return self._cache[key]
