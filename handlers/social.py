import logging
import html
import random
import aiohttp
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import User
from utils.formatters import format_blockquote, escape_html

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
        "help_desc": "Share warm affection and cozy hugs with fellow trainers!"
    },
    "kiss": {
        "emoji": "💋",
        "title": "ANIME KISS",
        "actions": [
            "pulls close and gives a sweet, passionate kiss to",
            "plants a gentle, loving anime kiss on",
            "blushes brightly and softly kisses",
            "shares a tender romantic anime kiss with",
        ],
        "flavor": "Doki-Doki Heartbeat: Over 9,000! 💕",
        "self_msg": "blows a magical, sparkling kiss into the air! ✨",
        "self_flavor": "Sending pure love across the entire anime universe! 💖",
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
        "help_desc": "Defeat someone in an epic anime battle duel!"
    },
    "wave": {
        "emoji": "👋",
        "title": "ANIME WAVE",
        "actions": [
            "smiles brightly and waves excitedly at",
            "gives a cheerful anime wave to",
            "waves hello warmly to",
        ],
        "flavor": "Friendliness: 100% Sparkles ✨",
        "self_msg": "waves to their own reflection in the mirror! 🪞",
        "self_flavor": "Confidence: Boosted ✨",
        "help_desc": "Give a cheerful anime wave to fellow trainers!"
    },
    "smile": {
        "emoji": "✨",
        "title": "ANIME SMILE",
        "actions": [
            "beams with joy and flashes a radiant anime smile at",
            "smiles warmly and tenderly towards",
            "gives a cute, glowing smile to",
        ],
        "flavor": "Brightness: Blinding Sunshine ☀️",
        "self_msg": "smiles brightly at how wonderful life is! 🌸",
        "self_flavor": "Inner Peace: Achieved 💖",
        "help_desc": "Share a warm, heart-melting anime smile!"
    },
    "yeet": {
        "emoji": "🚀",
        "title": "ANIME YEET",
        "actions": [
            "grabs and yeets",
            "hurls into the stratosphere",
            "launches into orbit",
        ],
        "flavor": "Escape Velocity Achieved: Mach 10 🌌",
        "self_msg": "yeeted themselves into another anime dimension! 🌠",
        "self_flavor": "Trajectory: Interstellar 🚀",
        "help_desc": "Yeet someone straight into outer orbit!"
    }
}

# ----------------------------------------------------
# MULTI-PROVIDER ANIME GIF FETCHER
# ----------------------------------------------------
async def _fetch_from_nekos_best(session: aiohttp.ClientSession, action: str):
    async with session.get(f"https://nekos.best/api/v2/{action}") as resp:
        if resp.status == 200:
            data = await resp.json()
            res = data.get("results", [{}])[0]
            url = res.get("url")
            anime = res.get("anime_name")
            if url and url.startswith("https://"):
                return url, anime
    return None, None

async def _fetch_from_gifukai(session: aiohttp.ClientSession, action: str):
    async with session.get(f"https://api.gifukai.com/v1/{action}") as resp:
        if resp.status == 200:
            data = await resp.json()
            url = data.get("url")
            anime = data.get("anime")
            if url and url.startswith("https://"):
                return url, anime
    return None, None

async def _fetch_from_otakugifs(session: aiohttp.ClientSession, action: str):
    async with session.get(f"https://api.otakugifs.xyz/gif?reaction={action}") as resp:
        if resp.status == 200:
            data = await resp.json()
            url = data.get("url")
            if url and url.startswith("https://"):
                return url, None
    return None, None

async def _fetch_from_purrbot(session: aiohttp.ClientSession, action: str):
    async with session.get(f"https://purrbot.site/api/img/sfw/{action}/gif") as resp:
        if resp.status == 200:
            data = await resp.json()
            url = data.get("link")
            if url and url.startswith("https://"):
                return url, None
    return None, None

async def _fetch_from_nekos_life(session: aiohttp.ClientSession, action: str):
    async with session.get(f"https://nekos.life/api/v2/img/{action}") as resp:
        if resp.status == 200:
            data = await resp.json()
            url = data.get("url")
            if url and url.startswith("https://"):
                return url, None
    return None, None

async def _fetch_from_waifu_pics(session: aiohttp.ClientSession, action: str):
    async with session.get(f"https://api.waifu.pics/sfw/{action}") as resp:
        if resp.status == 200:
            data = await resp.json()
            url = data.get("url")
            if url and url.startswith("https://"):
                return url, None
    return None, None

ALL_GIF_PROVIDERS = [
    _fetch_from_nekos_best,
    _fetch_from_gifukai,
    _fetch_from_otakugifs,
    _fetch_from_purrbot,
    _fetch_from_nekos_life,
    _fetch_from_waifu_pics,
]

async def fetch_action_gif(action: str) -> tuple[str | None, str | None]:
    """Fetches an anime GIF URL across 6 public anime GIF providers with randomized rotation and fallback."""
    providers = list(ALL_GIF_PROVIDERS)
    random.shuffle(providers)
    headers = {"User-Agent": "AniVerseBot/1.0", "Accept": "application/json"}
    timeout = aiohttp.ClientTimeout(total=4)

    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for provider_fn in providers:
                try:
                    url, anime = await provider_fn(session, action)
                    if url and isinstance(url, str) and url.startswith("https://"):
                        return url, anime if isinstance(anime, str) and anime.strip() else None
                except Exception as exc:
                    logger.debug(f"{provider_fn.__name__} error for {action}: {exc}")
                    continue
    except Exception as e:
        logger.warning(f"Error in multi-provider GIF pool: {e}")

    return None, None

async def resolve_target(message: Message, db: AsyncSession) -> tuple[int, str] | None:
    """Resolves the target user via reply, entity mention, @username, or numeric ID."""
    # 1. Direct message reply
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        name = u.first_name or u.username or "Trainer"
        return u.id, name

    # 2. Text mention entities
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

async def handle_social_action(message: Message, action: str, db: AsyncSession):
    if not message.from_user:
        return
    cfg = ACTION_CONFIG.get(action, ACTION_CONFIG["hug"])
    actor = message.from_user
    actor_name = actor.first_name or actor.username or "Trainer"

    target = await resolve_target(message, db)
    if not target:
        # Show styled console help card (clean, no inline buttons)
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

@router.message(Command("wave"))
async def cmd_wave(message: Message, db: AsyncSession):
    await handle_social_action(message, "wave", db)

@router.message(Command("smile"))
async def cmd_smile(message: Message, db: AsyncSession):
    await handle_social_action(message, "smile", db)

@router.message(Command("yeet"))
async def cmd_yeet(message: Message, db: AsyncSession):
    await handle_social_action(message, "yeet", db)
