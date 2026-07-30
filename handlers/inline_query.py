import logging
from aiogram import Router, F
from aiogram.types import (
    InlineQuery, 
    InlineQueryResultPhoto, 
    InlineQueryResultCachedPhoto, 
    InlineQueryResultCachedVideo, 
    InlineQueryResultArticle, 
    InputTextMessageContent
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import html
from database.database import AsyncSessionLocal
from database.models import User, UserCharacter, Character
from utils.formatters import get_rarity_emoji, escape_html

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

def build_inline_item(item_id: str, img_val: str, title: str, clean_anime: str, caption: str, rarity: str, filter_mode: str):
    """Safely builds appropriate InlineQueryResult based on image URL / Telegram file ID type."""
    if img_val.startswith("http"):
        if is_valid_url(img_val):
            return InlineQueryResultPhoto(
                id=item_id,
                photo_url=img_val,
                thumbnail_url=img_val,
                title=title,
                description=clean_anime,
                caption=caption,
                parse_mode="HTML"
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
                )
            )
    
    # Telegram file ID logic
    is_video = (
        img_val.startswith(("BAAC", "BAAD", "CgAC", "CGAC", "BQAC", "DQAC")) or 
        filter_mode == "AMV" or 
        rarity.lower() == "amv"
    )
    
    if is_video:
        try:
            return InlineQueryResultCachedVideo(
                id=item_id,
                video_file_id=img_val,
                title=title,
                description=clean_anime,
                caption=caption,
                parse_mode="HTML"
            )
        except Exception:
            pass

    try:
        return InlineQueryResultCachedPhoto(
            id=item_id,
            photo_file_id=img_val,
            title=title,
            description=clean_anime,
            caption=caption,
            parse_mode="HTML"
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
        )
    )

@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    query = inline_query.query.strip()
    results = []
    user_id = inline_query.from_user.id

    is_collection = False
    filter_mode = "ALL"
    search_query = ""

    # Parse query type
    if query.startswith("collection."):
        is_collection = True
        parts = query.split(".")
        user_id_str = parts[1] if len(parts) > 1 else ""
        if user_id_str.isdigit():
            user_id = int(user_id_str)
        filter_mode = parts[2].upper() if len(parts) > 2 else "ALL"
    else:
        is_collection = False
        search_query = query

    # Pagination settings (limit = 25 per page for fast & smooth Telegram scroll)
    offset = int(inline_query.offset) if inline_query.offset and inline_query.offset.isdigit() else 0
    limit = 25

    async with AsyncSessionLocal() as db:
        if is_collection:
            # Query specific User's Harem Collection
            u_stmt = select(User).where(User.user_id == user_id)
            u_res = await db.execute(u_stmt)
            owner = u_res.scalar_one_or_none()
            owner_name = escape_html(owner.first_name) if (owner and owner.first_name) else "Trainer"
            owner_mention = f'<a href="tg://user?id={user_id}">{owner_name}</a>'

            stmt = (
                select(Character, func.count(UserCharacter.id).label("cnt"))
                .join(UserCharacter, UserCharacter.character_id == Character.id)
                .where(UserCharacter.user_id == user_id)
            )

            if filter_mode == "AMV":
                stmt = stmt.where(Character.rarity.ilike("AMV"))

            stmt = stmt.group_by(Character.id).order_by(Character.id)
            stmt = stmt.offset(offset).limit(limit)
            res = await db.execute(stmt)
            rows = res.all()

            if not rows and offset == 0:
                msg_text = "No AMV characters found in collection!" if filter_mode == "AMV" else "Collection is empty!"
                results.append(
                    InlineQueryResultArticle(
                        id="empty_collection",
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

                caption = (
                    f"🌟 <b>{escape_html(char.name)}</b> [{r_emoji}]\n"
                    f"🆔 <b>ID:</b> #{char.id:03d}\n"
                    f"📺 <b>Anime:</b> {escape_html(char.anime)}\n"
                    f"{r_emoji} <b>Rarity:</b> {char.rarity}\n"
                    f"👑 <b>Owner:</b> {owner_mention}"
                )

                clean_name = clean_html_entities(char.name)
                clean_anime = clean_html_entities(char.anime)
                clean_rarity = clean_html_entities(char.rarity)

                title = f"AMV — {clean_name}" if filter_mode == "AMV" else f"{clean_rarity} — {clean_name}"
                item_id = f"item_{char.id}_{offset}_{idx}"

                try:
                    res_item = build_inline_item(item_id, img_val, title, clean_anime, caption, char.rarity, filter_mode)
                    if res_item:
                        results.append(res_item)
                except Exception as e:
                    logger.error(f"Error building inline item {char.id}: {e}")

        else:
            # Global Character Database Search
            if search_query == "":
                stmt = select(Character).order_by(Character.id)
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
                        id="no_results",
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

                caption = (
                    f"🌟 <b>{escape_html(char.name)}</b> [{r_emoji}]\n"
                    f"🆔 <b>ID:</b> #{char.id:03d}\n"
                    f"📺 <b>Anime:</b> {escape_html(char.anime)}\n"
                    f"💎 <b>Rarity:</b> {r_emoji} {char.rarity}\n"
                    f"🤖 <b>Bot:</b> @AniVerse1bot"
                )

                clean_name = clean_html_entities(char.name)
                clean_anime = clean_html_entities(char.anime)
                clean_rarity = clean_html_entities(char.rarity)
                title = f"{clean_rarity} — {clean_name}"
                item_id = f"search_{char.id}_{offset}_{idx}"

                try:
                    res_item = build_inline_item(item_id, img_val, title, clean_anime, caption, char.rarity, filter_mode)
                    if res_item:
                        results.append(res_item)
                except Exception as e:
                    logger.error(f"Error building search item {char.id}: {e}")

    # Set next_offset if full page was returned to enable infinite scroll
    next_offset = str(offset + limit) if len(results) == limit else ""

    try:
        await inline_query.answer(results, cache_time=1, is_personal=True, next_offset=next_offset)
    except Exception as e:
        logger.error(f"Error answering inline query: {e}", exc_info=True)


