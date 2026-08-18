from __future__ import annotations

import socket
import struct
from dataclasses import dataclass


SERVERDATA_AUTH = 3
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_RESPONSE_VALUE = 0


class RconError(RuntimeError):
    pass


@dataclass
class PlayerList:
    raw: str
    names: list[str]

    @property
    def count(self) -> int:
        return len(self.names)


def parse_players_output(text: str) -> PlayerList:
    """Parse PZ `players` RCON output into names."""
    names: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("playersconnected") or lowered.startswith("players connected"):
            continue
        if "connected" in lowered and line.endswith(":"):
            continue
        # Typical: "- name" or "name" or numbered lists
        cleaned = line.lstrip("-").strip()
        if cleaned.startswith("*"):
            cleaned = cleaned[1:].strip()
        if cleaned and not cleaned.lower().startswith("players"):
            names.append(cleaned)
    return PlayerList(raw=text, names=names)


class RconClient:
    def __init__(self, host: str, port: int, password: str, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._req_id = 0

    def __enter__(self) -> "RconClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        self._sock = sock
        resp = self._send(SERVERDATA_AUTH, self.password)
        if resp[0] == -1:
            self.close()
            raise RconError("RCON authentication failed")

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def command(self, body: str) -> str:
        if self._sock is None:
            self.connect()
        req_id, _kind, payload = self._send(SERVERDATA_EXECCOMMAND, body)
        if req_id == -1:
            raise RconError("RCON command rejected")
        return payload

    def _send(self, kind: int, body: str) -> tuple[int, int, str]:
        assert self._sock is not None
        self._req_id += 1
        req_id = self._req_id
        encoded = body.encode("utf-8")
        packet = struct.pack("<ii", req_id, kind) + encoded + b"\x00\x00"
        self._sock.sendall(struct.pack("<i", len(packet)) + packet)
        return self._read_packet()

    def _read_packet(self) -> tuple[int, int, str]:
        assert self._sock is not None
        length_raw = self._recv_exact(4)
        (length,) = struct.unpack("<i", length_raw)
        payload = self._recv_exact(length)
        req_id, kind = struct.unpack("<ii", payload[:8])
        body = payload[8:-2].decode("utf-8", errors="replace")
        return req_id, kind, body

    def _recv_exact(self, size: int) -> bytes:
        assert self._sock is not None
        chunks = b""
        while len(chunks) < size:
            piece = self._sock.recv(size - len(chunks))
            if not piece:
                raise RconError("RCON connection closed")
            chunks += piece
        return chunks


def fetch_players(host: str, port: int, password: str) -> PlayerList | None:
    if not password:
        return None
    try:
        with RconClient(host, port, password) as client:
            raw = client.command("players")
        return parse_players_output(raw)
    except (OSError, RconError):
        return None
