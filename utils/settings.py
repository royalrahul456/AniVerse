import json
import os

SETTINGS_FILE = "data/settings.json"
DEFAULT_ANIME_BANNER = "https://images7.alphacoders.com/133/1331826.jpeg"

def _load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"cover_media": DEFAULT_ANIME_BANNER}, f)
        return {"cover_media": DEFAULT_ANIME_BANNER}
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            if "pokeapi" in data.get("cover_media", "").lower():
                data["cover_media"] = DEFAULT_ANIME_BANNER
            return data
    except Exception:
        return {"cover_media": DEFAULT_ANIME_BANNER}

def get_cover_media(category: str = "start") -> str:
    settings = _load_settings()
    default_val = settings.get("cover_media", DEFAULT_ANIME_BANNER)
    return settings.get(f"{category}_cover", default_val)

def set_cover_media(category: str, media_url_or_id: str):
    settings = _load_settings()
    settings[f"{category}_cover"] = media_url_or_id
    if category == "start":
        settings["cover_media"] = media_url_or_id
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)
