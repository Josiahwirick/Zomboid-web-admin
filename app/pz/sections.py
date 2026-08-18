from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.pz.mods import SandboxOption, load_vanilla_groups
from app.pz.sandbox import flatten_sandbox


@dataclass
class FieldSpec:
    path: str
    label: str
    value: Any
    kind: str  # bool, int, float, enum, string, other
    help: str = ""
    min: Any = None
    max: Any = None
    enum_labels: list[str] = field(default_factory=list)


@dataclass
class Section:
    id: str
    label: str
    source: str  # vanilla | mod | other
    fields: list[FieldSpec] = field(default_factory=list)
    mod_id: str = ""


def _kind_from_value(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "string"


def _field_from_value(path: str, value: Any, label: str | None = None) -> FieldSpec:
    return FieldSpec(
        path=path,
        label=label or path.split(".")[-1],
        value=value,
        kind=_kind_from_value(value),
    )


def _field_from_option(option: SandboxOption, value: Any) -> FieldSpec:
    kind = {
        "boolean": "bool",
        "integer": "int",
        "double": "float",
        "enum": "enum",
        "string": "string",
    }.get(option.type, "string")
    return FieldSpec(
        path=option.dotted,
        label=option.label or option.option_name,
        value=value,
        kind=kind,
        help=option.tooltip,
        min=option.min,
        max=option.max,
        enum_labels=option.enum_labels,
    )


def get_nested(data: dict[str, Any], path: str) -> Any:
    cursor: Any = data
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def set_nested(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor = data
    for part in parts[:-1]:
        nxt = cursor.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cursor[part] = nxt
        cursor = nxt
    cursor[parts[-1]] = value


def seed_mod_defaults(sandbox: dict[str, Any], options: list[SandboxOption]) -> None:
    for option in options:
        current = get_nested(sandbox, option.dotted)
        if current is None:
            set_nested(sandbox, option.dotted, option.default)


def build_sandbox_sections(
    sandbox: dict[str, Any],
    mod_sections: list[tuple[str, str, list[SandboxOption]]],
) -> list[Section]:
    claimed: set[str] = set()
    sections: list[Section] = []
    raw = load_vanilla_groups()
    groups = raw.get("groups", []) if isinstance(raw, dict) else raw

    for group in groups:
        fields: list[FieldSpec] = []
        for key in group.get("keys", []):
            value = sandbox.get(key)
            if value is None:
                continue
            if isinstance(value, dict):
                for nested_key, nested_val in value.items():
                    if isinstance(nested_val, dict):
                        continue
                    path = f"{key}.{nested_key}"
                    fields.append(_field_from_value(path, nested_val))
                    claimed.add(path)
                claimed.add(key)
            else:
                fields.append(_field_from_value(key, value))
                claimed.add(key)
        if fields:
            sections.append(Section(id=group["id"], label=group["label"], source="vanilla", fields=fields))

    for mod_id, mod_name, options in mod_sections:
        by_page: dict[str, list[FieldSpec]] = {}
        for option in options:
            value = get_nested(sandbox, option.dotted)
            if value is None:
                value = option.default
            field = _field_from_option(option, value)
            by_page.setdefault(option.page or mod_name, []).append(field)
            claimed.add(option.dotted)
            claimed.add(option.table_name)
        for page, fields in by_page.items():
            section_id = f"mod-{mod_id}-{page}".replace(" ", "-")
            sections.append(
                Section(
                    id=section_id,
                    label=f"{mod_name}: {page}" if page != mod_name else mod_name,
                    source="mod",
                    fields=fields,
                    mod_id=mod_id,
                )
            )

    leftover: list[FieldSpec] = []
    for path, value in flatten_sandbox(sandbox).items():
        top = path.split(".", 1)[0]
        if path in claimed or top in claimed:
            continue
        leftover.append(_field_from_value(path, value))
    if leftover:
        sections.append(Section(id="other", label="Other", source="other", fields=leftover))

    return sections
