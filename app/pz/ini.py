from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IniLine:
    kind: str  # "pair" | "comment" | "blank" | "other"
    raw: str
    key: str = ""
    value: str = ""


@dataclass
class IniFile:
    lines: list[IniLine] = field(default_factory=list)

    def get(self, key: str, default: str = "") -> str:
        for line in self.lines:
            if line.kind == "pair" and line.key == key:
                return line.value
        return default

    def keys(self) -> list[str]:
        return [line.key for line in self.lines if line.kind == "pair"]

    def items(self) -> list[tuple[str, str]]:
        return [(line.key, line.value) for line in self.lines if line.kind == "pair"]

    def set(self, key: str, value: str) -> None:
        for line in self.lines:
            if line.kind == "pair" and line.key == key:
                line.value = value
                line.raw = f"{key}={value}"
                return
        self.lines.append(IniLine(kind="pair", raw=f"{key}={value}", key=key, value=value))

    def as_dict(self) -> dict[str, str]:
        return {key: value for key, value in self.items()}


def parse_ini(text: str) -> IniFile:
    ini = IniFile()
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            ini.lines.append(IniLine(kind="blank", raw=raw_line))
            continue
        if stripped.startswith("#") or stripped.startswith(";"):
            ini.lines.append(IniLine(kind="comment", raw=raw_line))
            continue
        if "=" in stripped:
            key, value = stripped.split("=", 1)
            ini.lines.append(
                IniLine(kind="pair", raw=raw_line, key=key.strip(), value=value)
            )
            continue
        ini.lines.append(IniLine(kind="other", raw=raw_line))
    return ini


def serialize_ini(ini: IniFile) -> str:
    out: list[str] = []
    for line in ini.lines:
        if line.kind == "pair":
            out.append(f"{line.key}={line.value}")
        else:
            out.append(line.raw)
    text = "\n".join(out)
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def load_ini(path: Path) -> IniFile:
    return parse_ini(path.read_text(encoding="utf-8", errors="replace"))


def save_ini(path: Path, ini: IniFile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_ini(ini), encoding="utf-8")


def split_list(value: str) -> list[str]:
    if not value.strip():
        return []
    parts = []
    for chunk in value.replace(",", ";").split(";"):
        item = chunk.strip()
        if item:
            parts.append(item)
    return parts


def join_list(items: list[str]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ";".join(ordered)


CURATED_SERVER_FIELDS: list[dict[str, str]] = [
    {"key": "PublicName", "label": "Server name", "type": "text", "help": "Name shown in the in-game and Steam server browsers."},
    {"key": "PublicDescription", "label": "Description", "type": "textarea", "help": "Short public description."},
    {"key": "Public", "label": "List publicly", "type": "bool", "help": "Show this server in the public browser."},
    {"key": "Open", "label": "Open (no password required to join)", "type": "bool", "help": "If false, players need the server password."},
    {"key": "Password", "label": "Join password", "type": "password", "help": "Leave empty for no join password."},
    {"key": "MaxPlayers", "label": "Max players", "type": "number", "help": "Hard cap on connected players."},
    {"key": "PVP", "label": "PVP", "type": "bool", "help": "Allow player-versus-player damage."},
    {"key": "PauseEmpty", "label": "Pause when empty", "type": "bool", "help": "Pause the world when nobody is online."},
    {"key": "Map", "label": "Map", "type": "text", "help": "Comma-separated map folders; keep Muldraugh, KY last."},
    {"key": "DefaultPort", "label": "Default port", "type": "number", "help": "Primary game port."},
    {"key": "UDPPort", "label": "UDP port", "type": "number", "help": "Steam/UDP port."},
    {"key": "RCONPort", "label": "RCON port", "type": "number", "help": "Remote console port."},
    {"key": "RCONPassword", "label": "RCON password", "type": "password", "help": "Leave empty to disable RCON."},
    {"key": "Mods", "label": "Mods", "type": "hidden", "help": ""},
    {"key": "WorkshopItems", "label": "Workshop items", "type": "hidden", "help": ""},
]

CURATED_KEYS = {field["key"] for field in CURATED_SERVER_FIELDS}


def is_advanced_key(key: str) -> bool:
    return key not in CURATED_KEYS
