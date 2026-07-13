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

router = Router()

DEFAULT_THUMB = "https://cdn.pixabay.com/photo/2022/12/01/04/35/anime-7628313_1280.jpg"

@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    query = inline_query.query.strip()
    results = []

    if query.startswith("collection."):
        parts = query.split(".")
        user_id_str = parts[1] if len(parts) > 1 else ""
        filter_mode = parts[2].upper() if len(parts) > 2 else "ALL"

        if user_id_str.isdigit():
            user_id = int(user_id_str)
            async with AsyncSessionLocal() as db:
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
                res = await db.execute(stmt)
                rows = res.all()

                if filter_mode == "AMV" and not rows:
                    fallback_stmt = (
                        select(Character, func.count(UserCharacter.id).label("cnt"))
                        .join(UserCharacter, UserCharacter.character_id == Character.id)
                        .where(UserCharacter.user_id == user_id)
                        .group_by(Character.id)
                        .order_by(Character.id)
                    )
                    rows = (await db.execute(fallback_stmt)).all()

                for idx, (char, cnt) in enumerate(rows[:50]):
                    r_emoji = get_rarity_emoji(char.rarity)
                    img_val = char.image_url if char.image_url else DEFAULT_THUMB

                    caption = (
                        f"🌟 <b>{escape_html(char.name)}</b> [{r_emoji}]\n"
                        f"🆔 <b>ID:</b> #{char.id}\n"
                        f"📺 <b>Anime:</b> {escape_html(char.anime)}\n"
                        f"{r_emoji} <b>Rarity:</b> {char.rarity}\n"
                        f"👑 <b>Owner:</b> {owner_mention}"
                    )

                    clean_name = html.unescape(char.name)
                    clean_anime = html.unescape(char.anime)
                    clean_rarity = html.unescape(char.rarity)

                    if filter_mode == "AMV":
                        title = f"AMV — {clean_name}"
                    else:
                        title = f"{clean_rarity} — {clean_name}"

                    item_id = f"item_{char.id}_{idx}"

                    if img_val.startswith("http"):
                        results.append(
                            InlineQueryResultPhoto(
                                id=item_id,
                                photo_url=img_val,
                                thumbnail_url=img_val,
                                title=title,
                                caption=caption,
                                parse_mode="HTML"
                            )
                        )
                    else:
                        if filter_mode == "AMV" or char.rarity.lower() == "amv":
                            try:
                                results.append(
                                    InlineQueryResultCachedVideo(
                                        id=item_id,
                                        video_file_id=img_val,
                                        title=title,
                                        caption=caption,
                                        parse_mode="HTML"
                                    )
                                )
                            except Exception:
                                results.append(
                                    InlineQueryResultArticle(
                                        id=item_id,
                                        title=title,
                                        description=clean_anime,
                                        thumbnail_url=DEFAULT_THUMB,
                                        input_message_content=InputTextMessageContent(
                                            message_text=caption,
                                            parse_mode="HTML"
                                        )
                                    )
                                )
                        else:
                            try:
                                results.append(
                                    InlineQueryResultCachedPhoto(
                                        id=item_id,
                                        photo_file_id=img_val,
                                        title=title,
                                        caption=caption,
                                        parse_mode="HTML"
                                    )
                                )
                            except Exception:
                                results.append(
                                    InlineQueryResultArticle(
                                        id=item_id,
                                        title=title,
                                        description=clean_anime,
                                        thumbnail_url=DEFAULT_THUMB,
                                        input_message_content=InputTextMessageContent(
                                            message_text=caption,
                                            parse_mode="HTML"
                                        )
                                    )
                                )

    try:
        await inline_query.answer(results, cache_time=5, is_personal=True)
    except Exception:
        pass
