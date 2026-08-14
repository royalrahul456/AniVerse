import asyncio
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import config

async def test_send():
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        # User ID 6593485710
        await bot.send_message(6593485710, 'Test custom emoji: <tg-emoji emoji_id="5222108309795908493">✨</tg-emoji>')
        print("Successfully sent message with custom emoji!")
    except Exception as e:
        print(f"Failed to send message: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_send())
