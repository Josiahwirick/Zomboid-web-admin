from app.pz.rcon import parse_players_output


def test_parse_players_output():
    raw = """Players connected: 2
- Alice
- Bob
"""
    listing = parse_players_output(raw)
    assert listing.count == 2
    assert listing.names == ["Alice", "Bob"]


def test_parse_players_ignores_header_only():
    listing = parse_players_output("Players connected: 0\n")
    assert listing.names == []
