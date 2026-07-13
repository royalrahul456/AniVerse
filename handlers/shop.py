from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InputMediaVideo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import User, Character, UserCharacter
from utils.formatters import format_blockquote, get_rarity_emoji, escape_html
from keyboards.inline import get_back_to_hub_keyboard
from handlers.start import get_or_create_user
from utils.settings import get_cover_media

router = Router()

THEMES = {
    "sakura": {"name": "Sakura Theme", "price": 50000, "emoji": "🌸", "description": "Beautiful pink sakura blossoms and pink frame accents."},
    "cosmic": {"name": "Cosmic Theme", "price": 75000, "emoji": "🌌", "description": "Starry space aesthetics with celestial frame accents."},
    "gold": {"name": "Gold VIP Theme", "price": 100000, "emoji": "👑", "description": "Shining gold crown borders and golden frame accents."},
    "dark": {"name": "Dark Knight Theme", "price": 120000, "emoji": "🦇", "description": "Dark gothic aesthetic with bat accents and black frame."},
    "cyber": {"name": "Neon Cyber Theme", "price": 150000, "emoji": "👾", "description": "Vibrant neon cyan and purple futuristic grid design."},
    "phoenix": {"name": "Phoenix Theme", "price": 200000, "emoji": "🐦‍🔥", "description": "Blazing fire crimson borders and phoenix emblem accents."}
}

async def send_or_edit_shop(message_obj, cover_media: str, text: str, reply_markup, is_callback: bool):
    if is_callback:
        if message_obj.photo or message_obj.video or message_obj.animation:
            try:
                await message_obj.edit_caption(caption=text, reply_markup=reply_markup, parse_mode="HTML")
                return
            except Exception:
                pass
        try:
            await message_obj.edit_media(InputMediaPhoto(media=cover_media, caption=text, parse_mode="HTML"), reply_markup=reply_markup)
            return
        except Exception:
            try:
                await message_obj.edit_media(InputMediaVideo(media=cover_media, caption=text, parse_mode="HTML"), reply_markup=reply_markup)
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

@router.callback_query(F.data == "dm_shop")
@router.message(Command("shop"))
async def cmd_shop(event, db: AsyncSession):
    import logging
    is_callback = isinstance(event, CallbackQuery)
    logging.getLogger(__name__).info(f"cmd_shop called! Event type: {type(event)}, User: {event.from_user.id}, Username: {event.from_user.username}")
    user_id = event.from_user.id
    user_fname = event.from_user.first_name
    user_uname = event.from_user.username
    
    user = await get_or_create_user(db, user_id, user_uname, user_fname)
    unlocked = [t.strip().lower() for t in (user.unlocked_themes or "default").split(",")]

    text = (
        "🎨 <b>AniVerse Custom Profile Themes</b>\n\n"
        + format_blockquote(
            "Give your trainer profile card a premium aesthetic makeover! Once purchased, you can apply themes using the <code>/settheme</code> command or from your profile.\n\n"
            "🌸 <b>Sakura Theme:</b> 50,000 coins (50k)\n"
            "🌌 <b>Cosmic Theme:</b> 75,000 coins (75k)\n"
            "👑 <b>Gold VIP Theme:</b> 100,000 coins (100k)\n"
            "🦇 <b>Dark Knight Theme:</b> 120,000 coins (120k)\n"
            "👾 <b>Neon Cyber Theme:</b> 150,000 coins (150k)\n"
            "🐦‍🔥 <b>Phoenix Theme:</b> 200,000 coins (200k)\n\n"
            f"💰 <b>Your Coins:</b> {user.coins:,} coins"
        )
    )

    message_obj = event.message if is_callback else event
    is_group = message_obj.chat.type != "private"

    builder = InlineKeyboardBuilder()
    for key, info in THEMES.items():
        if key in unlocked:
            label = f"{info['emoji']} {info['name']} (Unlocked)"
            builder.row(InlineKeyboardButton(text=label, callback_data="noop"))
        else:
            label = f"{info['emoji']} Buy {info['name']} ({info['price']//1000}k)"
            builder.row(InlineKeyboardButton(text=label, callback_data=f"buy_theme_{key}"))
            
    if is_group:
        builder.row(InlineKeyboardButton(text="🗑️ Close Shop", callback_data="close_menu"))
    else:
        builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))
        
    kb = builder.as_markup()
    cover_media = get_cover_media("start")
    if is_callback:
        await send_or_edit_shop(event.message, cover_media, text, kb, is_callback=True)
        await event.answer()
    else:
        await send_or_edit_shop(event, cover_media, text, kb, is_callback=False)

@router.callback_query(F.data.startswith("buy_theme_"))
async def cb_buy_theme(callback: CallbackQuery, db: AsyncSession):
    theme_key = callback.data.replace("buy_theme_", "")
    theme_info = THEMES.get(theme_key)
    if not theme_info:
        await callback.answer("Invalid theme selection!", show_alert=True)
        return

    user = await get_or_create_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    unlocked = [t.strip().lower() for t in (user.unlocked_themes or "default").split(",") if t.strip()]

    if theme_key in unlocked:
        await callback.answer("❌ You have already unlocked this theme!", show_alert=True)
        return

    if user.coins < theme_info["price"]:
        await callback.answer(f"❌ You need {theme_info['price']:,} coins! Balance: {user.coins:,}", show_alert=True)
        return

    user.coins -= theme_info["price"]
    unlocked.append(theme_key)
    user.unlocked_themes = ",".join(unlocked)
    user.selected_theme = theme_key
    await db.commit()

    await callback.answer(f"🎉 Unlocked & Applied {theme_info['name']} successfully!", show_alert=True)
    await cmd_shop(callback, db)

@router.callback_query(F.data == "close_menu")
async def cb_close_menu(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
