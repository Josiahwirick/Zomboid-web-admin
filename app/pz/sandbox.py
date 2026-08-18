from __future__ import annotations

from typing import Any


class LuaParseError(ValueError):
    pass


class _Lexer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.n = len(text)
        self.i = 0

    def peek(self) -> str:
        return self.text[self.i] if self.i < self.n else ""

    def eof(self) -> bool:
        return self.i >= self.n

    def skip_ws_and_comments(self) -> None:
        while not self.eof():
            ch = self.peek()
            if ch in " \t\r\n":
                self.i += 1
                continue
            if ch == "-" and self.i + 1 < self.n and self.text[self.i + 1] == "-":
                self.i += 2
                while not self.eof() and self.peek() not in "\n":
                    self.i += 1
                continue
            break

    def read_ident(self) -> str:
        start = self.i
        if not (self.peek().isalpha() or self.peek() == "_"):
            raise LuaParseError(f"Expected identifier at {self.i}")
        self.i += 1
        while not self.eof() and (self.peek().isalnum() or self.peek() == "_"):
            self.i += 1
        return self.text[start : self.i]

    def read_string(self) -> str:
        quote = self.peek()
        if quote not in "'\"":
            raise LuaParseError("Expected string")
        self.i += 1
        out: list[str] = []
        while not self.eof():
            ch = self.peek()
            if ch == "\\":
                self.i += 1
                esc = self.peek()
                mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}
                out.append(mapping.get(esc, esc))
                self.i += 1
                continue
            if ch == quote:
                self.i += 1
                return "".join(out)
            out.append(ch)
            self.i += 1
        raise LuaParseError("Unterminated string")

    def read_number(self) -> int | float:
        start = self.i
        if self.peek() == "-":
            self.i += 1
        while not self.eof() and (self.peek().isdigit() or self.peek() in ".eE+-"):
            # Don't consume a second minus that belongs to the next token
            if self.peek() in "+-" and self.i > start and self.text[self.i - 1] not in "eE":
                break
            self.i += 1
        raw = self.text[start : self.i]
        if "." in raw or "e" in raw.lower():
            return float(raw)
        return int(raw)


def parse_lua_value(text: str) -> Any:
    lexer = _Lexer(text)
    lexer.skip_ws_and_comments()
    value = _parse_value(lexer)
    lexer.skip_ws_and_comments()
    return value


def parse_sandbox_vars(text: str) -> dict[str, Any]:
    lexer = _Lexer(text)
    lexer.skip_ws_and_comments()
    ident = lexer.read_ident()
    if ident != "SandboxVars":
        # Allow a bare table, or "return { ... }"
        if ident == "return":
            lexer.skip_ws_and_comments()
            value = _parse_value(lexer)
            if not isinstance(value, dict):
                raise LuaParseError("Expected table after return")
            return value
        raise LuaParseError("Expected SandboxVars = { ... }")
    lexer.skip_ws_and_comments()
    if lexer.peek() != "=":
        raise LuaParseError("Expected '=' after SandboxVars")
    lexer.i += 1
    lexer.skip_ws_and_comments()
    value = _parse_value(lexer)
    if not isinstance(value, dict):
        raise LuaParseError("SandboxVars must be a table")
    return value


def _parse_value(lexer: _Lexer) -> Any:
    lexer.skip_ws_and_comments()
    ch = lexer.peek()
    if ch == "{":
        return _parse_table(lexer)
    if ch in "'\"":
        return lexer.read_string()
    if ch.isdigit() or ch == "-" or ch == ".":
        return lexer.read_number()
    ident = lexer.read_ident()
    if ident == "true":
        return True
    if ident == "false":
        return False
    if ident == "nil":
        return None
    raise LuaParseError(f"Unexpected identifier {ident!r}")


def _parse_table(lexer: _Lexer) -> dict[str, Any] | list[Any]:
    lexer.skip_ws_and_comments()
    if lexer.peek() != "{":
        raise LuaParseError("Expected '{'")
    lexer.i += 1
    mapping: dict[str, Any] = {}
    array: list[Any] = []
    is_array = True
    index = 1
    lexer.skip_ws_and_comments()
    while not lexer.eof() and lexer.peek() != "}":
        lexer.skip_ws_and_comments()
        if lexer.peek() == "}":
            break
        key: str | None = None
        # [expr] = value
        if lexer.peek() == "[":
            lexer.i += 1
            lexer.skip_ws_and_comments()
            if lexer.peek() in "'\"":
                key = lexer.read_string()
            else:
                num = lexer.read_number()
                key = str(num)
            lexer.skip_ws_and_comments()
            if lexer.peek() != "]":
                raise LuaParseError("Expected ']'")
            lexer.i += 1
            lexer.skip_ws_and_comments()
            if lexer.peek() != "=":
                raise LuaParseError("Expected '=' after table key")
            lexer.i += 1
            value = _parse_value(lexer)
            is_array = False
            mapping[key] = value
        else:
            # Lookahead: ident = value  vs  bare value
            saved = lexer.i
            try:
                maybe_ident = lexer.read_ident()
                lexer.skip_ws_and_comments()
                if lexer.peek() == "=":
                    lexer.i += 1
                    value = _parse_value(lexer)
                    is_array = False
                    mapping[maybe_ident] = value
                else:
                    lexer.i = saved
                    value = _parse_value(lexer)
                    array.append(value)
                    mapping[str(index)] = value
                    index += 1
            except LuaParseError:
                lexer.i = saved
                value = _parse_value(lexer)
                array.append(value)
                mapping[str(index)] = value
                index += 1
        lexer.skip_ws_and_comments()
        if lexer.peek() == ",":
            lexer.i += 1
            lexer.skip_ws_and_comments()
    if lexer.peek() != "}":
        raise LuaParseError("Unterminated table")
    lexer.i += 1
    if is_array and array:
        return array
    return mapping


def serialize_sandbox_vars(data: dict[str, Any]) -> str:
    body = _encode(data, 1)
    return f"SandboxVars = {body}\n"


def _encode(value: Any, indent: int) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    if isinstance(value, str):
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'
    if isinstance(value, list):
        if not value:
            return "{}"
        inner = ", ".join(_encode(item, indent + 1) for item in value)
        return "{ " + inner + " }"
    if isinstance(value, dict):
        if not value:
            return "{}"
        pad = "    " * indent
        closer = "    " * (indent - 1)
        parts: list[str] = ["{"]
        items = list(value.items())
        for i, (key, item) in enumerate(items):
            key_text = key if _is_ident(str(key)) else f'["{key}"]'
            comma = "," if i < len(items) - 1 else ","
            parts.append(f"{pad}{key_text} = {_encode(item, indent + 1)}{comma}")
        parts.append(f"{closer}}}")
        return "\n".join(parts)
    return f'"{value}"'


def _is_ident(key: str) -> bool:
    if not key or not (key[0].isalpha() or key[0] == "_"):
        return False
    return all(ch.isalnum() or ch == "_" for ch in key)


def merge_sandbox(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge updates into existing without dropping unknown keys."""
    result = dict(existing)
    for key, value in updates.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = merge_sandbox(result[key], value)
        else:
            result[key] = value
    return result


def flatten_sandbox(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(flatten_sandbox(value, path))
        else:
            out[path] = value
    return out


def unflatten_sandbox(flat: dict[str, Any]) -> dict[str, Any]:
    root: dict[str, Any] = {}
    for path, value in flat.items():
        parts = [p for p in path.split(".") if p]
        if not parts:
            continue
        cursor = root
        for part in parts[:-1]:
            nxt = cursor.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                cursor[part] = nxt
            cursor = nxt
        cursor[parts[-1]] = value
    return root


def coerce_lua_value(raw: str, template: Any = None) -> Any:
    text = raw.strip()
    if template is True or template is False:
        return text.lower() in {"1", "true", "on", "yes"}
    if isinstance(template, int) and not isinstance(template, bool):
        if text == "":
            return template
        if "." in text:
            return int(float(text))
        return int(text)
    if isinstance(template, float):
        return float(text) if text else template
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text
