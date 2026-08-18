from app.pz.mods import (
    apply_translations,
    parse_mod_info,
    parse_sandbox_options,
    parse_sandbox_translations,
    workshop_id_from_url,
)
from tests.conftest import FIXTURES


def test_parse_mod_info():
    info = parse_mod_info((FIXTURES / "mod.info").read_text())
    assert info.mod_id == "CoolMod"
    assert info.name == "Cool Weapons"
    assert info.require == ["ModFramework"]


def test_parse_sandbox_options_and_translations():
    options = parse_sandbox_options((FIXTURES / "sandbox-options.txt").read_text())
    assert [opt.dotted for opt in options] == [
        "CoolMod.LootRate",
        "CoolMod.EnableGuns",
        "CoolMod.Rarity",
    ]
    loot = options[0]
    assert loot.type == "integer"
    assert loot.default == 50
    assert loot.min == 0
    assert loot.max == 100
    guns = options[1]
    assert guns.type == "boolean"
    assert guns.default is True
    rarity = options[2]
    assert rarity.type == "enum"
    assert rarity.num_values == 3

    trans = parse_sandbox_translations((FIXTURES / "Sandbox_EN.txt").read_text())
    apply_translations(options, trans)
    assert loot.label == "Loot rate"
    assert loot.tooltip == "Percent chance for extra loot."
    assert rarity.enum_labels == ["Rare", "Normal", "Common"]


def test_workshop_id_from_url():
    assert workshop_id_from_url("2286124930") == "2286124930"
    assert (
        workshop_id_from_url("https://steamcommunity.com/sharedfiles/filedetails/?id=2286124930")
        == "2286124930"
    )
    assert workshop_id_from_url("not-an-id") == ""
