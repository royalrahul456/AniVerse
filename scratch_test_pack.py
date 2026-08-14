import asyncio
from aiogram import Bot
import config
from utils.emojis import DEFAULT_EMOJIS

async def test_pack():
    bot = Bot(token=config.BOT_TOKEN)
    try:
        pack_name = "vector_icons_by_fStikBot"
        print(f"Fetching pack: {pack_name}")
        pack = await bot.get_sticker_set(pack_name)
        print(f"Pack found! Type: {pack.sticker_type}")
        print(f"Total stickers: {len(pack.stickers)}")
        
        emoji_to_key = {v: k for k, v in DEFAULT_EMOJIS.items()}
        print(f"Looking for emojis: {list(emoji_to_key.keys())}")
        
        mapped = 0
        for sticker in pack.stickers:
            if sticker.emoji in emoji_to_key and sticker.custom_emoji_id:
                mapped += 1
                del emoji_to_key[sticker.emoji]
                
        print(f"Mapped {mapped} emojis.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_pack())
