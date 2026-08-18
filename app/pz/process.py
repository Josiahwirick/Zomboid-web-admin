from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

PZ_PROCESS_NAMES = {
    "ProjectZomboid64",
    "ProjectZomboid32",
    "ProjectZomboid64.exe",
    "ProjectZomboid32.exe",
    "start-server.sh",
}


@dataclass
class ProcessStats:
    running: bool
    pid: int | None = None
    name: str = ""
    cpu_percent: float | None = None
    memory_rss_mb: float | None = None
    memory_percent: float | None = None
    uptime_seconds: float | None = None
    status_cmd_ok: bool | None = None
    error: str = ""


@dataclass
class ControlResult:
    ok: bool
    action: str
    message: str
    stats: ProcessStats | None = None


def _run_cmd(command: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    if not command.strip():
        raise ValueError("Command is empty")
    return subprocess.run(
        command,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def find_pz_process() -> psutil.Process | None:
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = proc.info.get("name") or ""
            if name in PZ_PROCESS_NAMES:
                return proc
            cmdline = proc.info.get("cmdline") or []
            joined = " ".join(cmdline)
            if "ProjectZomboid" in joined or "start-server.sh" in joined:
                if "java" in name.lower() or "ProjectZomboid" in joined:
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def get_stats(status_cmd: str = "") -> ProcessStats:
    status_ok: bool | None = None
    if status_cmd:
        try:
            completed = _run_cmd(status_cmd, timeout=10)
            status_ok = completed.returncode == 0
        except Exception as exc:  # noqa: BLE001
            return ProcessStats(running=False, status_cmd_ok=False, error=str(exc))

    proc = find_pz_process()
    if proc is None:
        running = bool(status_ok) if status_ok is not None else False
        return ProcessStats(running=running, status_cmd_ok=status_ok)

    try:
        with proc.oneshot():
            cpu = proc.cpu_percent(interval=0.05)
            mem = proc.memory_info()
            mem_pct = proc.memory_percent()
            create = proc.create_time()
            uptime = time.time() - create
            return ProcessStats(
                running=True,
                pid=proc.pid,
                name=proc.name(),
                cpu_percent=round(cpu, 1),
                memory_rss_mb=round(mem.rss / (1024 * 1024), 1),
                memory_percent=round(mem_pct, 1),
                uptime_seconds=uptime,
                status_cmd_ok=status_ok,
            )
    except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
        return ProcessStats(running=False, status_cmd_ok=status_ok, error=str(exc))


def start(start_cmd: str) -> ControlResult:
    if not start_cmd:
        return ControlResult(False, "start", "PZ_START_CMD is not configured.")
    if get_stats().running:
        return ControlResult(True, "start", "Server is already running.", get_stats())
    try:
        completed = _run_cmd(start_cmd)
    except Exception as exc:  # noqa: BLE001
        return ControlResult(False, "start", f"Failed to start: {exc}")
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        return ControlResult(False, "start", err or f"Start command exited {completed.returncode}")
    stats = wait_for(running=True, timeout=20)
    return ControlResult(True, "start", "Start command issued.", stats)


def stop(stop_cmd: str, wait_timeout: int = 90) -> ControlResult:
    if not stop_cmd:
        return ControlResult(False, "stop", "PZ_STOP_CMD is not configured.")
    if not get_stats().running:
        return ControlResult(True, "stop", "Server is already stopped.", get_stats())
    try:
        completed = _run_cmd(stop_cmd)
    except Exception as exc:  # noqa: BLE001
        return ControlResult(False, "stop", f"Failed to stop: {exc}")
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        return ControlResult(False, "stop", err or f"Stop command exited {completed.returncode}")
    stats = wait_for(running=False, timeout=wait_timeout)
    if stats.running:
        return ControlResult(False, "stop", "Stop command issued but the process is still running.", stats)
    return ControlResult(True, "stop", "Server stopped.", stats)


def restart(start_cmd: str, stop_cmd: str) -> ControlResult:
    stopped = stop(stop_cmd)
    if not stopped.ok:
        return ControlResult(False, "restart", stopped.message, stopped.stats)
    started = start(start_cmd)
    if not started.ok:
        return ControlResult(False, "restart", started.message, started.stats)
    return ControlResult(True, "restart", "Server restarted.", started.stats)


def wait_for(running: bool, timeout: int = 60) -> ProcessStats:
    deadline = time.time() + timeout
    stats = get_stats()
    while time.time() < deadline:
        stats = get_stats()
        if stats.running == running:
            return stats
        time.sleep(0.5)
    return stats


def format_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    secs = int(seconds)
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, rem = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def tail_logs(logs_dir: Path, console_path: Path | None = None, lines: int = 12) -> str:
    candidates: list[Path] = []
    if console_path and console_path.exists():
        candidates.append(console_path)
    home_console = logs_dir.parent / "server-console.txt"
    if home_console.exists():
        candidates.append(home_console)
    if logs_dir.exists():
        log_files = sorted(logs_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        candidates.extend(log_files[:5])
    for path in candidates:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            tail = "\n".join(content.splitlines()[-lines:])
            if tail.strip():
                return tail
        except OSError:
            continue
    return ""
