import html
import config

RARITY_CACHE = {}

FALLBACK_EMOJIS = {
    "amv": "🎬",
    "video": "📹",
    "special": "⭐",
    "exclusive": "💎",
    "celestial": "🌌",
    "cosmic": "🪐"
}

def get_rarity_emoji(rarity: str) -> str:
    if not rarity:
        return "⚪"
    r_str = rarity.strip()
    r_lower = r_str.lower()
    r_title = r_str.title()
    
    if r_title in RARITY_CACHE:
        return RARITY_CACHE[r_title].get("emoji", "⚪")
    if r_title in config.RARITY_CONFIG:
        return config.RARITY_CONFIG[r_title].get("emoji", "⚪")
        
    for k, v in config.RARITY_CONFIG.items():
        if k.lower() == r_lower:
            return v.get("emoji", "⚪")
            
    for k, v in RARITY_CACHE.items():
        if k.lower() == r_lower:
            return v.get("emoji", "⚪")

    if r_lower in FALLBACK_EMOJIS:
        return FALLBACK_EMOJIS[r_lower]
            
    return "✨"

def format_blockquote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"

def get_progress_bar(current: int, total: int, length: int = 10) -> str:
    if total <= 0:
        return "░" * length
    percent = min(1.0, max(0.0, current / total))
    filled_length = int(length * percent)
    bar = "█" * filled_length + "░" * (length - filled_length)
    return f"`[{bar}]` {int(percent * 100)}%"

def format_coins(coins: int) -> str:
    if coins >= 1_000_000:
        return f"{coins / 1_000_000:.1f}M"
    elif coins >= 1_000:
        return f"{coins / 1_000:.1f}k"
    return str(coins)

def escape_html(text: str) -> str:
    if not text:
        return ""
    return html.escape(str(text))
