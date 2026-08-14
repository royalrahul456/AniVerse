from utils.emojis import get_emoji
import asyncio
from handlers.admin import parse_name_and_anime

def test_bracket_parsing():
    test_cases = [
        ("Monkey D. Luffy [One Piece]", "Monkey D. Luffy", "One Piece"),
        ("[One Piece] Monkey D. Luffy", "Monkey D. Luffy", "One Piece"),
        ("Rem (Re:Zero)", "Rem", "Re:Zero"),
        ("Saitama", "Saitama", None),
        ("Gojo Satoru [Jujutsu Kaisen]", "Gojo Satoru", "Jujutsu Kaisen"),
    ]
    for raw, expected_name, expected_anime in test_cases:
        n, a = parse_name_and_anime(raw)
        assert n == expected_name, f"Expected name {expected_name}, got {n}"
        assert a == expected_anime, f"Expected anime {expected_anime}, got {a}"
        print(f"{get_emoji('success')} Tested '{raw}' -> Name: '{n}', Anime: '{a}'")

if __name__ == "__main__":
    test_bracket_parsing()
