import logging
import html
import aiohttp
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import User

logger = logging.getLogger(__name__)
router = Router()

ACTION_CONFIG = {
    "hug": {
        "emoji": "🫂",
        "verb": "hugs",
        "suffix": "! 💖",
        "self_msg": "gives themselves a warm comforting hug! 💖",
        "help_text": "Reply to someone's message or use <code>/hug @username</code> to give them a warm hug!"
    },
    "kiss": {
        "emoji": "💋",
        "verb": "kisses",
        "suffix": "! 💕",
        "self_msg": "blows a sweet kiss into the air! ✨",
        "help_text": "Reply to someone's message or use <code>/kiss @username</code>!"
    },
    "pat": {
        "emoji": "🐱",
        "verb": "gently pats",
        "suffix": " on the head! ✨",
        "self_msg": "pats their own head gently! 🌸",
        "help_text": "Reply to someone's message or use <code>/pat @username</code>!"
    },
    "slap": {
        "emoji": "👋",
        "verb": "slaps",
        "suffix": " right across the face! 💢",
        "self_msg": "slaps their own forehead! 🤦",
        "help_text": "Reply to someone's message or use <code>/slap @username</code>!"
    },
    "cuddle": {
        "emoji": "🤍",
        "verb": "cuddles with",
        "suffix": " warmly! 🥰",
        "self_msg": "curls up and cuddles with a soft plushie! 🧸",
        "help_text": "Reply to someone's message or use <code>/cuddle @username</code>!"
    },
    "poke": {
        "emoji": "👉",
        "verb": "pokes",
        "suffix": " playfully! 🤭",
        "self_msg": "pokes their own cheek curiously! 🤔",
        "help_text": "Reply to someone's message or use <code>/poke @username</code>!"
    },
    "tickle": {
        "emoji": "🤭",
        "verb": "tickles",
        "suffix": " until they can't stop laughing! 😂",
        "self_msg": "starts laughing uncontrollably! 🤣",
        "help_text": "Reply to someone's message or use <code>/tickle @username</code>!"
    },
    "kill": {
        "emoji": "⚔️",
        "verb": "defeats",
        "suffix": " in an epic anime duel! ⚡",
        "self_msg": "accidentally tripped over their own cape! 💀",
        "help_text": "Reply to someone's message or use <code>/kill @username</code>!"
    }
}

async def fetch_action_gif(action: str) -> tuple[str | None, str | None]:
    """Fetch an anime GIF URL and optional anime title from Gifukai API with waifu.pics fallback."""
    headers = {"User-Agent": "AniVerseBot/1.0", "Accept": "application/json"}
    timeout = aiohttp.ClientTimeout(total=5)

    # 1. Primary API: Gifukai
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"https://api.gifukai.com/v1/{action}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    url = data.get("url")
                    anime = data.get("anime")
                    if url and isinstance(url, str) and url.startswith("https://"):
                        return url, anime if isinstance(anime, str) and anime.strip() else None
    except Exception as exc:
        logger.debug(f"Gifukai API error for {action}: {exc}")

    # 2. Fallback API: Waifu.pics
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"https://api.waifu.pics/sfw/{action}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    url = data.get("url")
                    if url and isinstance(url, str) and url.startswith("https://"):
                        return url, None
    except Exception as exc:
        logger.debug(f"Waifu.pics fallback error for {action}: {exc}")

    return None, None

async def resolve_target(message: Message, db: AsyncSession) -> tuple[int, str] | None:
    """Resolves the target user via reply, entity mention, @username, or numeric ID."""
    # 1. Direct message reply
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        name = u.first_name or u.username or "Trainer"
        return u.id, name

    # 2. Text mention entities (e.g. users without username mentioned inline)
    entities = list(message.entities or []) + list(message.caption_entities or [])
    for ent in entities:
        if ent.type == "text_mention" and ent.user:
            u = ent.user
            name = u.first_name or u.username or "Trainer"
            return u.id, name

    # 3. Argument: @username or numeric user_id
    parts = (message.text or message.caption or "").strip().split()
    if len(parts) > 1:
        arg = parts[1].strip()
        if arg.startswith("@"):
            clean_name = arg.lstrip("@").strip()
            stmt = select(User).where(func.lower(User.username) == clean_name.lower())
            res = await db.execute(stmt)
            db_user = res.scalar_one_or_none()
            if db_user:
                return db_user.user_id, db_user.first_name or clean_name
            return None
        elif arg.isdigit():
            target_id = int(arg)
            stmt = select(User).where(User.user_id == target_id)
            res = await db.execute(stmt)
            db_user = res.scalar_one_or_none()
            if db_user:
                return db_user.user_id, db_user.first_name or f"Trainer {target_id}"
            return target_id, f"Trainer {target_id}"

    return None

async def handle_social_action(message: Message, action: str, db: AsyncSession):
    if not message.from_user:
        return
    cfg = ACTION_CONFIG.get(action, ACTION_CONFIG["hug"])
    actor = message.from_user
    actor_name = html.escape(actor.first_name or actor.username or "Trainer")
    actor_link = f'<a href="tg://user?id={actor.id}">{actor_name}</a>'

    target = await resolve_target(message, db)
    if not target:
        await message.reply(
            f"{cfg['emoji']} <b>Anime {action.capitalize()}</b>\n\n"
            f"{cfg['help_text']}\n\n"
            f"<i>💡 You can also use .{action}, !{action}, or ani {action}!</i>",
            parse_mode="HTML"
        )
        return

    target_id, target_name_raw = target
    target_name = html.escape(target_name_raw)
    target_link = f'<a href="tg://user?id={target_id}">{target_name}</a>'

    if target_id == actor.id:
        caption = f"{cfg['emoji']} <b>{actor_link}</b> {cfg['self_msg']}"
    else:
        caption = f"{cfg['emoji']} <b>{actor_link}</b> {cfg['verb']} <b>{target_link}</b>{cfg['suffix']}"

    gif_url, anime_name = await fetch_action_gif(action)
    if anime_name:
        caption += f"\n🎬 <i>Anime: {html.escape(anime_name)}</i>"

    if gif_url:
        try:
            await message.reply_animation(animation=gif_url, caption=caption, parse_mode="HTML")
            return
        except Exception as exc:
            logger.warning(f"Could not send animation for {action}: {exc}")

    # Fallback to formatted text reply
    await message.reply(caption, parse_mode="HTML")

@router.message(Command("hug"))
async def cmd_hug(message: Message, db: AsyncSession):
    await handle_social_action(message, "hug", db)

@router.message(Command("kiss"))
async def cmd_kiss(message: Message, db: AsyncSession):
    await handle_social_action(message, "kiss", db)

@router.message(Command("pat"))
async def cmd_pat(message: Message, db: AsyncSession):
    await handle_social_action(message, "pat", db)

@router.message(Command("slap"))
async def cmd_slap(message: Message, db: AsyncSession):
    await handle_social_action(message, "slap", db)

@router.message(Command("cuddle"))
async def cmd_cuddle(message: Message, db: AsyncSession):
    await handle_social_action(message, "cuddle", db)

@router.message(Command("poke"))
async def cmd_poke(message: Message, db: AsyncSession):
    await handle_social_action(message, "poke", db)

@router.message(Command("tickle"))
async def cmd_tickle(message: Message, db: AsyncSession):
    await handle_social_action(message, "tickle", db)

@router.message(Command("kill"))
async def cmd_kill(message: Message, db: AsyncSession):
    await handle_social_action(message, "kill", db)
