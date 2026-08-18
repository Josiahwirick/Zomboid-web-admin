from app.pz.mods import parse_sandbox_options, parse_sandbox_translations, apply_translations
from app.pz.sandbox import parse_sandbox_vars
from app.pz.sections import build_sandbox_sections, seed_mod_defaults
from tests.conftest import FIXTURES


def test_mod_options_become_their_own_section():
    data = parse_sandbox_vars((FIXTURES / "servertest_SandboxVars.lua").read_text())
    options = parse_sandbox_options((FIXTURES / "sandbox-options.txt").read_text())
    trans = parse_sandbox_translations((FIXTURES / "Sandbox_EN.txt").read_text())
    apply_translations(options, trans)
    seed_mod_defaults(data, options)
    sections = build_sandbox_sections(data, [("CoolMod", "Cool Weapons", options)])
    ids = [s.id for s in sections]
    assert "zombie_lore" in ids
    mod_section = next(s for s in sections if s.source == "mod")
    labels = [f.label for f in mod_section.fields]
    assert "Loot rate" in labels
    paths = [f.path for f in mod_section.fields]
    assert "CoolMod.LootRate" in paths
