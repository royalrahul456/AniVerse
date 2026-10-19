import asyncio
import logging
from sqlalchemy import select
from database.database import init_db, AsyncSessionLocal
from database.models import BotEmoji
from utils.emojis import PREMIUM_EMOJI_IDS, DEFAULT_EMOJIS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_emojis():
    await init_db()
    async with AsyncSessionLocal() as session:
        count = 0
        for key, emoji_id in PREMIUM_EMOJI_IDS.items():
            # If the key is a string key or an emoji
            fallback = DEFAULT_EMOJIS.get(key, key)
            tag = f'<tg-emoji emoji_id="{emoji_id}">{fallback}</tg-emoji>'
            
            stmt = select(BotEmoji).where(BotEmoji.key == key)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            
            if existing:
                existing.emoji = tag
            else:
                session.add(BotEmoji(key=key, emoji=tag))
            count += 1
            
        await session.commit()
        logger.info(f"Successfully synced {count} premium emojis into the bot_emojis table!")

if __name__ == "__main__":
    asyncio.run(seed_emojis())
