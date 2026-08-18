from pathlib import Path

from app.config import Settings
from app.pz.apply import UnsafeEditError, apply_writes
from app.pz import process as process_mod
from app.pz.ini import parse_ini, serialize_ini
from tests.conftest import FIXTURES


def _settings(tmp_path: Path) -> Settings:
    zhome = tmp_path / "Zomboid"
    (zhome / "Server").mkdir(parents=True)
    ini_src = (FIXTURES / "servertest.ini").read_text()
    (zhome / "Server" / "servertest.ini").write_text(ini_src)
    (zhome / "Server" / "servertest_SandboxVars.lua").write_text(
        (FIXTURES / "servertest_SandboxVars.lua").read_text()
    )
    return Settings(
        admin_user="admin",
        admin_password="secret",
        session_secret="test-secret-key",
        bind_host="127.0.0.1",
        bind_port=8080,
        zomboid_home=zhome,
        pz_server_name="servertest",
        pz_install_dir=None,
        steam_workshop_dir=None,
        pz_start_cmd="true",
        pz_stop_cmd="true",
        pz_status_cmd="",
        rcon_host="127.0.0.1",
        rcon_port=None,
        backup_dir=tmp_path / "backups",
    )


def test_refuses_live_edit_without_restart(tmp_path, monkeypatch):
    settings = _settings(tmp_path)

    class FakeStats:
        running = True

    monkeypatch.setattr(process_mod, "get_stats", lambda *_a, **_k: FakeStats())
    wrote = {"n": 0}

    def write() -> None:
        wrote["n"] += 1

    try:
        apply_writes(settings, [write], restart=False, files=[settings.ini_path])
        assert False, "expected UnsafeEditError"
    except UnsafeEditError:
        pass
    assert wrote["n"] == 0


def test_stop_backup_write_start(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    state = {"running": True, "stopped": 0, "started": 0}

    class FakeStats:
        def __init__(self, running: bool) -> None:
            self.running = running

    monkeypatch.setattr(
        process_mod, "get_stats", lambda *_a, **_k: FakeStats(state["running"])
    )

    def fake_stop(_cmd, wait_timeout=90):
        state["running"] = False
        state["stopped"] += 1

        class R:
            ok = True
            message = "stopped"

        return R()

    def fake_start(_cmd):
        state["running"] = True
        state["started"] += 1

        class R:
            ok = True
            message = "started"

        return R()

    monkeypatch.setattr(process_mod, "stop", fake_stop)
    monkeypatch.setattr(process_mod, "start", fake_start)

    def write() -> None:
        ini = parse_ini(settings.ini_path.read_text())
        ini.set("PublicName", "After Restart")
        settings.ini_path.write_text(serialize_ini(ini))

    result = apply_writes(settings, [write], restart=True, files=[settings.ini_path])
    assert result.ok
    assert result.restarted
    assert state["stopped"] == 1
    assert state["started"] == 1
    assert "After Restart" in settings.ini_path.read_text()
    backups = list((tmp_path / "backups").iterdir())
    assert backups
    assert (backups[0] / "servertest.ini").exists()
