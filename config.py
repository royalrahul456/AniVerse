import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Support Railway PostgreSQL (postgres://) and local SQLite
_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///aniverse.db")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgresql://") and "+asyncpg" not in _db_url:
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
DATABASE_URL = _db_url

# Master Administrative Hierarchy (Telegram User IDs)
OWNER_IDS = [int(x) for x in os.getenv("OWNER_IDS", "6593485710").split(",") if x.strip().isdigit()]
COOWNER_IDS = [int(x) for x in os.getenv("COOWNER_IDS", "1412402578").split(",") if x.strip().isdigit()]

# Full Master Admin Access (Owners + Co-Owners + Custom Admins)
_admin_env = os.getenv("ADMIN_IDS", "")
if _admin_env:
    ADMIN_IDS = [int(x) for x in _admin_env.split(",") if x.strip().isdigit()]
    for _uid in OWNER_IDS + COOWNER_IDS:
        if _uid not in ADMIN_IDS:
            ADMIN_IDS.append(_uid)
else:
    ADMIN_IDS = list(dict.fromkeys(OWNER_IDS + COOWNER_IDS))

# Enable Telegram Custom Premium Emojis
ENABLE_PREMIUM_EMOJIS = os.getenv("ENABLE_PREMIUM_EMOJIS", "true").lower() in ("true", "1", "yes")

# Pre-configured Bot Administrative Staff
DEFAULT_BOT_ADMINS = {
    1412402578: {"username": "Xcaliber_s84", "first_name": "Xcaliber", "role": "coowner"},
    8365981430: {"username": "Sylveon_sy", "first_name": "Sylveon", "role": "snradmin"}
}

# Official Channels & Groups
def _parse_channel_id(val, default):
    val = str(val).strip()
    if not val:
        return default
    if val.startswith("@"):
        return val
    try:
        return int(val)
    except ValueError:
        return val

OFFICIAL_CHAT_ID = int(os.getenv("OFFICIAL_CHAT_ID", "-1003616974453"))
OFFICIAL_CHANNEL_ID = _parse_channel_id(os.getenv("OFFICIAL_CHANNEL_ID", "@aniverseupdate"), "@aniverseupdate")
OFFICIAL_CHANNEL_LINK = os.getenv("OFFICIAL_CHANNEL_LINK", "https://t.me/aniverseupdate")

# Currency Configuration
CURRENCY_NAME = "Gold"
CURRENCY_EMOJI = "🪙"

# Periodic Rewards Configuration
DAILY_REWARD_MIN = 288
DAILY_REWARD_MAX = 635

WEEKLY_REWARD_MIN = 500
WEEKLY_REWARD_MAX = 1000  # Cap: max 1000

MONTHLY_REWARD_MIN = 2500
MONTHLY_REWARD_MAX = 5000  # Cap: max 5000

YEARLY_REWARD_MIN = 25000
YEARLY_REWARD_MAX = 50000  # Cap: max 50000

CATCH_REWARD_MIN = 92
CATCH_REWARD_MAX = 150

SPIN_REWARDS = [116, 173, 231, 288, 404, 635]

TRIVIA_REWARD = 173
GUESS_REWARD = 231
DICE_WIN_MULTIPLIER = 2

# Default Rarity Emojis & Colors/Weights
RARITY_CONFIG = {
    "Common": {"emoji": "⚪", "weight": 50, "color": "Gray"},
    "Rare": {"emoji": "🔵", "weight": 30, "color": "Blue"},
    "Epic": {"emoji": "🟣", "weight": 14, "color": "Purple"},
    "Legendary": {"emoji": "🟡", "weight": 5, "color": "Gold"},
    "Mythical": {"emoji": "🔴", "weight": 1, "color": "Red"}
}

# Telegram Mini App URL
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://royalrahul456.github.io/AniVerse/web/")
