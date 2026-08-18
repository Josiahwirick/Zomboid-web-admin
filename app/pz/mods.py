from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.pz.ini import split_list

VANILLA_GROUPS_PATH = Path(__file__).resolve().parent.parent / "data" / "vanilla_sandbox_groups.json"


@dataclass
class ModInfo:
    mod_id: str
    name: str = ""
    description: str = ""
    require: list[str] = field(default_factory=list)
    poster: str = ""
    path: Path | None = None
    workshop_id: str = ""


@dataclass
class SandboxOption:
    table_name: str
    option_name: str
    type: str
    default: Any
    min: Any = None
    max: Any = None
    num_values: int | None = None
    page: str = ""
    translation: str = ""
    label: str = ""
    tooltip: str = ""
    enum_labels: list[str] = field(default_factory=list)

    @property
    def dotted(self) -> str:
        return f"{self.table_name}.{self.option_name}"


def parse_mod_info(text: str) -> ModInfo:
    data: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip().lower()] = value.strip()
    require = split_list(data.get("require", ""))
    return ModInfo(
        mod_id=data.get("id", ""),
        name=data.get("name", "") or data.get("id", ""),
        description=data.get("description", ""),
        require=require,
        poster=data.get("poster", ""),
    )


def parse_sandbox_options(text: str) -> list[SandboxOption]:
    options: list[SandboxOption] = []
    i = 0
    lines = text.splitlines()
    n = len(lines)
    while i < n:
        stripped = lines[i].strip()
        if stripped.startswith("option "):
            ident = stripped[len("option ") :].strip()
            table_name, option_name = _split_option_ident(ident)
            i += 1
            block: dict[str, str] = {}
            while i < n and "{" not in lines[i]:
                i += 1
            if i < n and "{" in lines[i]:
                i += 1
            while i < n and "}" not in lines[i].split("//")[0]:
                inner = lines[i].split("//")[0].strip().rstrip(",")
                if "=" in inner:
                    key, value = inner.split("=", 1)
                    block[key.strip().lower()] = value.strip().rstrip(",")
                i += 1
            option_type = block.get("type", "string")
            default = _coerce_option_default(option_type, block.get("default", ""))
            min_v = _maybe_number(block.get("min"))
            max_v = _maybe_number(block.get("max"))
            num_values = None
            if "numvalues" in block:
                try:
                    num_values = int(block["numvalues"])
                except ValueError:
                    num_values = None
            options.append(
                SandboxOption(
                    table_name=table_name,
                    option_name=option_name,
                    type=option_type,
                    default=default,
                    min=min_v,
                    max=max_v,
                    num_values=num_values,
                    page=block.get("page", "") or table_name,
                    translation=block.get("translation", ""),
                    label=option_name,
                )
            )
        i += 1
    return options


def parse_sandbox_translations(text: str) -> dict[str, str]:
    """Parse PZ translation files: Sandbox_Page = "Label", etc."""
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip().rstrip(",")
        if not line or line.startswith("--") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().strip('"')
        value = value.strip().strip(",").strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        result[key] = value.replace("\\n", "\n")
    return result


def apply_translations(options: list[SandboxOption], translations: dict[str, str]) -> None:
    for option in options:
        page_key = f"Sandbox_{option.page}"
        name_key = f"Sandbox_{option.translation}" if option.translation else ""
        tooltip_key = f"{name_key}_tooltip" if name_key else ""
        if name_key and name_key in translations:
            option.label = translations[name_key]
        elif f"Sandbox_{option.table_name}_{option.option_name}" in translations:
            option.label = translations[f"Sandbox_{option.table_name}_{option.option_name}"]
        if tooltip_key and tooltip_key in translations:
            option.tooltip = translations[tooltip_key]
        if option.type == "enum" and option.num_values:
            labels: list[str] = []
            base = option.translation or f"{option.table_name}_{option.option_name}"
            for idx in range(1, option.num_values + 1):
                labels.append(
                    translations.get(f"Sandbox_{base}_option{idx}", str(idx))
                )
            option.enum_labels = labels


def load_vanilla_groups() -> list[dict[str, Any]]:
    if not VANILLA_GROUPS_PATH.exists():
        return []
    return json.loads(VANILLA_GROUPS_PATH.read_text(encoding="utf-8"))


def find_mod_roots(search_dirs: list[Path], workshop_id: str | None = None) -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for base in search_dirs:
        if not base or not base.exists():
            continue
        candidates = [base]
        if workshop_id:
            candidates = [base / workshop_id, base]
        for candidate in candidates:
            if not candidate.exists():
                continue
            for info in candidate.rglob("mod.info"):
                root = info.parent
                resolved = root.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                roots.append(root)
    return roots


def load_mod_info_from_dir(mod_dir: Path, workshop_id: str = "") -> ModInfo | None:
    info_path = mod_dir / "mod.info"
    if not info_path.exists():
        return None
    info = parse_mod_info(info_path.read_text(encoding="utf-8", errors="replace"))
    info.path = mod_dir
    info.workshop_id = workshop_id
    return info


def load_mod_sandbox_schema(mod_dir: Path) -> tuple[list[SandboxOption], dict[str, str]]:
    options: list[SandboxOption] = []
    translations: dict[str, str] = {}
    sandbox_file = mod_dir / "media" / "sandbox-options.txt"
    if sandbox_file.exists():
        options = parse_sandbox_options(sandbox_file.read_text(encoding="utf-8", errors="replace"))
    trans_dir = mod_dir / "media" / "lua" / "shared" / "Translate"
    if trans_dir.exists():
        preferred = list(trans_dir.glob("EN/Sandbox_EN.txt")) + list(trans_dir.glob("EN/Sandbox*.txt"))
        fallback = list(trans_dir.rglob("Sandbox*.txt"))
        for path in preferred + fallback:
            translations.update(parse_sandbox_translations(path.read_text(encoding="utf-8", errors="replace")))
            if translations:
                break
    apply_translations(options, translations)
    return options, translations


def workshop_id_from_url(value: str) -> str:
    text = value.strip()
    if "id=" in text:
        after = text.split("id=", 1)[1]
        digits = ""
        for ch in after:
            if ch.isdigit():
                digits += ch
            else:
                break
        return digits
    if text.isdigit():
        return text
    return ""


def _split_option_ident(ident: str) -> tuple[str, str]:
    ident = ident.strip()
    if "." in ident:
        table, name = ident.split(".", 1)
        return table.strip(), name.strip()
    return ident, ident


def _maybe_number(raw: str | None) -> int | float | None:
    if raw is None or raw == "":
        return None
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return None


def _coerce_option_default(option_type: str, raw: str) -> Any:
    text = (raw or "").strip()
    if option_type == "boolean":
        return text.lower() in {"true", "1", "yes"}
    if option_type == "integer":
        try:
            return int(float(text)) if text else 0
        except ValueError:
            return 0
    if option_type == "double":
        try:
            return float(text) if text else 0.0
        except ValueError:
            return 0.0
    if option_type == "enum":
        try:
            return int(text) if text else 1
        except ValueError:
            return 1
    return text


def collect_enabled_mod_options(
    search_dirs: list[Path],
    workshop_ids: list[str],
    mod_ids: list[str],
) -> list[tuple[ModInfo, list[SandboxOption]]]:
    """Find sandbox-options for mods that are enabled (or at least downloaded)."""
    results: list[tuple[ModInfo, list[SandboxOption]]] = []
    seen_ids: set[str] = set()
    roots = find_mod_roots(search_dirs)
    for root in roots:
        workshop_id = ""
        for part in root.parts:
            if part.isdigit() and len(part) >= 6:
                workshop_id = part
        info = load_mod_info_from_dir(root, workshop_id=workshop_id)
        if not info or not info.mod_id:
            continue
        if info.mod_id in seen_ids:
            continue
        if mod_ids and info.mod_id not in mod_ids:
            # Still include if its workshop package is listed
            if workshop_id and workshop_id not in workshop_ids:
                continue
        seen_ids.add(info.mod_id)
        options, _ = load_mod_sandbox_schema(root)
        if options:
            results.append((info, options))
    return results
