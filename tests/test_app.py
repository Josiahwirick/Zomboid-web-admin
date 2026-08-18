from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.pz import process as process_mod
from app.pz import steam as steam_mod
from tests.conftest import FIXTURES


def _settings(tmp_path: Path) -> Settings:
    zhome = tmp_path / "Zomboid"
    server = zhome / "Server"
    workshop = tmp_path / "workshop" / "123456789" / "mods" / "CoolMod"
    if not server.exists():
        server.mkdir(parents=True)
        (server / "servertest.ini").write_text((FIXTURES / "servertest.ini").read_text())
        (server / "servertest_SandboxVars.lua").write_text(
            (FIXTURES / "servertest_SandboxVars.lua").read_text()
        )
    if not workshop.exists():
        (workshop / "media" / "lua" / "shared" / "Translate" / "EN").mkdir(parents=True)
        (workshop / "mod.info").write_text((FIXTURES / "mod.info").read_text())
        (workshop / "media" / "sandbox-options.txt").write_text(
            (FIXTURES / "sandbox-options.txt").read_text()
        )
        (workshop / "media" / "lua" / "shared" / "Translate" / "EN" / "Sandbox_EN.txt").write_text(
            (FIXTURES / "Sandbox_EN.txt").read_text()
        )
    return Settings(
        admin_user="admin",
        admin_password="secret",
        session_secret="test-secret-key-please-change",
        bind_host="127.0.0.1",
        bind_port=8080,
        zomboid_home=zhome,
        pz_server_name="servertest",
        pz_install_dir=None,
        steam_workshop_dir=tmp_path / "workshop",
        pz_start_cmd="true",
        pz_stop_cmd="true",
        pz_status_cmd="",
        rcon_host="127.0.0.1",
        rcon_port=None,
        backup_dir=tmp_path / "backups",
    )


class Stopped:
    running = False
    pid = None
    cpu_percent = None
    memory_rss_mb = None
    memory_percent = None
    uptime_seconds = None
    name = ""
    error = ""


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(process_mod, "get_stats", lambda *_a, **_k: Stopped())
    monkeypatch.setattr(steam_mod, "fetch_workshop_titles", lambda *_a, **_k: {"123456789": "Cool Pack"})
    app = create_app(_settings(tmp_path))
    return TestClient(app)


def test_login_required(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_and_dashboard(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    bad = client.post("/login", data={"username": "admin", "password": "nope"})
    assert bad.status_code == 401
    ok = client.post("/login", data={"username": "admin", "password": "secret"}, follow_redirects=False)
    assert ok.status_code == 303
    dash = client.get("/")
    assert dash.status_code == 200
    assert "Dashboard" in dash.text
    assert "Test Knox Server" in dash.text


def test_server_save_when_stopped(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "admin", "password": "secret"})
    page = client.get("/server")
    assert "PublicName" in page.text
    start = page.text.index('name="csrf"')
    token = page.text[start:].split('value="', 1)[1].split('"', 1)[0]
    response = client.post(
        "/server",
        data={
            "csrf": token,
            "PublicName": "New Name",
            "PublicDescription": "desc",
            "Public": "false",
            "Open": "true",
            "Password": "",
            "MaxPlayers": "12",
            "PVP": "true",
            "PauseEmpty": "true",
            "Map": "Muldraugh, KY",
            "DefaultPort": "16261",
            "UDPPort": "16262",
            "RCONPort": "27015",
            "RCONPassword": "rcon-secret",
            "restart": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    saved = (_settings(tmp_path).ini_path).read_text()
    assert "PublicName=New Name" in saved
    assert "MaxPlayers=12" in saved


def test_workshop_and_sandbox_pages(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "admin", "password": "secret"})
    workshop = client.get("/workshop")
    assert workshop.status_code == 200
    assert "123456789" in workshop.text
    assert "CoolMod" in workshop.text
    sandbox = client.get("/sandbox")
    assert sandbox.status_code == 200
    assert "Loot rate" in sandbox.text or "LootRate" in sandbox.text
    assert "Zombie lore" in sandbox.text or "ZombieLore" in sandbox.text


def _csrf(html: str) -> str:
    start = html.index('name="csrf"')
    return html[start:].split('value="', 1)[1].split('"', 1)[0]


def test_workshop_add_id_when_stopped(tmp_path, monkeypatch):
    from urllib.parse import urlencode

    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "admin", "password": "secret"})
    page = client.get("/workshop")
    token = _csrf(page.text)
    body = urlencode(
        [
            ("csrf", token),
            ("workshop_ids", "123456789"),
            ("workshop_ids", "987654321"),
            ("mod_ids", "CoolMod"),
            ("add_workshop", "https://steamcommunity.com/sharedfiles/filedetails/?id=555555555"),
            ("restart", "0"),
        ]
    )
    response = client.post(
        "/workshop",
        content=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    saved = _settings(tmp_path).ini_path.read_text()
    assert "555555555" in saved
    assert "123456789" in saved
    assert "987654321" in saved
    assert "Mods=CoolMod" in saved


def test_sandbox_save_when_stopped(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "admin", "password": "secret"})
    page = client.get("/sandbox")
    token = _csrf(page.text)
    response = client.post(
        "/sandbox",
        data={
            "csrf": token,
            "sv.Zombies": "1",
            "sv.CoolMod.LootRate": "12",
            "sv.CoolMod.EnableGuns": "false",
            "restart": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    from app.pz.sandbox import parse_sandbox_vars

    data = parse_sandbox_vars(_settings(tmp_path).sandbox_path.read_text())
    assert data["Zombies"] == 1
    assert data["CoolMod"]["LootRate"] == 12
    assert data["CoolMod"]["EnableGuns"] is False
    assert data["DayLength"] == 3

