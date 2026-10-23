import logging
import html
import random
import aiohttp
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import User
from utils.formatters import format_blockquote, escape_html
from utils.emojis import get_emoji

logger = logging.getLogger(__name__)
router = Router()

ACTION_CONFIG = {
    "hug": {
        "emoji": "🫂",
        "title": "ANIME HUG",
        "actions": [
            "warmly wraps their arms around",
            "runs up and gives a giant, cozy bear hug to",
            "pulls into a tight, affectionate anime embrace with",
            "gently and lovingly hugs",
        ],
        "flavor": "Wholesome levels: 100% Maximum ✨",
        "self_msg": "wraps their arms around themselves with a warm, comforting self-hug! 💖",
        "self_flavor": "Self-Love & Care: 100% Wholesome ✨",
        "btn_text": "🫂 Hug Back",
        "help_desc": "Share warm affection and cozy hugs with fellow trainers!"
    },
    "kiss": {
        "emoji": "💋",
        "title": "ANIME KISS",
        "actions": [
            "pulls close and gives a sweet, passionate kiss to",
            "plants a gentle, loving anime kiss on",
            "blushes brightly and softly kisses",
            "leans in and shares a tender romantic kiss with",
        ],
        "flavor": "Doki-Doki Heartbeat: Over 9,000! 💕",
        "self_msg": "blows a magical, sparkling kiss into the air! ✨",
        "self_flavor": "Sending pure love across the entire anime universe! 💖",
        "btn_text": "💋 Kiss Back",
        "help_desc": "Send sweet, romantic anime kisses to fellow trainers!"
    },
    "pat": {
        "emoji": "🐱",
        "title": "ANIME HEADPAT",
        "actions": [
            "reaches out and gently pats the head of",
            "gives soft, soothing headpats to",
            "smiles warmly and pats",
            "gives adorable, rhythmic headpats to",
        ],
        "flavor": "Comfort rating: 10/10 Pure Serotonin 🌸",
        "self_msg": "pats their own head and says 'I did great today!' 🌸",
        "self_flavor": "Trainer Pride: Maximum ✨",
        "btn_text": "🐱 Pat Back",
        "help_desc": "Give soft, soothing anime headpats!"
    },
    "slap": {
        "emoji": "👋",
        "title": "ANIME SLAP",
        "actions": [
            "delivers a stinging anime slap right across the cheek of",
            "yells 'B-Baka!' and dramatically slaps",
            "spins around and lands an explosive anime slap on",
        ],
        "flavor": "Anime Impact Damage: 9,999 💢",
        "self_msg": "facepalms and slaps their own forehead in complete disbelief! 🤦",
        "self_flavor": "Facepalm level: Maximum 🤦",
        "btn_text": "👋 Slap Back",
        "help_desc": "Deliver dramatic, classic tsundere anime slaps!"
    },
    "cuddle": {
        "emoji": "🤍",
        "title": "ANIME CUDDLE",
        "actions": [
            "snuggles up close for a cozy, heartwarming cuddle with",
            "pulls into a soft, snuggly embrace with",
            "curls up peacefully and cuddles beside",
        ],
        "flavor": "Cozy comfort rating: Infinite Warmth 🥰",
        "self_msg": "curls up tightly inside a warm blanket with a plushie! 🧸",
        "self_flavor": "Cozy mode: Fully Activated ☕",
        "btn_text": "🤍 Cuddle Back",
        "help_desc": "Snuggle up close with fellow trainers!"
    },
    "poke": {
        "emoji": "👉",
        "title": "ANIME POKE",
        "actions": [
            "playfully pokes the squishy cheek of",
            "repeatedly pokes",
            "sneaks up behind and pokes the shoulder of",
        ],
        "flavor": "*Poke poke!* Attention successfully demanded! 🤭",
        "self_msg": "pokes their own cheek curiously wondering why they did that! 🤔",
        "self_flavor": "Curiosity: 100% ❓",
        "btn_text": "👉 Poke Back",
        "help_desc": "Playfully poke someone to get their attention!"
    },
    "tickle": {
        "emoji": "🤭",
        "title": "ANIME TICKLE",
        "actions": [
            "launches an unstoppable tickle assault on",
            "tickles the ribs of",
            "sneaks up with tickle fingers targeting",
        ],
        "flavor": "Laughter gauge: Overloaded! 😂",
        "self_msg": "tries to tickle themselves and realizes it doesn't work! 🤣",
        "self_flavor": "Science test: Complete 🧠",
        "btn_text": "🤭 Tickle Back",
        "help_desc": "Start an unstoppable anime tickle war!"
    },
    "kill": {
        "emoji": "⚔️",
        "title": "ANIME DUEL DEFEAT",
        "actions": [
            "unleashes an ultimate finishing move and obliterates",
            "draws their legendary anime blade and slices down",
            "lands an earth-shattering critical strike against",
        ],
        "flavor": "FATALITY! Critical Hit: 999,999 DMG ⚡",
        "self_msg": "tripped over their own cape and took 9,999 self-damage! 💀",
        "self_flavor": "Respawning in 3... 2... 1... 🪦",
        "btn_text": "⚔️ Counter Strike",
        "help_desc": "Defeat someone in an epic anime battle duel!"
    }
}

async def fetch_action_gif(action: str) -> tuple[str | None, str | None]:
    """Fetch an anime GIF URL and optional anime title from Gifukai API with waifu.pics fallback."""
    headers = {"User-Agent": "AniVerseBot/1.0", "Accept": "application/json"}
    timeout = aiohttp.ClientTimeout(total=4)

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

    # 2. Text mention entities (users without usernames mentioned inline)
    entities = list(message.entities or []) + list(message.caption_entities or [])
    for ent in entities:
        if ent.type == "text_mention" and ent.user:
            u = ent.user
            name = u.first_name or u.username or "Trainer"
            return u.id, name

    # 3. Text arguments (@username or numeric user ID)
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

def build_social_card(actor_id: int, actor_name_raw: str, target_id: int, target_name_raw: str, action: str, anime_name: str | None = None) -> str:
    cfg = ACTION_CONFIG[action]
    actor_name = escape_html(actor_name_raw)
    target_name = escape_html(target_name_raw)
    actor_link = f'<a href="tg://user?id={actor_id}">{actor_name}</a>'
    target_link = f'<a href="tg://user?id={target_id}">{target_name}</a>'

    header = f"✨ <b>ANIVERSE EMOTE</b> • <b>{cfg['title']}</b> {cfg['emoji']}\n\n"

    if actor_id == target_id:
        body = (
            f"🌸 <b>{actor_link}</b> {cfg['self_msg']}\n\n"
            f"💌 <i>{cfg['self_flavor']}</i>"
        )
    else:
        chosen_action = random.choice(cfg["actions"])
        body = f"🌸 <b>{actor_link}</b> {chosen_action} <b>{target_link}</b>!\n"
        if anime_name:
            body += f"\n🎬 <b>Anime:</b> <i>{escape_html(anime_name)}</i>"
        body += f"\n💌 <i>{cfg['flavor']}</i>"

    return header + format_blockquote(body)

def build_action_keyboard(action: str, actor_id: int, target_id: int) -> InlineKeyboardBuilder | None:
    if actor_id == target_id:
        return None
    cfg = ACTION_CONFIG[action]
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=cfg["btn_text"], callback_data=f"soc_ret:{action}:{actor_id}:{target_id}"),
        InlineKeyboardButton(text="🎲 Random", callback_data=f"soc_rnd:{actor_id}:{target_id}")
    )
    return builder

async def handle_social_action(message: Message, action: str, db: AsyncSession):
    if not message.from_user:
        return
    cfg = ACTION_CONFIG.get(action, ACTION_CONFIG["hug"])
    actor = message.from_user
    actor_name = actor.first_name or actor.username or "Trainer"

    target = await resolve_target(message, db)
    if not target:
        # Show styled console help card
        card = (
            f"╭───「 {cfg['emoji']} <b>{cfg['title']} CONSOLE</b> 」───╮\n"
            f"│ <i>{cfg['help_desc']}</i>\n"
            f"╰──────────────────────────────╯\n\n"
            + format_blockquote(
                f"📖 <b>How to Use:</b>\n"
                f"• <b>Reply:</b> Reply to someone's message with <code>/{action}</code>\n"
                f"• <b>Username:</b> <code>/{action} @username</code>\n"
                f"• <b>Trainer ID:</b> <code>/{action} 123456789</code>\n\n"
                f"💡 <i>Prefixes: Works with <code>/{action}</code>, <code>.{action}</code>, <code>!{action}</code>, or <code>ani {action}</code>!</i>"
            )
        )
        await message.reply(card, parse_mode="HTML")
        return

    target_id, target_name = target
    gif_url, anime_name = await fetch_action_gif(action)
    caption = build_social_card(actor.id, actor_name, target_id, target_name, action, anime_name)
    builder = build_action_keyboard(action, actor.id, target_id)
    markup = builder.as_markup() if builder else None

    if gif_url:
        try:
            await message.reply_animation(animation=gif_url, caption=caption, parse_mode="HTML", reply_markup=markup)
            return
        except Exception as exc:
            logger.warning(f"Could not send animation for {action}: {exc}")

    # Fallback to formatted text reply
    await message.reply(caption, parse_mode="HTML", reply_markup=markup)

@router.callback_query(F.data.startswith("soc_ret:") | F.data.startswith("soc_rnd:"))
async def cb_social_interact(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split(":")
    mode = parts[0]
    action = parts[1] if mode == "soc_ret" else random.choice(["hug", "kiss", "pat", "cuddle", "poke"])
    orig_actor_id = int(parts[2])
    orig_target_id = int(parts[3])

    caller = callback.from_user
    caller_id = caller.id
    caller_name = caller.first_name or caller.username or "Trainer"

    # Determine who is being targeted in return
    if caller_id == orig_target_id:
        # The original target returns the action to the original actor!
        dest_id = orig_actor_id
        stmt = select(User).where(User.user_id == dest_id)
        res = await db.execute(stmt)
        u = res.scalar_one_or_none()
        dest_name = u.first_name if u else "Trainer"
    elif caller_id == orig_actor_id:
        await callback.answer(f"You already started the {action}! Wait for someone to respond 😉", show_alert=True)
        return
    else:
        # A third party jumped into the reaction!
        dest_id = orig_actor_id
        stmt = select(User).where(User.user_id == dest_id)
        res = await db.execute(stmt)
        u = res.scalar_one_or_none()
        dest_name = u.first_name if u else "Trainer"

    gif_url, anime_name = await fetch_action_gif(action)
    caption = build_social_card(caller_id, caller_name, dest_id, dest_name, action, anime_name)
    builder = build_action_keyboard(action, caller_id, dest_id)
    markup = builder.as_markup() if builder else None

    await callback.answer(f"Sent {action.capitalize()}!")
    if gif_url and callback.message:
        try:
            await callback.message.reply_animation(animation=gif_url, caption=caption, parse_mode="HTML", reply_markup=markup)
            return
        except Exception:
            pass

    if callback.message:
        await callback.message.reply(caption, parse_mode="HTML", reply_markup=markup)

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
