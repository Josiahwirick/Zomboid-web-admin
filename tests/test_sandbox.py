from app.pz.sandbox import (
    coerce_lua_value,
    flatten_sandbox,
    merge_sandbox,
    parse_sandbox_vars,
    serialize_sandbox_vars,
    unflatten_sandbox,
)
from tests.conftest import FIXTURES


def test_parse_nested_sandbox_vars():
    data = parse_sandbox_vars((FIXTURES / "servertest_SandboxVars.lua").read_text())
    assert data["VERSION"] == 5
    assert data["Zombies"] == 3
    assert data["XpMultiplier"] == 1.0
    assert data["PVP"] is False
    assert data["ZombieLore"]["Speed"] == 2
    assert data["CoolMod"]["EnableGuns"] is True


def test_roundtrip_keeps_unknown_keys():
    original = parse_sandbox_vars((FIXTURES / "servertest_SandboxVars.lua").read_text())
    text = serialize_sandbox_vars(original)
    again = parse_sandbox_vars(text)
    assert again["CoolMod"]["LootRate"] == 50
    assert again["ZombieConfig"]["PopulationPeakDay"] == 28


def test_merge_does_not_drop_unknown():
    existing = parse_sandbox_vars((FIXTURES / "servertest_SandboxVars.lua").read_text())
    merged = merge_sandbox(existing, {"Zombies": 4, "CoolMod": {"LootRate": 10}})
    assert merged["Zombies"] == 4
    assert merged["CoolMod"]["LootRate"] == 10
    assert merged["CoolMod"]["EnableGuns"] is True
    assert merged["DayLength"] == 3


def test_flatten_unflatten():
    data = {"A": 1, "B": {"C": True}}
    flat = flatten_sandbox(data)
    assert flat["A"] == 1
    assert flat["B.C"] is True
    assert unflatten_sandbox(flat) == data


def test_coerce_uses_template_type():
    assert coerce_lua_value("true", False) is True
    assert coerce_lua_value("on", False) is True
    assert coerce_lua_value("4", 1) == 4
    assert coerce_lua_value("1.5", 1.0) == 1.5
    assert coerce_lua_value("hello", "x") == "hello"
