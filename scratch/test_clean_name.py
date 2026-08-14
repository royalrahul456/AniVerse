from utils.emojis import get_emoji
import re

def get_clean_name(name: str) -> str:
    if not name:
        return ""
    text = re.sub(r'\[.*?\]', '', name)
    text = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE)
    return text.strip()

if __name__ == "__main__":
    tests = [
        "Luffy 🏴‍☠️",
        f"Zenitsu {get_emoji('energy')}",
        "Gojo Satoru 💥",
        "Rem 💙 [Special]",
        "Levi Ackerman ⚔️"
    ]
    for t in tests:
        cleaned = get_clean_name(t)
        print(f"Original: '{t}' -> Cleaned: '{cleaned}'")
