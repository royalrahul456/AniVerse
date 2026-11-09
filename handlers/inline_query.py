from utils.emojis import get_emoji, get_plain_emoji
import logging
import html
from aiogram import Router, F
from aiogram.types import (
    InlineQuery, 
    InlineQueryResultPhoto, 
    InlineQueryResultCachedPhoto, 
    InlineQueryResultCachedVideo, 
    InlineQueryResultArticle, 
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, or_
from database.database import AsyncSessionLocal
from database.models import User, UserCharacter, Character
from utils.formatters import get_rarity_emoji, escape_html, format_blockquote
from handlers.start import get_or_create_user
from handlers.profile import build_profile_card, get_user_harem_cover, make_safe_caption

logger = logging.getLogger(__name__)
router = Router()

DEFAULT_THUMB = "https://images7.alphacoders.com/133/1331826.jpeg"

def clean_html_entities(val: str) -> str:
    """Recursively unescapes HTML entities to handle double-escaped strings like &amp;amp; or &#x27;"""
    if not val:
        return ""
    prev = ""
    while prev != val:
        prev = val
        val = html.unescape(val)
    return val

def is_valid_url(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    if url in ("https://img.jpg", "http://img.jpg", "https://example.com"):
        return False
    return True

def build_inline_item(
    item_id: str,
    img_val: str,
    title: str,
    clean_anime: str,
    caption: str,
    rarity: str = "",
    filter_mode: str = "",
    reply_markup: InlineKeyboardMarkup = None
):
    """Safely builds appropriate InlineQueryResult based on image URL / Telegram file ID type."""
    if img_val and img_val.startswith("http"):
        if is_valid_url(img_val):
            return InlineQueryResultPhoto(
                id=item_id,
                photo_url=img_val,
                thumbnail_url=img_val,
                title=title,
                description=clean_anime,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        else:
            return InlineQueryResultArticle(
                id=item_id,
                title=title,
                description=clean_anime,
                thumbnail_url=DEFAULT_THUMB,
                input_message_content=InputTextMessageContent(
                    message_text=caption,
                    parse_mode="HTML"
                ),
                reply_markup=reply_markup
            )
    
    # Telegram file ID logic
    is_video = (
        bool(img_val and img_val.startswith(("BAAC", "BAAD", "CgAC", "CGAC", "BQAC", "DQAC"))) or 
        (filter_mode and filter_mode.upper() == "AMV") or 
        (rarity and rarity.lower() == "amv")
    )
    
    if is_video and img_val:
        try:
            return InlineQueryResultCachedVideo(
                id=item_id,
                video_file_id=img_val,
                title=title,
                description=clean_anime,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except Exception:
            pass

    if img_val:
        try:
            return InlineQueryResultCachedPhoto(
                id=item_id,
                photo_file_id=img_val,
                title=title,
                description=clean_anime,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except Exception:
            pass

    return InlineQueryResultArticle(
        id=item_id,
        title=title,
        description=clean_anime,
        thumbnail_url=DEFAULT_THUMB,
        input_message_content=InputTextMessageContent(
            message_text=caption,
            parse_mode="HTML"
        ),
        reply_markup=reply_markup
    )

@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    query = inline_query.query.strip()
    results = []
    user_id = inline_query.from_user.id

    # Pagination settings (limit = 25 per page for fast & smooth Telegram scroll)
    offset = int(inline_query.offset) if inline_query.offset and inline_query.offset.isdigit() else 0
    limit = 25

    try:
        bot_user = await inline_query.bot.get_me()
        bot_username = bot_user.username or "AniVerse1bot"
    except Exception:
        bot_username = "AniVerse1bot"

    async with AsyncSessionLocal() as db:
        # =========================================================
        # 1. EMPTY QUERY OR HELP COMMAND
        # =========================================================
        if not query or query.lower() in ("help", "guide", "inline"):
            if offset == 0:
                # Article 1: Guide card
                guide_text = (
                    f"🔍 <b>AniVerse Inline Mode</b>\n\n"
                    f"<b>How to use:</b>\n"
                    f"• <code>@{bot_username} collection.USER_ID</code> — View a user's harem\n"
                    f"• <code>@{bot_username} collection.USER_ID.AMV</code> — Filter by rarity\n"
                    f"• <code>@{bot_username} collection.USER_ID Naruto</code> — Search by name\n"
                    f"• <code>@{bot_username} whohas CHAR_ID</code> — Who owns a character\n"
                    f"• <code>@{bot_username} CharacterName</code> — Search global DB\n"
                    f"• <code>@{bot_username} myinfo</code> — Share your profile card"
                )
                guide_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🎒 My Harem", switch_inline_query_current_chat=f"collection.{user_id}"),
                        InlineKeyboardButton(text="👤 My Profile", switch_inline_query_current_chat="myinfo")
                    ],
                    [
                        InlineKeyboardButton(text="🎮 Play AniVerse", url=f"https://t.me/{bot_username}?start=help")
                    ]
                ])
                results.append(
                    InlineQueryResultArticle(
                        id="guide_inline_mode",
                        title="🔍 Bot Inline Mode (How to Use)",
                        description="Tap to send or view inline search commands guide",
                        thumbnail_url=DEFAULT_THUMB,
                        input_message_content=InputTextMessageContent(
                            message_text=guide_text,
                            parse_mode="HTML"
                        ),
                        reply_markup=guide_kb
                    )
                )

                # Article 2: Quick My Profile Card shortcut
                try:
                    user_obj = await get_or_create_user(db, user_id, inline_query.from_user.username, inline_query.from_user.first_name)
                    p_text = await build_profile_card(user_obj, db)
                    p_cap = make_safe_caption(p_text, max_limit=1020)
                    p_cover = await get_user_harem_cover(user_obj, db) or DEFAULT_THUMB
                    p_kb = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🎒 View Harem", switch_inline_query_current_chat=f"collection.{user_id}"),
                            InlineKeyboardButton(text="🎴 Profile", url=f"https://t.me/{bot_username}?start=profile")
                        ]
                    ])
                    p_item = build_inline_item(
                        item_id=f"quick_myinfo_{user_id}",
                        img_val=p_cover,
                        title=f"👤 Share My Profile Card ({clean_html_entities(user_obj.first_name or 'Trainer')})",
                        clean_anime=f"Balance: {user_obj.coins:,} Coins • Tap to share",
                        caption=p_cap,
                        reply_markup=p_kb
                    )
                    if p_item:
                        results.append(p_item)
                except Exception as ex:
                    logger.warning(f"Error generating quick myinfo: {ex}")

            # Browse global characters
            stmt = select(Character).order_by(Character.id).offset(offset).limit(limit)
            res = await db.execute(stmt)
            chars = res.scalars().all()

            for idx, char in enumerate(chars):
                r_emoji = get_rarity_emoji(char.rarity)
                img_val = char.image_url if char.image_url else DEFAULT_THUMB
                clean_name = clean_html_entities(char.name)
                clean_anime = clean_html_entities(char.anime)
                clean_rarity = clean_html_entities(char.rarity)

                caption = (
                    f"🌟 <b>{escape_html(char.name)}</b> [{r_emoji}]\n"
                    f"{get_emoji('id')} <b>ID:</b> #{char.id:03d}\n"
                    f"{get_emoji('tv')} <b>Anime:</b> {escape_html(char.anime)}\n"
                    f"{get_emoji('gem')} <b>Rarity:</b> {r_emoji} {char.rarity}\n"
                    f"🤖 <b>Bot:</b> @{bot_username}"
                )
                safe_cap = make_safe_caption(caption, max_limit=1020)
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="👥 Who Has It", callback_data=f"who_has_{char.id}"),
                        InlineKeyboardButton(text="🔍 Search More", switch_inline_query_current_chat="")
                    ]
                ])
                item_id = f"char_{char.id}_{offset}_{idx}"
                item = build_inline_item(item_id, img_val, f"{clean_rarity} — {clean_name}", clean_anime, safe_cap, char.rarity, reply_markup=kb)
                if item:
                    results.append(item)

        # =========================================================
        # 2. MYINFO — Share personal profile card
        # =========================================================
        elif query.lower() == "myinfo":
            try:
                user_obj = await get_or_create_user(db, user_id, inline_query.from_user.username, inline_query.from_user.first_name)
                p_text = await build_profile_card(user_obj, db)
                p_cap = make_safe_caption(p_text, max_limit=1020)
                p_cover = await get_user_harem_cover(user_obj, db) or DEFAULT_THUMB
                p_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🎒 View Harem", switch_inline_query_current_chat=f"collection.{user_id}"),
                        InlineKeyboardButton(text="🎴 Profile", url=f"https://t.me/{bot_username}?start=profile")
                    ]
                ])

                # 1) Photo / media card result
                photo_item = build_inline_item(
                    item_id=f"myinfo_photo_{user_id}",
                    img_val=p_cover,
                    title=f"👤 My Profile Card — {clean_html_entities(user_obj.first_name or 'Trainer')}",
                    clean_anime=f"Balance: {user_obj.coins:,} Coins • Tap to share profile card",
                    caption=p_cap,
                    reply_markup=p_kb
                )
                if photo_item:
                    results.append(photo_item)

                # 2) Full text article option
                results.append(
                    InlineQueryResultArticle(
                        id=f"myinfo_text_{user_id}",
                        title="📋 My Profile Card (Text Only)",
                        description="Share full profile stats text without cover photo",
                        thumbnail_url=DEFAULT_THUMB,
                        input_message_content=InputTextMessageContent(
                            message_text=p_text,
                            parse_mode="HTML"
                        ),
                        reply_markup=p_kb
                    )
                )
            except Exception as e:
                logger.error(f"Error building myinfo result: {e}", exc_info=True)

        # =========================================================
        # 3. WHOHAS CHAR_ID / Name — Who owns a character
        # =========================================================
        elif query.lower().startswith("whohas") or query.lower().startswith("who_has"):
            prefix = "whohas" if query.lower().startswith("whohas") else "who_has"
            arg = query[len(prefix):].strip().lstrip("#").strip()

            if not arg:
                results.append(
                    InlineQueryResultArticle(
                        id="whohas_help",
                        title="👥 Who Has It? (Character Owners Lookup)",
                        description=f"Usage: @{bot_username} whohas <id or name> (e.g. whohas 818)",
                        thumbnail_url=DEFAULT_THUMB,
                        input_message_content=InputTextMessageContent(
                            message_text=(
                                f"🔍 <b>Who Has Character Lookup</b>\n\n"
                                f"Type a character ID or name in inline mode to view owners:\n"
                                f"• <code>@{bot_username} whohas 818</code>\n"
                                f"• <code>@{bot_username} whohas Rias Gremory</code>"
                            ),
                            parse_mode="HTML"
                        )
                    )
                )
            elif arg.isdigit():
                char_id = int(arg)
                c_stmt = select(Character).where(Character.id == char_id)
                c_res = await db.execute(c_stmt)
                char = c_res.scalar_one_or_none()

                if not char:
                    results.append(
                        InlineQueryResultArticle(
                            id=f"whohas_none_{char_id}",
                            title=f"Character #{char_id} Not Found",
                            description="No character found in database with this ID.",
                            thumbnail_url=DEFAULT_THUMB,
                            input_message_content=InputTextMessageContent(
                                message_text=f"❌ No character found with ID <b>#{char_id}</b>.",
                                parse_mode="HTML"
                            )
                        )
                    )
                else:
                    # Query top owners
                    o_stmt = (
                        select(User.first_name, User.user_id, func.count(UserCharacter.id).label("cnt"))
                        .join(UserCharacter, UserCharacter.user_id == User.user_id)
                        .where(UserCharacter.character_id == char.id)
                        .group_by(User.user_id)
                        .order_by(func.count(UserCharacter.id).desc())
                        .limit(15)
                    )
                    o_res = await db.execute(o_stmt)
                    rows = o_res.all()

                    total_copies_res = await db.execute(select(func.count(UserCharacter.id)).where(UserCharacter.character_id == char.id))
                    total_copies = total_copies_res.scalar() or 0

                    if rows:
                        owner_lines = [f"{idx}. {escape_html(f_name)} ×{cnt}" for idx, (f_name, u_id, cnt) in enumerate(rows, 1)]
                        owners_text = "\n".join(owner_lines)
                    else:
                        owners_text = "<i>Nobody owns this character yet!</i>"

                    r_emoji = get_rarity_emoji(char.rarity)
                    clean_name = clean_html_entities(char.name)
                    clean_anime = clean_html_entities(char.anime)
                    clean_rarity = clean_html_entities(char.rarity)

                    caption = (
                        f"👾 <b>Character Info</b>\n\n"
                        + format_blockquote(
                            f"{get_emoji('id')} <b>ID:</b> #{char.id}\n"
                            f"{get_emoji('user')} <b>Name:</b> {escape_html(char.name)}\n"
                            f"🍿 <b>Anime:</b> {escape_html(char.anime)}\n"
                            f"🎬 <b>Rarity:</b> {r_emoji} {char.rarity}\n"
                            f"👥 <b>Total Owners:</b> {len(rows)} (Copies: {total_copies})"
                        )
                        + f"\n\n🎦 <b>Who has this character :</b>\n"
                        + format_blockquote(owners_text)
                    )
                    safe_cap = make_safe_caption(caption, max_limit=1020)
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="👥 Who Has It", callback_data=f"who_has_{char.id}"),
                            InlineKeyboardButton(text="🔍 Search More", switch_inline_query_current_chat="")
                        ]
                    ])
                    item = build_inline_item(
                        item_id=f"whohas_{char.id}",
                        img_val=char.image_url if char.image_url else DEFAULT_THUMB,
                        title=f"Who Has: {clean_name} (#{char.id})",
                        clean_anime=f"{clean_anime} • {len(rows)} Owner(s) • Total: {total_copies}",
                        caption=safe_cap,
                        rarity=char.rarity,
                        reply_markup=kb
                    )
                    if item:
                        results.append(item)
            else:
                # Name search for whohas
                c_stmt = (
                    select(Character)
                    .where(
                        (Character.name.ilike(f"%{arg}%")) |
                        (Character.anime.ilike(f"%{arg}%"))
                    )
                    .order_by(Character.id)
                    .offset(offset)
                    .limit(limit)
                )
                c_res = await db.execute(c_stmt)
                chars = c_res.scalars().all()

                if not chars and offset == 0:
                    results.append(
                        InlineQueryResultArticle(
                            id=f"whohas_no_match_{arg[:15]}",
                            title=f"No characters matching '{arg}'",
                            description="Try searching with a character ID or another name",
                            thumbnail_url=DEFAULT_THUMB,
                            input_message_content=InputTextMessageContent(
                                message_text=f"🔍 No characters found matching <b>{escape_html(arg)}</b>.",
                                parse_mode="HTML"
                            )
                        )
                    )

                for idx, char in enumerate(chars):
                    o_stmt = (
                        select(User.first_name, User.user_id, func.count(UserCharacter.id).label("cnt"))
                        .join(UserCharacter, UserCharacter.user_id == User.user_id)
                        .where(UserCharacter.character_id == char.id)
                        .group_by(User.user_id)
                        .order_by(func.count(UserCharacter.id).desc())
                        .limit(10)
                    )
                    o_res = await db.execute(o_stmt)
                    rows = o_res.all()

                    total_copies_res = await db.execute(select(func.count(UserCharacter.id)).where(UserCharacter.character_id == char.id))
                    total_copies = total_copies_res.scalar() or 0

                    if rows:
                        owner_lines = [f"{i}. {escape_html(f_name)} ×{cnt}" for i, (f_name, u_id, cnt) in enumerate(rows, 1)]
                        owners_text = "\n".join(owner_lines)
                    else:
                        owners_text = "<i>Nobody owns this character yet!</i>"

                    r_emoji = get_rarity_emoji(char.rarity)
                    clean_name = clean_html_entities(char.name)
                    clean_anime = clean_html_entities(char.anime)
                    clean_rarity = clean_html_entities(char.rarity)

                    caption = (
                        f"👾 <b>Character Info</b>\n\n"
                        + format_blockquote(
                            f"{get_emoji('id')} <b>ID:</b> #{char.id}\n"
                            f"{get_emoji('user')} <b>Name:</b> {escape_html(char.name)}\n"
                            f"🍿 <b>Anime:</b> {escape_html(char.anime)}\n"
                            f"🎬 <b>Rarity:</b> {r_emoji} {char.rarity}\n"
                            f"👥 <b>Total Owners:</b> {len(rows)} (Copies: {total_copies})"
                        )
                        + f"\n\n🎦 <b>Who has this character :</b>\n"
                        + format_blockquote(owners_text)
                    )
                    safe_cap = make_safe_caption(caption, max_limit=1020)
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="👥 Who Has It", callback_data=f"who_has_{char.id}"),
                            InlineKeyboardButton(text="🔍 Search More", switch_inline_query_current_chat="")
                        ]
                    ])
                    item = build_inline_item(
                        item_id=f"whohas_{char.id}_{offset}_{idx}",
                        img_val=char.image_url if char.image_url else DEFAULT_THUMB,
                        title=f"Who Has: {clean_name} (#{char.id})",
                        clean_anime=f"{clean_anime} • {len(rows)} Owner(s) (Total: {total_copies})",
                        caption=safe_cap,
                        rarity=char.rarity,
                        reply_markup=kb
                    )
                    if item:
                        results.append(item)

        # =========================================================
        # 4. COLLECTION — Harem lookup (by User ID, rarity, and/or name)
        # =========================================================
        elif (
            query.lower().startswith("collection.")
            or query.lower().startswith("collection ")
            or query.lower() == "collection"
            or query.lower().startswith("col.")
            or query.lower().startswith("col ")
            or query.lower() == "col"
        ):
            parts_space = query.split(maxsplit=1)
            first_part = parts_space[0]
            name_filter = parts_space[1].strip() if len(parts_space) > 1 else ""

            if first_part.lower().startswith("collection."):
                tail = first_part[len("collection."):]
            elif first_part.lower().startswith("collection"):
                tail = first_part[len("collection"):].lstrip(".")
            elif first_part.lower().startswith("col."):
                tail = first_part[len("col."):]
            else:
                tail = first_part[len("col"):].lstrip(".")

            dot_parts = [p.strip() for p in tail.split(".") if p.strip()] if tail else []
            target_user_id = user_id
            rarity_filter = None

            if len(dot_parts) >= 1:
                if dot_parts[0].isdigit():
                    target_user_id = int(dot_parts[0])
                    if len(dot_parts) >= 2:
                        rarity_filter = dot_parts[1]
                else:
                    candidate = dot_parts[0].upper()
                    if candidate in ("AMV", "COMMON", "RARE", "EPIC", "LEGENDARY", "MYTHICAL", "EXPENSIVE", "EXCLUSIVE"):
                        rarity_filter = dot_parts[0]
                    else:
                        if not name_filter:
                            name_filter = dot_parts[0]

            # Fetch owner information
            u_stmt = select(User).where(User.user_id == target_user_id)
            u_res = await db.execute(u_stmt)
            owner = u_res.scalar_one_or_none()
            owner_name = escape_html(owner.first_name) if (owner and owner.first_name) else f"Trainer {target_user_id}"
            owner_mention = f'<a href="tg://user?id={target_user_id}">{owner_name}</a>'

            stmt = (
                select(Character, func.count(UserCharacter.id).label("cnt"))
                .join(UserCharacter, UserCharacter.character_id == Character.id)
                .where(UserCharacter.user_id == target_user_id)
            )

            if rarity_filter and rarity_filter.upper() != "ALL":
                stmt = stmt.where(Character.rarity.ilike(rarity_filter))

            if name_filter:
                stmt = stmt.where(
                    (Character.name.ilike(f"%{name_filter}%")) |
                    (Character.anime.ilike(f"%{name_filter}%"))
                )

            stmt = stmt.group_by(Character.id).order_by(Character.id).offset(offset).limit(limit)
            res = await db.execute(stmt)
            rows = res.all()

            if not rows and offset == 0:
                empty_desc = []
                if rarity_filter and rarity_filter.upper() != "ALL":
                    empty_desc.append(f"Rarity: {rarity_filter}")
                if name_filter:
                    empty_desc.append(f"Name: '{name_filter}'")
                desc_str = f" ({', '.join(empty_desc)})" if empty_desc else ""
                msg_text = f"No characters found in collection{desc_str}!"

                results.append(
                    InlineQueryResultArticle(
                        id=f"empty_col_{target_user_id}",
                        title=msg_text,
                        description=f"{owner_name}'s collection",
                        thumbnail_url=DEFAULT_THUMB,
                        input_message_content=InputTextMessageContent(
                            message_text=f"🎒 <b>{owner_mention}'s Collection</b>\n\n{msg_text}",
                            parse_mode="HTML"
                        )
                    )
                )

            for idx, (char, cnt) in enumerate(rows):
                r_emoji = get_rarity_emoji(char.rarity)
                img_val = char.image_url if char.image_url else DEFAULT_THUMB
                clean_name = clean_html_entities(char.name)
                clean_anime = clean_html_entities(char.anime)
                clean_rarity = clean_html_entities(char.rarity)

                count_str = f" ×{cnt}" if cnt > 1 else ""
                caption = (
                    f"🌟 <b>{escape_html(char.name)}</b> [{r_emoji}]{count_str}\n"
                    f"{get_emoji('id')} <b>ID:</b> #{char.id:03d}\n"
                    f"{get_emoji('tv')} <b>Anime:</b> {escape_html(char.anime)}\n"
                    f"{r_emoji} <b>Rarity:</b> {char.rarity}\n"
                    f"{get_emoji('crown')} <b>Owner:</b> {owner_mention}"
                )
                safe_cap = make_safe_caption(caption, max_limit=1020)
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="👥 Who Has It", callback_data=f"who_has_{char.id}"),
                        InlineKeyboardButton(text="🎒 View Harem", switch_inline_query_current_chat=f"collection.{target_user_id}")
                    ]
                ])

                title = f"{clean_rarity} — {clean_name}{count_str}"
                item_id = f"item_{char.id}_{offset}_{idx}"
                item = build_inline_item(item_id, img_val, title, clean_anime, safe_cap, char.rarity, filter_mode=rarity_filter or "", reply_markup=kb)
                if item:
                    results.append(item)

        # =========================================================
        # 5. GLOBAL CHARACTER SEARCH — CharacterName, Anime, or ID
        # =========================================================
        else:
            search_query = query
            if search_query.isdigit():
                num_id = int(search_query)
                stmt = select(Character).where(
                    (Character.id == num_id) |
                    (Character.name.ilike(f"%{search_query}%")) |
                    (Character.anime.ilike(f"%{search_query}%"))
                ).order_by(
                    case((Character.id == num_id, 0), else_=1),
                    Character.id
                )
            elif search_query.lower() == "amv":
                stmt = select(Character).where(Character.rarity.ilike("AMV")).order_by(Character.id)
            else:
                stmt = select(Character).where(
                    (Character.name.ilike(f"%{search_query}%")) |
                    (Character.anime.ilike(f"%{search_query}%"))
                ).order_by(Character.id)

            stmt = stmt.offset(offset).limit(limit)
            res = await db.execute(stmt)
            chars = res.scalars().all()

            if not chars and offset == 0:
                results.append(
                    InlineQueryResultArticle(
                        id=f"no_results_{search_query[:15]}",
                        title="No characters found",
                        description=f"No matches for '{search_query}'",
                        thumbnail_url=DEFAULT_THUMB,
                        input_message_content=InputTextMessageContent(
                            message_text=f"🔍 No characters found matching <b>{escape_html(search_query)}</b>.",
                            parse_mode="HTML"
                        )
                    )
                )

            for idx, char in enumerate(chars):
                r_emoji = get_rarity_emoji(char.rarity)
                img_val = char.image_url if char.image_url else DEFAULT_THUMB
                clean_name = clean_html_entities(char.name)
                clean_anime = clean_html_entities(char.anime)
                clean_rarity = clean_html_entities(char.rarity)

                caption = (
                    f"🌟 <b>{escape_html(char.name)}</b> [{r_emoji}]\n"
                    f"{get_emoji('id')} <b>ID:</b> #{char.id:03d}\n"
                    f"{get_emoji('tv')} <b>Anime:</b> {escape_html(char.anime)}\n"
                    f"{get_emoji('gem')} <b>Rarity:</b> {r_emoji} {char.rarity}\n"
                    f"🤖 <b>Bot:</b> @{bot_username}"
                )
                safe_cap = make_safe_caption(caption, max_limit=1020)
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="👥 Who Has It", callback_data=f"who_has_{char.id}"),
                        InlineKeyboardButton(text="🔍 Search More", switch_inline_query_current_chat="")
                    ]
                ])

                title = f"{clean_rarity} — {clean_name}"
                item_id = f"search_{char.id}_{offset}_{idx}"
                item = build_inline_item(item_id, img_val, title, clean_anime, safe_cap, char.rarity, reply_markup=kb)
                if item:
                    results.append(item)

    # Set next_offset if full page was returned to enable infinite scroll
    next_offset = str(offset + limit) if len(results) >= limit else ""

    try:
        await inline_query.answer(results, cache_time=1, is_personal=True, next_offset=next_offset)
    except Exception as e:
        logger.error(f"Error answering inline query: {e}", exc_info=True)
