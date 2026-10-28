from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from .tools import tool

NOTES_FILE = Path(os.getenv("CRITTER_NOTES", "~/.critter/notes.txt")).expanduser()


@tool
def current_time() -> str:
    """Get the current local date and time."""
    return datetime.now().strftime("%A %Y-%m-%d %H:%M")


@tool(state="working:search")
def search_files(pattern: str, folder: str = "~") -> str:
    """Find files whose name contains the pattern, searching a folder up to 3 levels deep."""
    root = Path(folder).expanduser()
    base_depth = len(root.parts)
    hits: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if len(Path(dirpath).parts) - base_depth >= 3:
            dirnames[:] = []
        hits += [str(Path(dirpath) / f) for f in filenames if pattern.lower() in f.lower()]
        if len(hits) >= 20:
            break
    return "\n".join(hits[:20]) or "No matches."


@tool(tier="ask", state="working:write")
def add_note(text: str) -> str:
    """Append a note to the user's notes file."""
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NOTES_FILE.open("a") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M}  {text}\n")
    return f"Saved note to {NOTES_FILE}"
