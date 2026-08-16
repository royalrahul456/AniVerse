import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Support Railway PostgreSQL (postgres://) and local SQLite
_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///aniverse.db")
# Railway gives postgres:// but asyncpg needs postgresql+asyncpg://
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgresql://") and "+asyncpg" not in _db_url:
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
DATABASE_URL = _db_url


# Admin IDs (Telegram User IDs)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "6593485710").split(",") if x.strip().isdigit()]

# Gameplay Rewards Configuration
DAILY_REWARD_MIN = 262

# Currency Configuration
CURRENCY_NAME = "Gold"
CURRENCY_EMOJI = "🪙"
# Official Group Chat ID (Daily claim restriction)
OFFICIAL_CHAT_ID = int(os.getenv("OFFICIAL_CHAT_ID", "-1003616974453"))
DAILY_REWARD_MAX = 577
CATCH_REWARD_MIN = 84
CATCH_REWARD_MAX = 136

SPIN_REWARDS = [105, 157, 210, 262, 367, 577]

TRIVIA_REWARD = 157
GUESS_REWARD = 210
DICE_WIN_MULTIPLIER = 2

# Default Rarity Emojis & Colors/Weights
RARITY_CONFIG = {
    "Common": {"emoji": "⚪", "weight": 50, "color": "Gray"},
    "Rare": {"emoji": "🔵", "weight": 30, "color": "Blue"},
    "Epic": {"emoji": "🟣", "weight": 14, "color": "Purple"},
    "Legendary": {"emoji": "🟡", "weight": 5, "color": "Gold"},
    "Mythical": {"emoji": "🔴", "weight": 1, "color": "Red"}
}

# Telegram Mini App URL (Frontend hosted link)
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://royalrahul456.github.io/AniVerse/web/")
