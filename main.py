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

# In-memory cache for join status checks to avoid hitting Telegram API rate limits and causing lag
_join_check_cache = {}

class JoinCheckMiddleware:
    async def __call__(self, handler, event, data):
        from aiogram.types import Message, CallbackQuery
        import time
        
        user_id = None
        if isinstance(event, Message):
            if event.text and event.text.strip().startswith("/start"):
                return await handler(event, data)
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            if event.data and event.data == "dm_home":
                return await handler(event, data)
            user_id = event.from_user.id if event.from_user else None

        if user_id:
            if config.ADMIN_IDS and user_id in config.ADMIN_IDS:
                return await handler(event, data)

            current_time = time.time()
            if user_id in _join_check_cache:
                cached_time, cached_joined = _join_check_cache[user_id]
                expiry = 300 if cached_joined else 10
                if current_time - cached_time < expiry:
                    if cached_joined:
                        return await handler(event, data)
                    else:
                        return await self._send_denied_response(event)

            try:
                member = await event.bot.get_chat_member(config.OFFICIAL_CHANNEL_ID, user_id)
                is_joined = member.status in ["member", "administrator", "creator"]
                _join_check_cache[user_id] = (current_time, is_joined)
                if is_joined:
                    return await handler(event, data)
            except Exception:
                _join_check_cache[user_id] = (current_time, True)
                return await handler(event, data)

            return await self._send_denied_response(event)
        return await handler(event, data)

    async def _send_denied_response(self, event):
        from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        text = (
            "🚨 <b>Access Denied!</b>\n\n"
            "You must join our **Official Update Channel** to use this bot and play games!"
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📢 Join Updates Channel", url=config.OFFICIAL_CHANNEL_LINK))
        
        if isinstance(event, CallbackQuery):
            builder.row(InlineKeyboardButton(text="🔄 Try Again", callback_data="dm_home"))
            try:
                await event.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception:
                pass
            try:
                await event.answer("⚠️ Please join the channel first!", show_alert=True)
            except Exception:
                pass
        else:
            try:
                await event.reply(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception:
                pass
        return None

# Combined Web App server running on Render's single dynamic port
async def start_health_server():
    app = web.Application()
    
    # 1. Render Health Check Endpoint
    async def health_check(request):
        return web.Response(text="OK", status=200)
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    
    # 2. REST API Endpoints for Telegram Mini App
    from handlers.api import get_user_profile_api, post_game_reward_api
    app.router.add_get("/api/profile/{user_id}", get_user_profile_api)
    app.router.add_post("/api/games/reward", post_game_reward_api)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Bind to Render's single dynamic PORT (falls back to 8080 locally)
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Consolidated API & Health Server running on port {port}...")

async def main():
    await init_db()
    await seed_characters()
    
    # Pre-populate custom rarities
    from utils.formatters import RARITY_CACHE
    try:
        async with AsyncSessionLocal() as session:
            # Seed default rarities if none exist
            rarity_check = await session.execute(select(RarityType))
            if not rarity_check.scalars().all():
                logger.info("Initializing default rarities in database...")
                defaults = [
                    ("Common", "⚪", 70, "Gray", True, True, 70),
                    ("Rare", "🔵", 18, "Blue", True, True, 18),
                    ("Epic", "🟣", 9, "Purple", True, True, 9),
                    ("Legendary", "🟡", 3, "Gold", True, True, 3)
                ]
                for name, emoji, weight, color, spawn, claim, c_weight in defaults:
                    new_r = RarityType(
                        name=name, emoji=emoji, weight=weight, color=color,
                        spawn_enabled=spawn, claim_enabled=claim, claim_weight=c_weight
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
        BotCommand(command="search", description="View character variants by name"),
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
        BotCommand(command="nameguess", description="Start a manual character guessing game"),
        BotCommand(command="togglenameguess", description="Toggle continuous automatic guessing loop"),
        BotCommand(command="addtoclaim", description="Add a rarity to claim pool (Admin only)"),
        BotCommand(command="removefromclaim", description="Remove a rarity from claim pool (Admin only)"),
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

    # background tasks
    async def auction_background_loop():
        from handlers.auction import process_auctions_tick
        while True:
            try:
                await process_auctions_tick(bot)
            except Exception as e:
                logger.error(f"Error in auction tick: {e}")
            await asyncio.sleep(5)
    asyncio.create_task(auction_background_loop())

    # Start consolidated Health & API Web Server
    await start_health_server()

    logger.info("AniVerse Anime Collection Bot started successfully!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
