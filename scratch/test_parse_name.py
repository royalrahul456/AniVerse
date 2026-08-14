import re

def parse_name_and_anime(raw_input: str):
    if not raw_input:
        return '', None
    raw = raw_input.strip()
    match_square = re.search(r'\[(.*?)\]', raw)
    if match_square:
        anime_extracted = match_square.group(1).strip()
        name_clean = re.sub(r'\[.*?\]', '', raw).strip()
        if name_clean and anime_extracted:
            return name_clean, anime_extracted
    match_round = re.search(r'\((.*?)\)', raw)
    if match_round:
        anime_extracted = match_round.group(1).strip()
        name_clean = re.sub(r'\(.*?\)', '', raw).strip()
        if name_clean and anime_extracted:
            return name_clean, anime_extracted
    return raw, None

if __name__ == "__main__":
    tests = [
        "Monkey D. Luffy [One Piece]",
        "[One Piece] Monkey D. Luffy",
        "Rem (Re:Zero)",
        "Saitama",
        "Gojo Satoru [Jujutsu Kaisen]"
    ]
    for t in tests:
        name, anime = parse_name_and_anime(t)
        print(f"Input: '{t}' -> Name: '{name}' | Anime: {anime}")
