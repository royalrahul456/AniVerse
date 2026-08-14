from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.models import BotEmoji

# In-memory cache for fast lookups
EMOJI_CACHE = {}

DEFAULT_EMOJIS = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "coin": "💰",
    "crown": "👑",
    "party": "🎉",
    "id": "🆔",
    "gem": "💎",
    "back": "🔙",
    "sparkle": "✨",
    "pointer": "👉",
    "circle": "⭕",
    "energy": "⚡",
    "tv": "📺",
    "bomb": "💣",
    "gift": "🎁",
    "trophy": "🏆",
    "target": "🎯",
    "no_entry": "⛔",
    "user": "👤"
}

async def load_emojis(db: AsyncSession):
    """Load custom emojis from database into cache."""
    stmt = select(BotEmoji)
    result = await db.execute(stmt)
    emojis = result.scalars().all()
    for em in emojis:
        EMOJI_CACHE[em.key] = em.emoji

def get_emoji(key: str) -> str:
    """Get the default unicode emoji for a given key.
    Note: Custom premium emojis via HTML tags are disabled because Telegram API 
    forbids bots from using them in text messages unless the bot has a purchased 
    Fragment collectible username.
    """
    return DEFAULT_EMOJIS.get(key, "✨")
