from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    admin_user: str
    admin_password: str
    session_secret: str
    bind_host: str
    bind_port: int
    zomboid_home: Path
    pz_server_name: str
    pz_install_dir: Path | None
    steam_workshop_dir: Path | None
    pz_start_cmd: str
    pz_stop_cmd: str
    pz_status_cmd: str
    rcon_host: str
    rcon_port: int | None
    backup_dir: Path

    @property
    def server_dir(self) -> Path:
        return self.zomboid_home / "Server"

    @property
    def ini_path(self) -> Path:
        return self.server_dir / f"{self.pz_server_name}.ini"

    @property
    def sandbox_path(self) -> Path:
        return self.server_dir / f"{self.pz_server_name}_SandboxVars.lua"

    @property
    def logs_dir(self) -> Path:
        return self.zomboid_home / "Logs"

    @property
    def local_mods_dir(self) -> Path:
        return self.zomboid_home / "mods"

    @property
    def zomboid_workshop_dir(self) -> Path:
        return self.zomboid_home / "Workshop"

    @property
    def workshop_search_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        if self.steam_workshop_dir:
            dirs.append(self.steam_workshop_dir)
        dirs.append(self.zomboid_workshop_dir)
        dirs.append(self.zomboid_home / "workshop")
        dirs.append(self.local_mods_dir)
        return dirs


def load_settings() -> Settings:
    workshop = _env("STEAM_WORKSHOP_DIR")
    install = _env("PZ_INSTALL_DIR")
    rcon_port_raw = _env("RCON_PORT")
    backup = _env("BACKUP_DIR", "./backups")
    secret = _env("SESSION_SECRET")
    if not secret:
        secret = "dev-only-change-me"

    return Settings(
        admin_user=_env("ADMIN_USER", "admin"),
        admin_password=_env("ADMIN_PASSWORD", "change-me"),
        session_secret=secret,
        bind_host=_env("BIND_HOST", "127.0.0.1"),
        bind_port=_env_int("BIND_PORT", 8080),
        zomboid_home=Path(_env("ZOMBOID_HOME", "/home/steam/Zomboid")).expanduser(),
        pz_server_name=_env("PZ_SERVER_NAME", "servertest") or "servertest",
        pz_install_dir=Path(install).expanduser() if install else None,
        steam_workshop_dir=Path(workshop).expanduser() if workshop else None,
        pz_start_cmd=_env("PZ_START_CMD"),
        pz_stop_cmd=_env("PZ_STOP_CMD"),
        pz_status_cmd=_env("PZ_STATUS_CMD"),
        rcon_host=_env("RCON_HOST", "127.0.0.1") or "127.0.0.1",
        rcon_port=int(rcon_port_raw) if rcon_port_raw else None,
        backup_dir=Path(backup).expanduser(),
    )
