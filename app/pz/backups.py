from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


def backup_files(backup_dir: Path, files: list[Path]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for path in files:
        if path.exists() and path.is_file():
            shutil.copy2(path, dest / path.name)
    return dest
