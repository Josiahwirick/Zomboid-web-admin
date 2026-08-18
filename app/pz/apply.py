from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.pz import backups, process


class UnsafeEditError(RuntimeError):
    pass


@dataclass
class ApplyResult:
    ok: bool
    message: str
    backup_dir: Path | None = None
    restarted: bool = False


def apply_writes(
    settings: Settings,
    write_fns: list[Callable[[], None]],
    restart: bool,
    files: list[Path],
) -> ApplyResult:
    """Stop (if restarting), backup, write, then start.

    PZ overwrites configs on shutdown if they were edited while running, so
    writes while the server is online require restart=True.
    """
    stats = process.get_stats(settings.pz_status_cmd)
    running = stats.running

    if running and not restart:
        raise UnsafeEditError(
            "The server is running. Saving now would be overwritten on shutdown. Use Save and restart."
        )

    if restart and running:
        stopped = process.stop(settings.pz_stop_cmd)
        if not stopped.ok:
            return ApplyResult(False, stopped.message)

    backup_dir = backups.backup_files(settings.backup_dir, files)
    try:
        for fn in write_fns:
            fn()
    except Exception as exc:  # noqa: BLE001
        return ApplyResult(False, f"Failed to write config: {exc}", backup_dir=backup_dir)

    if restart:
        started = process.start(settings.pz_start_cmd)
        if not started.ok:
            return ApplyResult(
                False,
                f"Config saved, but start failed: {started.message}",
                backup_dir=backup_dir,
                restarted=False,
            )
        return ApplyResult(True, "Saved and restarted.", backup_dir=backup_dir, restarted=True)

    return ApplyResult(True, "Saved. Restart the server when you want the changes to apply.", backup_dir=backup_dir)
