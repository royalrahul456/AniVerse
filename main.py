import asyncio
import json
import logging
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from sqlalchemy import select

import config
from database.database import init_db, AsyncSessionLocal
from database.models import Character, RarityType, UserDailyLimit, BotAdmin
from handlers import start, profile, catch, shop, games, trade, admin, xo, inline_query, redeem, auction
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def seed_characters():
    async with AsyncSessionLocal() as session:
        stmt = select(Character)
        res = await session.execute(stmt)
        existing = res.scalars().all()
        if not existing and os.path.exists("data/characters.json"):
            logger.info("Seeding initial starter characters into database...")
            with open("data/characters.json", "r") as f:
                data = json.load(f)
            for item in data:
                char = Character(
                    name=item["name"],
                    anime=item["anime"],
                    rarity=item["rarity"],
                    image_url=item.get("image_url")
                )
                session.add(char)
            await session.commit()
            logger.info(f"Successfully seeded {len(data)} characters!")

class DbSessionMiddleware:
    async def __call__(self, handler, event, data):
        from aiogram.types import Message, CallbackQuery
        if isinstance(event, Message):
            logging.getLogger(__name__).info(f"Incoming Message: '{event.text}' from chat {event.chat.id} type {event.chat.type}")
        elif isinstance(event, CallbackQuery):
            logging.getLogger(__name__).info(f"Incoming CallbackQuery: '{event.data}'")
        async with AsyncSessionLocal() as session:
            data["db"] = session
            return await handler(event, data)

class JoinCheckMiddleware:
    async def __call__(self, handler, event, data):
        from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        user_id = None
        if isinstance(event, Message):
            # Bypass join check for /start command to let users see welcome/start menu
            if event.text and event.text.strip().startswith("/start"):
                return await handler(event, data)
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            # Bypass join check if the callback data belongs to home command back actions
            if event.data and event.data == "dm_home":
                return await handler(event, data)
            user_id = event.from_user.id if event.from_user else None

        if user_id:
            # Bypass checks for bot admin/owners
            if config.ADMIN_IDS and user_id in config.ADMIN_IDS:
                return await handler(event, data)

            bot = data["bot"]
            is_joined = False
            try:
                member = await bot.get_chat_member(chat_id="@AniVerseUnion", user_id=user_id)
                if member.status in ["member", "administrator", "creator"]:
                    is_joined = True
            except Exception as e:
                err_msg = str(e).lower()
                if "user not found" in err_msg:
                    is_joined = False
                else:
                    # Let pass if bot is not in group chat or public username is not setup yet
                    is_joined = True

            if not is_joined:
                builder = InlineKeyboardBuilder()
                builder.row(InlineKeyboardButton(text="💬 Join Official GC", url="https://t.me/AniVerseUnion"))
                
                caption = (
                    "⚠️ <b>Access Denied!</b>\n\n"
                    "You must join our official group chat to use this bot:\n"
                    "👉 https://t.me/AniVerseUnion"
                )
                
                if isinstance(event, Message):
                    await event.reply(caption, reply_markup=builder.as_markup(), parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    try:
                        await event.message.reply(caption, reply_markup=builder.as_markup(), parse_mode="HTML")
                    except Exception:
                        pass
                    try:
                        await event.answer("⚠️ You must join our official GC first!", show_alert=True)
                    except Exception:
                        pass
                return

        return await handler(event, data)

async def start_health_server():
    """Lightweight HTTP server for Render health checks — keeps the service alive."""
    async def health(request):
        return web.Response(text="AniVerse Bot is running! ✅")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check server running on port {port}")

async def main():
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.warning("BOT_TOKEN is not configured in environment variables or config.py!")

    # Start health check server (required for Render free tier)
    await start_health_server()

    await init_db()
    await seed_characters()

    # Pre-populate custom rarity cache and seed defaults
    try:
        from database.models import RarityType
        from utils.formatters import RARITY_CACHE
        async with AsyncSessionLocal() as session:
            for name, config_info in config.RARITY_CONFIG.items():
                stmt = select(RarityType).where(RarityType.name.ilike(name))
                res = await session.execute(stmt)
                existing = res.scalar_one_or_none()
                if not existing:
                    new_r = RarityType(
                        name=name.title(),
                        emoji=config_info.get("emoji", "⚪"),
                        weight=config_info.get("weight", 10),
                        color=config_info.get("color", "Gray"),
                        spawn_enabled=True
                    )
                    session.add(new_r)
            await session.commit()

            res = await session.execute(select(RarityType))
            rarities = res.scalars().all()
            for r in rarities:
                RARITY_CACHE[r.name.title()] = {"emoji": r.emoji}
        logger.info(f"Loaded {len(rarities)} custom rarities into cache.")
    except Exception as e:
        logger.error(f"Failed to pre-populate custom rarities: {e}")

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Set bot commands in Telegram menu
    commands = [
        BotCommand(command="start", description="Welcome & Main Menu Hub"),
        BotCommand(command="help", description="Guide & Help Center"),
        BotCommand(command="profile", description="View trainer profile card"),
        BotCommand(command="harem", description="View your character collection"),
        BotCommand(command="leaderboard", description="Global trainer rankings"),
        BotCommand(command="check", description="Check character details & owners"),
        BotCommand(command="cid", description="View character variants by name"),
        BotCommand(command="search", description="Search character database"),
        BotCommand(command="anime", description="Filter characters by anime title"),
        BotCommand(command="claim", description="Claim a free daily character"),
        BotCommand(command="games", description="Open Games Center"),
        BotCommand(command="mines", description="Start a new 5x5 Mines game"),
        BotCommand(command="endmines", description="Force-quit active Mines game"),
        BotCommand(command="spin", description="Spin the Lucky Wheel (daily 3x)"),
        BotCommand(command="coinflip", description="Play coinflip bet (daily 2x)"),
        BotCommand(command="dice", description="Play animated dice roll (daily 2x)"),
        BotCommand(command="dart", description="Play animated dart throw (daily 2x)"),
        BotCommand(command="trivia", description="Play anime quiz trivia"),
        BotCommand(command="scramble", description="Play word scramble puzzle"),
        BotCommand(command="spawnchance", description="View wild character spawn chances"),
        BotCommand(command="editspawnchance", description="Edit spawn weights (Admin only)"),
        BotCommand(command="pay", description="Pay coins to another trainer"),
        BotCommand(command="balance", description="Check your coin balance"),
        BotCommand(command="chk", description="Quick balance check"),
        BotCommand(command="gift", description="Gift a character to another trainer"),
        BotCommand(command="editchar", description="Edit character details (Admin only)"),
        BotCommand(command="promote", description="Promote user to admin (Owner only)"),
        BotCommand(command="demote", description="Demote user from admin (Owner only)"),
        BotCommand(command="adminlist", description="List bot admin staff"),
        BotCommand(command="delrarity", description="Delete custom rarity tier (Owner only)"),
        BotCommand(command="editrarityemoji", description="Edit custom rarity emoji (Owner only)"),
        BotCommand(command="shop", description="Buy new profile themes")
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Bot commands registered successfully in Telegram menu.")
    except Exception as e:
        logger.error(f"Failed to register bot commands: {e}")
    db_middleware = DbSessionMiddleware()
    join_middleware = JoinCheckMiddleware()
    
    dp.message.middleware(db_middleware)
    dp.message.middleware(join_middleware)    
    dp.callback_query.middleware(db_middleware)
    dp.callback_query.middleware(join_middleware)

    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(profile.router)
    dp.include_router(catch.router)
    dp.include_router(shop.router)
    dp.include_router(games.router)
    dp.include_router(trade.router)
    dp.include_router(xo.router)
    dp.include_router(inline_query.router)
    dp.include_router(redeem.router)
    dp.include_router(auction.router)

    async def auction_background_loop():
        from handlers.auction import process_auctions_tick
        while True:
            try:
                await process_auctions_tick(bot)
            except Exception as e:
                logger.error(f"Error in auction tick: {e}")
            await asyncio.sleep(5)

    asyncio.create_task(auction_background_loop())

    logger.info("AniVerse Anime Collection Bot started successfully!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
