from app.pz.ini import join_list, parse_ini, serialize_ini, split_list
from tests.conftest import FIXTURES


def test_parse_preserves_order_and_values():
    ini = parse_ini((FIXTURES / "servertest.ini").read_text())
    assert ini.get("PublicName") == "Test Knox Server"
    assert ini.get("MaxPlayers") == "8"
    assert ini.get("WorkshopItems") == "123456789;987654321"
    assert ini.keys()[0] == "PublicName"
    assert "AntiCheatProtectionType1" in ini.keys()


def test_set_rewrites_existing_and_appends_new():
    ini = parse_ini((FIXTURES / "servertest.ini").read_text())
    ini.set("PublicName", "Renamed")
    ini.set("BrandNew", "yes")
    text = serialize_ini(ini)
    again = parse_ini(text)
    assert again.get("PublicName") == "Renamed"
    assert again.get("BrandNew") == "yes"
    assert again.get("Mods") == "SomeMod;AnotherMod"


def test_split_join_lists():
    assert split_list("a;b;c") == ["a", "b", "c"]
    assert split_list("a, b; c") == ["a", "b", "c"]
    assert join_list(["a", "a", " b ", ""]) == "a;b"
    assert split_list("") == []
