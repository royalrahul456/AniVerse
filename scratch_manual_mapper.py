import asyncio
import os
from aiogram import Bot
import config
from utils.emojis import DEFAULT_EMOJIS
from database.database import init_db, AsyncSessionLocal
from database.models import BotEmoji
from sqlalchemy.future import select

async def run_manual_mapper():
    await init_db()
    bot = Bot(token=config.BOT_TOKEN)
    try:
        pack_name = "RestrictedEmoji"
        print(f"Fetching pack: {pack_name}")
        pack = await bot.get_sticker_set(pack_name)
        print(f"Pack found! Type: {pack.sticker_type}")
        
        emoji_to_key = {v: k for k, v in DEFAULT_EMOJIS.items()}
        
        mapped = 0
        async with AsyncSessionLocal() as db:
            for sticker in pack.stickers:
                if sticker.emoji in emoji_to_key and sticker.custom_emoji_id:
                    key = emoji_to_key[sticker.emoji]
                    tag = f'<tg-emoji emoji_id="{sticker.custom_emoji_id}">{sticker.emoji}</tg-emoji>'
                    
                    stmt = select(BotEmoji).where(BotEmoji.key == key)
                    res = await db.execute(stmt)
                    existing = res.scalar_one_or_none()
                    
                    if existing:
                        existing.emoji = tag
                    else:
                        db.add(BotEmoji(key=key, emoji=tag))
                    
                    mapped += 1
                    del emoji_to_key[sticker.emoji]
            await db.commit()
            
        print(f"Mapped {mapped} emojis to the database successfully!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(run_manual_mapper())
