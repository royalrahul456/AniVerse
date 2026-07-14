import random
import math
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InputMediaVideo, InputMediaAnimation, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import joinedload
import config
from database.models import User, Character, UserCharacter, RarityType
from utils.formatters import format_blockquote, get_rarity_emoji, escape_html, format_coins
from utils.claim import check_claim_cooldown, record_claim
from utils.settings import get_cover_media
from keyboards.inline import (
    get_harem_keyboard, 
    get_rarity_selection_menu_keyboard,
    get_list_pagination_keyboard,
    get_check_character_keyboard,
    get_check_back_keyboard,
    get_back_to_hub_keyboard,
    get_showcase_keyboard,
    get_profile_keyboard,
    get_leaderboard_keyboard,
    get_harem_sorting_keyboard
)
from handlers.start import get_or_create_user

router = Router()

PAGE_SIZE = 12
DEFAULT_CHAR_PHOTO = "https://cdn.pixabay.com/photo/2022/12/01/04/35/anime-7628313_1280.jpg"

async def get_all_rarity_items(db: AsyncSession):
    items = [("All", "🌐 View All")]
    seen = set()
    for r_name, r_info in config.RARITY_CONFIG.items():
        items.append((r_name, f"{r_info['emoji']} {r_name}"))
        seen.add(r_name.lower())

    stmt = select(RarityType)
    res = await db.execute(stmt)
    db_rarities = res.scalars().all()
    for dr in db_rarities:
        if dr.name.lower() not in seen:
            items.append((dr.name, f"{dr.emoji} {dr.name}"))
            seen.add(dr.name.lower())
            
    return items

async def get_user_harem_cover(user: User, db: AsyncSession) -> str:
    if user and user.favorite_character_id:
        stmt = select(UserCharacter).where(UserCharacter.user_id == user.user_id, UserCharacter.character_id == user.favorite_character_id).limit(1)
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            char_stmt = select(Character).where(Character.id == user.favorite_character_id)
            char_res = await db.execute(char_stmt)
            char = char_res.scalar_one_or_none()
            if char and char.image_url:
                return char.image_url
    return get_cover_media("dex")

async def send_or_edit_harem(message_obj, cover_media: str, text: str, reply_markup, is_callback: bool):
    if is_callback:
        try:
            await message_obj.edit_media(InputMediaPhoto(media=cover_media, caption=text, parse_mode="HTML"), reply_markup=reply_markup)
            return
        except Exception:
            try:
                await message_obj.edit_media(InputMediaVideo(media=cover_media, caption=text, parse_mode="HTML"), reply_markup=reply_markup)
                return
            except Exception:
                pass
        if message_obj.photo or message_obj.video or message_obj.animation:
            try:
                await message_obj.edit_caption(caption=text, reply_markup=reply_markup, parse_mode="HTML")
                return
            except Exception:
                pass
        try:
            await message_obj.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
            return
        except Exception:
            pass
    try:
        await message_obj.reply_photo(cover_media, caption=text, parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        try:
            await message_obj.reply_video(cover_media, caption=text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception:
            await message_obj.reply(text, parse_mode="HTML", reply_markup=reply_markup)

@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass

# Rarity menu is handled dynamically in cb_bag now

@router.message(Command("fav", "favorite"))
async def cmd_fav(message: Message, db: AsyncSession):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.reply(
            "⚠️ <b>Usage Format:</b> <code>/fav &lt;character_id&gt;</code>\n\n"
            + format_blockquote("Please provide only the numeric character ID!\n<b>Example:</b> <code>/fav 1</code>"),
            parse_mode="HTML"
        )
        return

    char_id = int(parts[1].strip())
    user = await get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)

    stmt = select(UserCharacter, Character).join(Character).where(UserCharacter.user_id == user.user_id, Character.id == char_id)
    res = await db.execute(stmt)
    item = res.first()

    if not item:
        await message.reply(f"❌ You don't own any character with ID <b>#{char_id}</b> in your harem!", parse_mode="HTML")
        return

    uc, char = item
    user.favorite_character_id = char.id
    await db.commit()

    r_emoji = get_rarity_emoji(char.rarity)
    card = (
        f"🌟 <b>FAVORITE HAREM CHARACTER UPDATED!</b> 🌟\n\n"
        + format_blockquote(
            f"🆔 <b>ID:</b> #{char.id}\n"
            f"👤 <b>Favorite:</b> <b>{escape_html(char.name)}</b> [{char.anime}]\n"
            f"{r_emoji} <b>Rarity:</b> {r_emoji} {char.rarity}\n\n"
            f"🖼️ This character's photo will now be used as your custom <b>Harem Cover Banner</b>!"
        )
    )
    photo = char.image_url if char.image_url else get_cover_media()
    try:
        await message.reply_photo(photo, caption=card, parse_mode="HTML")
    except Exception:
        try:
            await message.reply_video(photo, caption=card, parse_mode="HTML")
        except Exception:
            await message.reply(card, parse_mode="HTML")

async def build_profile_card(user: User, db: AsyncSession) -> str:
    THEME_CONFIGS = {
        "default": {
            "top_border": "╭──「 🏆 Profile 」",
            "bullet": "├─➩",
            "progress_filled": "▰",
            "progress_empty": "▱",
            "rarity_header": "╭─ Rarity Breakdown ─",
            "rarity_footer": "╰───────────────────",
            "rank_header": "╭─ Global Rank ─",
            "rank_footer": "╰───────────────────",
            "prem_header": "╭─ Premium Status ─",
            "prem_footer": "╰───────────────────"
        },
        "sakura": {
            "top_border": "╭───「 🌸 Sakura Profile 」───╮",
            "bullet": "├─🌸",
            "progress_filled": "🌸",
            "progress_empty": "💮",
            "rarity_header": "╭─ Rarity Breakdown ─",
            "rarity_footer": "╰───────────────────",
            "rank_header": "╭─ Global Rank ─",
            "rank_footer": "╰───────────────────",
            "prem_header": "╭─ Premium Status ─",
            "prem_footer": "╰───────────────────"
        },
        "gold": {
            "top_border": "╭───「 👑 Gold VIP Profile 」───╮",
            "bullet": "├─👑",
            "progress_filled": "🪙",
            "progress_empty": "🔸",
            "rarity_header": "╭─ Rarity Breakdown ─",
            "rarity_footer": "╰───────────────────",
            "rank_header": "╭─ Global Rank ─",
            "rank_footer": "╰───────────────────",
            "prem_header": "╭─ Premium Status ─",
            "prem_footer": "╰───────────────────"
        },
        "cosmic": {
            "top_border": "╭───「 🌌 Cosmic Profile 」───╮",
            "bullet": "├─🌌",
            "progress_filled": "⭐",
            "progress_empty": "🌑",
            "rarity_header": "╭─ Rarity Breakdown ─",
            "rarity_footer": "╰───────────────────",
            "rank_header": "╭─ Global Rank ─",
            "rank_footer": "╰───────────────────",
            "prem_header": "╭─ Premium Status ─",
            "prem_footer": "╰───────────────────"
        },
        "dark": {
            "top_border": "╭───「 🦇 Dark Knight Profile 」───╮",
            "bullet": "├─🦇",
            "progress_filled": "🖤",
            "progress_empty": "🌑",
            "rarity_header": "╭─ Rarity Breakdown ─",
            "rarity_footer": "╰───────────────────",
            "rank_header": "╭─ Global Rank ─",
            "rank_footer": "╰───────────────────",
            "prem_header": "╭─ Premium Status ─",
            "prem_footer": "╰───────────────────"
        },
        "cyber": {
            "top_border": "╭───「 👾 Neon Cyber Profile 」───╮",
            "bullet": "├─👾",
            "progress_filled": "🔲",
            "progress_empty": "🔳",
            "rarity_header": "╭─ Rarity Breakdown ─",
            "rarity_footer": "╰───────────────────",
            "rank_header": "╭─ Global Rank ─",
            "rank_footer": "╰───────────────────",
            "prem_header": "╭─ Premium Status ─",
            "prem_footer": "╰───────────────────"
        },
        "phoenix": {
            "top_border": "╭───「 🐦‍🔥 Phoenix Profile 」───╮",
            "bullet": "├─🔥",
            "progress_filled": "🔴",
            "progress_empty": "🔸",
            "rarity_header": "╭─ Rarity Breakdown ─",
            "rarity_footer": "╰───────────────────",
            "rank_header": "╭─ Global Rank ─",
            "rank_footer": "╰───────────────────",
            "prem_header": "╭─ Premium Status ─",
            "prem_footer": "╰───────────────────"
        }
    }

    t_key = (user.selected_theme or "default").lower()
    if t_key not in THEME_CONFIGS:
        t_key = "default"
    cfg = THEME_CONFIGS[t_key]

    total_db_chars = (await db.execute(select(func.count(Character.id)))).scalar() or 1

    unique_owned = (await db.execute(
        select(func.count(func.distinct(UserCharacter.character_id)))
        .where(UserCharacter.user_id == user.user_id)
    )).scalar() or 0

    total_snatches = (await db.execute(
        select(func.count(UserCharacter.id))
        .where(UserCharacter.user_id == user.user_id)
    )).scalar() or 0

    harem_pct = (unique_owned / total_db_chars) * 100

    filled = min(10, max(0, int(10 * (unique_owned / total_db_chars))))
    progress_bar = cfg["progress_filled"] * filled + cfg["progress_empty"] * (10 - filled)

    rarity_stmt = (
        select(Character.rarity, func.count(func.distinct(UserCharacter.character_id)))
        .join(UserCharacter, UserCharacter.character_id == Character.id)
        .where(UserCharacter.user_id == user.user_id)
        .group_by(Character.rarity)
    )
    rarity_res = await db.execute(rarity_stmt)
    rarity_counts = list(rarity_res.all())
    rarity_counts.sort(key=lambda x: (x[1], x[0]), reverse=True)

    bullet = cfg["bullet"]
    breakdown_lines = []
    for r_name, r_cnt in rarity_counts:
        emoji = get_rarity_emoji(r_name)
        breakdown_lines.append(f"{bullet} {emoji} {r_name}: <b>{r_cnt}</b>")
    breakdown_text = "\n".join(breakdown_lines) if breakdown_lines else f"{bullet} ⚪️ No characters yet!"

    rank_stmt = (
        select(User.user_id)
        .join(UserCharacter, UserCharacter.user_id == User.user_id)
        .group_by(User.user_id)
        .order_by(desc(func.count(UserCharacter.id)))
    )
    rank_res = await db.execute(rank_stmt)
    all_ranks = rank_res.scalars().all()
    position = 1
    for idx, uid in enumerate(all_ranks):
        if uid == user.user_id:
            position = idx + 1
            break

    now = datetime.datetime.utcnow()
    is_premium = user.premium_until and user.premium_until > now
    if is_premium:
        delta = user.premium_until - now
        days = delta.days
        hours = delta.seconds // 3600
        premium_line = f"{bullet} 👑 Premium Active ({days}d {hours}h left)"
        tag_line = f"{bullet} 🏷️ Tag: {escape_html(user.premium_tag or 'None')}"
    else:
        premium_line = f"{bullet} ❌ Premium Inactive"
        tag_line = f"{bullet} 🏷️ Tag: None"

    card = (
        f"{cfg['top_border']}\n"
        f"{bullet} 🏓 User: {escape_html(user.first_name)}\n"
        f"{bullet} 🆔 ID: {user.user_id}\n"
        f"{bullet} 💰 Balance: {user.coins:,}\n"
        f"{bullet} ⚡ Characters: {unique_owned} (Total Snatches: {total_snatches})\n"
        f"{bullet} 🌍 Harem: {unique_owned}/{total_db_chars} ({harem_pct:.3f}%)\n"
        f"{bullet} 🎁 Progress:\n"
        f"╰         {progress_bar}\n\n"
        f"{cfg['rarity_header']}\n"
        f"{breakdown_text}\n"
        f"{cfg['rarity_footer']}\n\n"
        f"{cfg['rank_header']}\n"
        f"{bullet} 🏆 Position: #{position}\n"
        f"{cfg['rank_footer']}\n"
        f"{cfg['prem_header']}\n"
        f"{premium_line}\n"
        f"{tag_line}\n"
        f"{cfg['prem_footer']}"
    )
    return card

@router.message(Command("profile"))
async def cmd_profile(message: Message, db: AsyncSession):
    user = await get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    text = await build_profile_card(user, db)
    cover_photo = await get_user_harem_cover(user, db)
    kb = get_profile_keyboard()
    await send_or_edit_harem(message, cover_photo, text, kb, is_callback=False)

@router.callback_query(F.data == "dm_profile")
async def cb_profile(callback: CallbackQuery, db: AsyncSession):
    user = await get_or_create_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    text = await build_profile_card(user, db)
    cover_photo = await get_user_harem_cover(user, db)
    kb = get_profile_keyboard()
    await send_or_edit_harem(callback.message, cover_photo, text, kb, is_callback=True)
    try:
        await callback.answer()
    except Exception:
        pass

@router.message(Command("harem"))
async def cmd_harem(message: Message, db: AsyncSession):
    await render_bag_page(message.from_user.id, "All", 1, "anime", message, db, is_callback=False)

@router.callback_query(F.data.startswith("dm_bag_"))
async def cb_bag(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    
    # 1. Check if it's the Sort Menu request
    # Format: dm_bag_sort_menu_{rarity}_{page}_{sort_by}
    if len(parts) >= 7 and parts[2] == "sort" and parts[3] == "menu":
        rarity = parts[4]
        page = int(parts[5])
        sort_by = parts[6]
        
        text = (
            "⇅ <b>SORT HAREM COLLECTION</b>\n\n"
            + format_blockquote("Choose how you would like to sort the characters displayed in your Harem:")
        )
        kb = get_harem_sorting_keyboard(rarity, page, sort_by)
        user_stmt = select(User).where(User.user_id == callback.from_user.id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        cover_photo = await get_user_harem_cover(user, db)
        await send_or_edit_harem(callback.message, cover_photo, text, kb, is_callback=True)
        try:
            await callback.answer()
        except Exception:
            pass
        return

    # 2. Check if it's the Rarity Filter Menu request
    # Format: dm_bag_rarity_menu_{sort_by}
    if len(parts) >= 5 and parts[2] == "rarity" and parts[3] == "menu":
        sort_by = parts[4]
        rarity_items = await get_all_rarity_items(db)
        text = (
            "🔍 <b>FILTER HAREM BY RARITY TIER</b>\n\n"
            + format_blockquote("Select a rarity tier below to view characters belonging exclusively to that category:")
        )
        kb = get_rarity_selection_menu_keyboard(rarity_items, sort_by)
        user_stmt = select(User).where(User.user_id == callback.from_user.id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        cover_photo = await get_user_harem_cover(user, db)
        await send_or_edit_harem(callback.message, cover_photo, text, kb, is_callback=True)
        try:
            await callback.answer()
        except Exception:
            pass
        return

    # 3. Standard bag query
    # Format: dm_bag_{rarity}_{page}_{sort_by}
    if len(parts) >= 5:
        rarity = parts[2]
        page = int(parts[3])
        sort_by = parts[4]
    elif len(parts) == 4:
        rarity = parts[2]
        page = int(parts[3])
        sort_by = "anime"
    else:
        rarity = "All"
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
        sort_by = "anime"

    await render_bag_page(callback.from_user.id, rarity, page, sort_by, callback.message, db, is_callback=True)
    try:
        await callback.answer()
    except Exception:
        pass

async def render_bag_page(user_id: int, rarity: str, page: int, sort_by: str, message_obj, db: AsyncSession, is_callback: bool = False):
    u_stmt = select(User).where(User.user_id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    
    owner_name = escape_html(user.first_name) if (user and user.first_name) else "Trainer"
    owner_header = f'⭐ <b><a href="tg://user?id={user_id}">{owner_name}</a>\'s Harem</b> ⭐'
    cover_photo = await get_user_harem_cover(user, db)

    stmt = (
        select(
            Character.anime,
            Character.id,
            Character.name,
            Character.rarity,
            func.count(UserCharacter.id).label("user_count")
        )
        .join(UserCharacter, UserCharacter.character_id == Character.id)
        .where(UserCharacter.user_id == user_id)
    )

    if rarity.lower() != "all":
        stmt = stmt.where(Character.rarity.ilike(rarity))

    stmt = stmt.group_by(Character.id)

    if sort_by.lower() == "id":
        stmt = stmt.order_by(Character.id)
    elif sort_by.lower() == "name":
        stmt = stmt.order_by(Character.name)
    elif sort_by.lower() == "rarity":
        stmt = stmt.order_by(Character.rarity, Character.id)
    else:
        sort_by = "anime"
        stmt = stmt.order_by(Character.anime, Character.id)

    res = await db.execute(stmt)
    user_owned_rows = res.all()

    if not user_owned_rows:
        text = (
            f"{owner_header} — Page 1/1\n\n"
            + format_blockquote(f"Your harem collection for tier [{rarity.upper()}] is currently empty!\nCatch wild characters or open mystery boxes in the shop.")
        )
        kb = get_harem_keyboard(user_id, 1, 1, rarity, sort_by)
        await send_or_edit_harem(message_obj, cover_photo, text, kb, is_callback)
        return

    if sort_by == "anime":
        anime_groups = {}
        for anime, c_id, c_name, c_rarity, u_cnt in user_owned_rows:
            if anime not in anime_groups:
                anime_groups[anime] = []
            anime_groups[anime].append((c_id, c_name, c_rarity, u_cnt))

        total_anime_shows = len(anime_groups)
        per_page_anime = 4
        max_page = math.ceil(total_anime_shows / per_page_anime)
        page = max(1, min(page, max_page))

        anime_keys = list(anime_groups.keys())
        start_idx = (page - 1) * per_page_anime
        page_anime_keys = anime_keys[start_idx:start_idx + per_page_anime]

        anime_totals_res = await db.execute(select(Character.anime, func.count(Character.id)).group_by(Character.anime))
        anime_db_totals = {an: cnt for an, cnt in anime_totals_res.all()}

        lines = [f"{owner_header} — Page {page}/{max_page}\n"]
        for an_title in page_anime_keys:
            char_list = anime_groups[an_title]
            owned_in_anime = len(char_list)
            total_in_anime = anime_db_totals.get(an_title, owned_in_anime)
            lines.append(f"\n<b>{escape_html(an_title)} {owned_in_anime}/{total_in_anime}</b>")
            for c_id, c_name, c_rarity, u_cnt in char_list:
                r_emoji = get_rarity_emoji(c_rarity)
                lines.append(f"◈ [ {r_emoji} ] {c_id} {escape_html(c_name)} ×{u_cnt}")
    else:
        total_items = len(user_owned_rows)
        per_page_flat = 15
        max_page = math.ceil(total_items / per_page_flat)
        page = max(1, min(page, max_page))

        start_idx = (page - 1) * per_page_flat
        page_rows = user_owned_rows[start_idx:start_idx + per_page_flat]

        lines = [f"{owner_header} (Sorted by: {sort_by.upper()}) — Page {page}/{max_page}\n"]
        for anime, c_id, c_name, c_rarity, u_cnt in page_rows:
            r_emoji = get_rarity_emoji(c_rarity)
            lines.append(f"◈ [ {r_emoji} ] <code>#{c_id}</code> <b>{escape_html(c_name)}</b> ({escape_html(anime)}) ×{u_cnt}")

    text = "\n".join(lines)
    kb = get_harem_keyboard(user_id, page, max_page, rarity, sort_by)
    await send_or_edit_harem(message_obj, cover_photo, text, kb, is_callback)

@router.callback_query(F.data.startswith("harem_col_") | F.data.startswith("harem_amv_"))
async def cb_harem_showcase(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    mode = parts[1]
    user_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 1
    await render_harem_showcase(user_id, mode, page, callback.message, db, is_callback=True)
    try:
        await callback.answer()
    except Exception:
        pass

async def render_harem_showcase(user_id: int, mode: str, page: int, message_obj, db: AsyncSession, is_callback: bool = True):
    u_stmt = select(User).where(User.user_id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    owner_name = escape_html(user.first_name) if (user and user.first_name) else "Trainer"

    stmt = (
        select(Character, func.count(UserCharacter.id).label("user_count"))
        .join(UserCharacter, UserCharacter.character_id == Character.id)
        .where(UserCharacter.user_id == user_id)
        .group_by(Character.id)
        .order_by(Character.id)
    )
    res = await db.execute(stmt)
    rows = res.all()

    if not rows:
        text = f"🎒 <b>{owner_name}'s Collection is empty!</b>"
        await send_or_edit_harem(message_obj, get_cover_media(), text, get_showcase_keyboard(user_id, mode, 1, 1), is_callback)
        return

    total_items = len(rows)
    page = max(1, min(page, total_items))
    char, u_cnt = rows[page - 1]

    r_emoji = get_rarity_emoji(char.rarity)
    title_header = "💌 <b>HAREM AMV EDIT SHOWCASE</b>" if mode == "amv" else "🖼️ <b>COLLECTION SHOWCASE</b>"
    
    text = (
        f"{title_header} ({page}/{total_items})\n"
        f"👤 <b>Owner:</b> <a href=\"tg://user?id={user_id}\">{owner_name}</a>\n\n"
        + format_blockquote(
            f"🌟 <b>Name:</b> {escape_html(char.name)}\n"
            f"🆔 <b>ID:</b> #{char.id}\n"
            f"📺 <b>Anime:</b> {escape_html(char.anime)}\n"
            f"🎬 <b>Rarity:</b> {r_emoji} {char.rarity}\n"
            f"📦 <b>Copies Owned:</b> ×{u_cnt}"
        )
    )

    media_url = char.image_url if char.image_url else DEFAULT_CHAR_PHOTO
    kb = get_showcase_keyboard(user_id, mode, page, total_items)
    await send_or_edit_harem(message_obj, media_url, text, kb, is_callback)

@router.message(Command("check"))
async def cmd_check(message: Message, db: AsyncSession):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⚠️ <b>Usage:</b> <code>/check &lt;character_id or name&gt;</code>", parse_mode="HTML")
        return

    query_str = parts[1].strip()
    if query_str.isdigit():
        stmt = select(Character).where(Character.id == int(query_str))
    else:
        stmt = select(Character).where(Character.name.ilike(f"%{query_str}%"))

    res = await db.execute(stmt)
    character = res.scalar_one_or_none()

    if not character:
        await message.reply(f"❌ No character found matching {escape_html(query_str)}!", parse_mode="HTML")
        return

    r_emoji = get_rarity_emoji(character.rarity)
    card = (
        f"👾 <b>Character Info</b>\n\n"
        + format_blockquote(
            f"🆔 <b>ID:</b> {character.id}\n"
            f"⛔ <b>Name:</b> {escape_html(character.name)}\n"
            f"🍿 <b>Anime:</b> {escape_html(character.anime)}\n"
            f"🎬 <b>Rarity:</b> {r_emoji} {character.rarity}"
        )
    )

    photo_to_send = character.image_url if character.image_url else DEFAULT_CHAR_PHOTO
    kb = get_check_character_keyboard(character.id)
    try:
        await message.reply_photo(photo_to_send, caption=card, parse_mode="HTML", reply_markup=kb)
    except Exception:
        try:
            await message.reply_video(photo_to_send, caption=card, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await message.reply(card, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("who_has_"))
async def cb_who_has(callback: CallbackQuery, db: AsyncSession):
    char_id = int(callback.data.split("_")[2])
    
    char_stmt = select(Character).where(Character.id == char_id)
    char_res = await db.execute(char_stmt)
    character = char_res.scalar_one_or_none()
    if not character:
        await callback.answer("❌ Character not found.", show_alert=True)
        return

    stmt = (
        select(User.first_name, User.user_id, func.count(UserCharacter.id).label("cnt"))
        .join(UserCharacter, UserCharacter.user_id == User.user_id)
        .where(UserCharacter.character_id == char_id)
        .group_by(User.user_id)
        .order_by(func.count(UserCharacter.id).desc())
        .limit(15)
    )
    res = await db.execute(stmt)
    rows = res.all()

    if not rows:
        try:
            await callback.answer("❌ Nobody owns this character yet!", show_alert=True)
        except Exception:
            pass
        return

    lines = []
    for idx, (f_name, u_id, cnt) in enumerate(rows, 1):
        lines.append(f"{idx}. {escape_html(f_name)} ×{cnt}")

    text = (
        f"🎦 <b>Who has this character :</b>\n"
        + format_blockquote("\n".join(lines))
    )

    kb = get_check_back_keyboard(char_id)
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass
    try:
        await callback.answer()
    except Exception:
        pass

@router.callback_query(F.data.startswith("check_back_"))
async def cb_check_back(callback: CallbackQuery, db: AsyncSession):
    char_id = int(callback.data.split("_")[2])
    
    char_stmt = select(Character).where(Character.id == char_id)
    char_res = await db.execute(char_stmt)
    character = char_res.scalar_one_or_none()
    if not character:
        await callback.answer("❌ Character not found.", show_alert=True)
        return

    r_emoji = get_rarity_emoji(character.rarity)
    card = (
        f"👾 <b>Character Info</b>\n\n"
        + format_blockquote(
            f"🆔 <b>ID:</b> {character.id}\n"
            f"⛔ <b>Name:</b> {escape_html(character.name)}\n"
            f"🍿 <b>Anime:</b> {escape_html(character.anime)}\n"
            f"🎬 <b>Rarity:</b> {r_emoji} {character.rarity}"
        )
    )
    
    kb = get_check_character_keyboard(character.id)
    try:
        await callback.message.edit_caption(caption=card, parse_mode="HTML", reply_markup=kb)
    except Exception:
        try:
            await callback.message.edit_text(card, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass
    try:
        await callback.answer()
    except Exception:
        pass

@router.message(Command("search"))
async def cmd_search(message: Message, db: AsyncSession):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⚠️ <b>Usage:</b> <code>/search &lt;character_name&gt;</code>\n<i>Example: /search Goku</i>", parse_mode="HTML")
        return
    query_str = parts[1].strip()
    await render_search_list(query_str, 1, message, db, is_callback=False)

@router.callback_query(F.data.startswith("search_list_"))
async def cb_search_list(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    page = int(parts[-1])
    query_str = "_".join(parts[2:-1])
    await render_search_list(query_str, page, callback.message, db, is_callback=True)
    try:
        await callback.answer()
    except Exception:
        pass

async def render_search_list(query_str: str, page: int, message_obj, db: AsyncSession, is_callback: bool = False):
    stmt = select(Character).where(Character.name.ilike(f"%{query_str}%")).order_by(Character.id)
    res = await db.execute(stmt)
    characters = res.scalars().all()

    if not characters:
        text = f"❌ No characters found matching <b>{escape_html(query_str)}</b>!"
        if is_callback:
            await message_obj.edit_text(text, parse_mode="HTML")
        else:
            await message_obj.reply(text, parse_mode="HTML")
        return

    per_page = 8
    total_cnt = len(characters)
    max_page = math.ceil(total_cnt / per_page)
    page = max(1, min(page, max_page))

    start_idx = (page - 1) * per_page
    page_chars = characters[start_idx:start_idx + per_page]

    lines = [f"✨ <b>Results for \"{escape_html(query_str)}\"</b>", f"Total: <b>{total_cnt}</b> — Page <b>{page}/{max_page}</b>\n"]
    for c in page_chars:
        r_emoji = get_rarity_emoji(c.rarity)
        lines.append(f"• <b>{escape_html(c.name)}</b> — {escape_html(c.anime)}\n  {r_emoji} {c.rarity} | ID: {c.id}\n")

    text = "\n".join(lines)
    kb = get_list_pagination_keyboard("search_list", query_str, page, max_page)
    if is_callback:
        await message_obj.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message_obj.reply(text, parse_mode="HTML", reply_markup=kb)

@router.message(Command("anime"))
async def cmd_anime(message: Message, db: AsyncSession):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⚠️ <b>Usage:</b> <code>/anime &lt;anime_name&gt;</code>\n<i>Example: /anime Wuthering Waves</i>", parse_mode="HTML")
        return
    query_str = parts[1].strip()
    await render_anime_list(query_str, 1, message, db, is_callback=False)

@router.callback_query(F.data.startswith("anime_list_"))
async def cb_anime_list(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    page = int(parts[-1])
    query_str = "_".join(parts[2:-1])
    await render_anime_list(query_str, page, callback.message, db, is_callback=True)
    try:
        await callback.answer()
    except Exception:
        pass

async def render_anime_list(query_str: str, page: int, message_obj, db: AsyncSession, is_callback: bool = False):
    stmt = select(Character).where(Character.anime.ilike(f"%{query_str}%")).order_by(Character.id)
    res = await db.execute(stmt)
    characters = res.scalars().all()

    if not characters:
        text = f"❌ No anime shows found matching <b>{escape_html(query_str)}</b>!"
        if is_callback:
            await message_obj.edit_text(text, parse_mode="HTML")
        else:
            await message_obj.reply(text, parse_mode="HTML")
        return

    anime_title = characters[0].anime
    per_page = 8
    total_cnt = len(characters)
    max_page = math.ceil(total_cnt / per_page)
    page = max(1, min(page, max_page))

    start_idx = (page - 1) * per_page
    page_chars = characters[start_idx:start_idx + per_page]

    lines = [f"🍿 <b>{escape_html(anime_title)}</b>", f"Total characters: <b>{total_cnt}</b> — Page <b>{page}/{max_page}</b>\n"]
    for c in page_chars:
        r_emoji = get_rarity_emoji(c.rarity)
        lines.append(f"• <b>{escape_html(c.name)}</b>\n  {r_emoji} {c.rarity} | ID: {c.id}\n")

    text = "\n".join(lines)
    kb = get_list_pagination_keyboard("anime_list", query_str, page, max_page)
    if is_callback:
        await message_obj.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message_obj.reply(text, parse_mode="HTML", reply_markup=kb)

@router.message(Command("claim"))
async def cmd_claim(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    can_claim, time_remaining = check_claim_cooldown(user_id)
    
    if not can_claim:
        hours = time_remaining // 3600
        minutes = (time_remaining % 3600) // 60
        text = (
            f"⏳ <b>Daily Free Roll Cooldown!</b>\n\n"
            + format_blockquote(f"You must wait <b>{hours}h {minutes}m</b> before claiming your next random free character!\n\n<i>Resets daily at 5:30 AM IST</i>")
        )
        cover = get_cover_media("start")
        try:
            await message.reply_photo(cover, caption=text, parse_mode="HTML")
        except Exception:
            try:
                await message.reply_video(cover, caption=text, parse_mode="HTML")
            except Exception:
                await message.reply(text, parse_mode="HTML")
        return

    stmt = select(Character)
    res = await db.execute(stmt)
    characters = res.scalars().all()
    if not characters:
        await message.reply("⚠️ No characters available in database right now.")
        return

    weights = [config.RARITY_CONFIG.get(c.rarity, {"weight": 10})["weight"] for c in characters]
    character = random.choices(characters, weights=weights, k=1)[0]

    user = await get_or_create_user(db, user_id, message.from_user.username, message.from_user.first_name)
    user.total_catches += 1
    
    user_char = UserCharacter(user_id=user_id, character_id=character.id, nickname=character.name)
    db.add(user_char)
    await db.commit()

    record_claim(user_id)
    r_emoji = get_rarity_emoji(character.rarity)
    total_weight = sum(config.RARITY_CONFIG.get(c.rarity, {"weight": 10})["weight"] for c in characters)
    char_weight = config.RARITY_CONFIG.get(character.rarity, {"weight": 10})["weight"]
    chance_pct = (char_weight / total_weight) * 100

    card = (
        f"✨ <b>CONGRATS {escape_html(message.from_user.first_name.upper())}!</b>\n\n"
        + format_blockquote(
            f"📛 <b>Name:</b> {escape_html(character.name)}\n"
            f"💎 <b>Rarity:</b> {r_emoji} {character.rarity}\n"
            f"⚡ <b>Chance:</b> {chance_pct:.2f}%\n"
            f"📺 <b>Anime:</b> {escape_html(character.anime)}\n"
            f"🆔 <b>ID:</b> #{character.id:03d}\n\n"
            f"⏳ <i>Resets daily at 5:30 AM IST</i>"
        )
    )
    
    photo_to_send = character.image_url if character.image_url else DEFAULT_CHAR_PHOTO
    try:
        await message.reply_photo(photo_to_send, caption=card, parse_mode="HTML")
    except Exception:
        try:
            await message.reply_video(photo_to_send, caption=card, parse_mode="HTML")
        except Exception:
            await message.reply(card, parse_mode="HTML")

@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message, db: AsyncSession):
    parts = message.text.strip().split()
    category = "coins"
    if len(parts) > 1:
        arg = parts[1].lower()
        if "catch" in arg or "snatch" in arg:
            category = "catches"
        elif "prem" in arg:
            category = "premium"
    await render_leaderboard(category, message, db, is_callback=False)

@router.callback_query(F.data.startswith("dm_leaderboard"))
async def cb_leaderboard(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    category = parts[2] if len(parts) > 2 else "coins"
    await render_leaderboard(category, callback.message, db, is_callback=True)
    try:
        await callback.answer()
    except Exception:
        pass

async def render_leaderboard(category: str, message_obj, db: AsyncSession, is_callback: bool = False):
    category = category.lower()
    medals = ["🥇", "🥈", "🥉"]
    lines = []

    if category == "catches":
        border_top = "╭───「 ⚡ Top Snatches 」───╮"
        stmt = select(User).order_by(desc(User.total_catches)).limit(10)
        res = await db.execute(stmt)
        top_users = res.scalars().all()
        for idx, u in enumerate(top_users):
            icon = medals[idx] if idx < 3 else f"<b>#{idx+1}</b>"
            name_str = f"@{u.username}" if u.username else u.first_name
            lines.append(f"│  {icon} <b>{escape_html(name_str)}</b> - {u.total_catches:,} catches")
        
    elif category == "premium":
        border_top = "╭───「 👑 Premium Members 」───╮"
        now = datetime.datetime.utcnow()
        stmt = select(User).where(User.premium_until > now).order_by(User.premium_until).limit(10)
        res = await db.execute(stmt)
        top_users = res.scalars().all()
        for idx, u in enumerate(top_users):
            icon = medals[idx] if idx < 3 else f"<b>#{idx+1}</b>"
            name_str = f"@{u.username}" if u.username else u.first_name
            delta = u.premium_until - now
            tag_str = f" [{escape_html(u.premium_tag)}]" if u.premium_tag else ""
            lines.append(f"│  {icon} <b>{escape_html(name_str)}</b>{tag_str} - {delta.days}d left")
        
    else:
        category = "coins"
        border_top = "╭───「 💰 Rich Leaderboard 」───╮"
        stmt = select(User).order_by(desc(User.coins)).limit(10)
        res = await db.execute(stmt)
        top_users = res.scalars().all()
        for idx, u in enumerate(top_users):
            icon = medals[idx] if idx < 3 else f"<b>#{idx+1}</b>"
            name_str = f"@{u.username}" if u.username else u.first_name
            lines.append(f"│  {icon} <b>{escape_html(name_str)}</b> - {format_coins(u.coins)}")

    border_bottom = "╰──────────────────────────╯"
    body_content = "\n".join(lines) if lines else "│  No players ranked yet!"
    
    text = (
        f"{border_top}\n"
        f"│\n"
        f"{body_content}\n"
        f"│\n"
        f"{border_bottom}"
    )

    cover_media = get_cover_media("leaderboard")
    kb = get_leaderboard_keyboard(category)

    if is_callback:
        try:
            await message_obj.edit_media(InputMediaPhoto(media=cover_media, caption=text, parse_mode="HTML"), reply_markup=kb)
        except Exception:
            try:
                await message_obj.edit_media(InputMediaVideo(media=cover_media, caption=text, parse_mode="HTML"), reply_markup=kb)
            except Exception:
                try:
                    await message_obj.edit_text(text, parse_mode="HTML", reply_markup=kb)
                except Exception:
                    pass
    else:
        try:
            await message_obj.reply_photo(cover_media, caption=text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            try:
                await message_obj.reply_video(cover_media, caption=text, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await message_obj.reply(text, parse_mode="HTML", reply_markup=kb)

@router.message(Command("settheme"))
async def cmd_settheme(message: Message, db: AsyncSession):
    user = await get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    unlocked = [t.strip().lower() for t in (user.unlocked_themes or "default").split(",") if t.strip()]

    theme_details = {
        "default": {"name": "Default Theme", "emoji": "🏆"},
        "sakura": {"name": "Sakura Theme", "emoji": "🌸"},
        "cosmic": {"name": "Cosmic Theme", "emoji": "🌌"},
        "gold": {"name": "Gold VIP Theme", "emoji": "👑"},
        "dark": {"name": "Dark Knight Theme", "emoji": "🦇"},
        "cyber": {"name": "Neon Cyber Theme", "emoji": "👾"},
        "phoenix": {"name": "Phoenix Theme", "emoji": "🐦‍🔥"}
    }

    text = (
        "🎨 <b>Choose Your Trainer Profile Theme</b>\n\n"
        + format_blockquote(
            "Select one of your unlocked profile card themes below to apply it dynamically to your profile card!\n\n"
            f"✨ <b>Active Theme:</b> {theme_details.get(user.selected_theme or 'default', theme_details['default'])['name']}"
        )
    )

    builder = InlineKeyboardBuilder()
    for key, info in theme_details.items():
        if key in unlocked:
            is_active = (user.selected_theme or "default").lower() == key
            label = f"{info['emoji']} {info['name']}" + (" (Active)" if is_active else "")
            builder.row(InlineKeyboardButton(text=label, callback_data=f"set_theme_{key}"))
        else:
            label = f"🔒 {info['name']} (Lock)"
            builder.row(InlineKeyboardButton(text=label, callback_data="noop"))
    builder.row(
        InlineKeyboardButton(text="🔙 Back to Profile", callback_data="dm_profile"),
        InlineKeyboardButton(text="🏠 Hub", callback_data="dm_home")
    )

    await message.reply(text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "cb_themes_menu")
async def cb_themes_menu(callback: CallbackQuery, db: AsyncSession):
    user = await get_or_create_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    unlocked = [t.strip().lower() for t in (user.unlocked_themes or "default").split(",") if t.strip()]

    theme_details = {
        "default": {"name": "Default Theme", "emoji": "🏆"},
        "sakura": {"name": "Sakura Theme", "emoji": "🌸"},
        "cosmic": {"name": "Cosmic Theme", "emoji": "🌌"},
        "gold": {"name": "Gold VIP Theme", "emoji": "👑"},
        "dark": {"name": "Dark Knight Theme", "emoji": "🦇"},
        "cyber": {"name": "Neon Cyber Theme", "emoji": "👾"},
        "phoenix": {"name": "Phoenix Theme", "emoji": "🐦‍🔥"}
    }

    text = (
        "🎨 <b>Choose Your Trainer Profile Theme</b>\n\n"
        + format_blockquote(
            "Select one of your unlocked profile card themes below to apply it dynamically to your profile card!\n\n"
            f"✨ <b>Active Theme:</b> {theme_details.get(user.selected_theme or 'default', theme_details['default'])['name']}"
        )
    )

    builder = InlineKeyboardBuilder()
    for key, info in theme_details.items():
        if key in unlocked:
            is_active = (user.selected_theme or "default").lower() == key
            label = f"{info['emoji']} {info['name']}" + (" (Active)" if is_active else "")
            builder.row(InlineKeyboardButton(text=label, callback_data=f"set_theme_{key}"))
        else:
            label = f"🔒 {info['name']} (Lock)"
            builder.row(InlineKeyboardButton(text=label, callback_data="noop"))
    builder.row(
        InlineKeyboardButton(text="🔙 Back to Profile", callback_data="dm_profile"),
        InlineKeyboardButton(text="🏠 Hub", callback_data="dm_home")
    )

    cover_media = await get_user_harem_cover(user, db)
    await send_or_edit_harem(callback.message, cover_media, text, builder.as_markup(), is_callback=True)
    await callback.answer()

@router.callback_query(F.data.startswith("set_theme_"))
async def cb_set_theme(callback: CallbackQuery, db: AsyncSession):
    theme_key = callback.data.replace("set_theme_", "")
    user = await get_or_create_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    unlocked = [t.strip().lower() for t in (user.unlocked_themes or "default").split(",") if t.strip()]

    if theme_key not in unlocked:
        await callback.answer("❌ You haven't unlocked this theme yet!", show_alert=True)
        return

    user.selected_theme = theme_key
    await db.commit()

    await callback.answer(f"✅ Applied theme successfully!", show_alert=True)
    
    theme_details = {
        "default": {"name": "Default Theme", "emoji": "🏆"},
        "sakura": {"name": "Sakura Theme", "emoji": "🌸"},
        "cosmic": {"name": "Cosmic Theme", "emoji": "🌌"},
        "gold": {"name": "Gold VIP Theme", "emoji": "👑"},
        "dark": {"name": "Dark Knight Theme", "emoji": "🦇"},
        "cyber": {"name": "Neon Cyber Theme", "emoji": "👾"},
        "phoenix": {"name": "Phoenix Theme", "emoji": "🐦‍🔥"}
    }
    text = (
        "🎨 <b>Choose Your Trainer Profile Theme</b>\n\n"
        + format_blockquote(
            "Select one of your unlocked profile card themes below to apply it dynamically to your profile card!\n\n"
            f"✨ <b>Active Theme:</b> {theme_details.get(user.selected_theme or 'default', theme_details['default'])['name']}"
        )
    )

    builder = InlineKeyboardBuilder()
    for key, info in theme_details.items():
        if key in unlocked:
            is_active = (user.selected_theme or "default").lower() == key
            label = f"{info['emoji']} {info['name']}" + (" (Active)" if is_active else "")
            builder.row(InlineKeyboardButton(text=label, callback_data=f"set_theme_{key}"))
        else:
            label = f"🔒 {info['name']} (Lock)"
            builder.row(InlineKeyboardButton(text=label, callback_data="noop"))
    builder.row(
        InlineKeyboardButton(text="🔙 Back to Profile", callback_data="dm_profile"),
        InlineKeyboardButton(text="🏠 Hub", callback_data="dm_home")
    )

    cover_media = await get_user_harem_cover(user, db)
    await send_or_edit_harem(callback.message, cover_media, text, builder.as_markup(), is_callback=True)
