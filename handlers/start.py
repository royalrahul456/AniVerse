import time
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import User
from utils.formatters import format_blockquote, escape_html
from utils.settings import get_cover_media

START_TIME = time.time()
router = Router()

async def get_or_create_user(session: AsyncSession, user_id: int, username: str = "", first_name: str = "") -> User:
    stmt = select(User).where(User.user_id == user_id)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        fname = first_name if first_name else "Trainer"
        user = User(user_id=user_id, username=username, first_name=fname, coins=500)
        session.add(user)
        await session.commit()
    else:
        updated = False
        if username and user.username != username:
            user.username = username
            updated = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updated = True
        if updated:
            await session.commit()
    return user

@router.message(CommandStart())
async def cmd_start(message: Message, db: AsyncSession):
    # Ensure user is registered in db
    await get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    cover_media = get_cover_media("start")
    bot_info = await message.bot.get_me()
    
    caption = (
        "🎉 <b>Welcome to AniVerse Universe!</b>\n\n"
        + format_blockquote(
            "Snatch anime characters, build your harem,\n"
            "earn coins, and dominate the leaderboards!\n\n"
            "Use /help to see all commands!"
        )
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Add to your GC", url=f"https://t.me/{bot_info.username}?startgroup=true"))
    
    await send_or_edit_start(message, cover_media, caption, builder.as_markup(), is_callback=False)

async def send_or_edit_start(message_obj, cover_media: str, text: str, reply_markup, is_callback: bool):
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

@router.callback_query(F.data == "dm_home")
async def cb_dm_home(callback: CallbackQuery, db: AsyncSession):
    bot_info = await callback.bot.get_me()
    
    caption = (
        "🎉 <b>Welcome to AniVerse Universe!</b>\n\n"
        + format_blockquote(
            "Snatch anime characters, build your harem,\n"
            "earn coins, and dominate the leaderboards!\n\n"
            "Use /help to see all commands!"
        )
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Add to your GC", url=f"https://t.me/{bot_info.username}?startgroup=true"))
    
    await send_or_edit_start(callback.message, get_cover_media("start"), caption, builder.as_markup(), is_callback=True)
    await callback.answer()

@router.callback_query(F.data == "dm_help")
async def cb_dm_help(callback: CallbackQuery):
    from keyboards.inline import get_back_to_hub_keyboard
    is_admin = callback.from_user.id in config.ADMIN_IDS
    text = (
        "❓ <b>AniVerse Guide & Help Center</b>\n\n"
        "╭───「 🎒 Trainer Utilities 」───╮\n"
        "├─➩ /profile — Stats & themes\n"
        "├─➩ /harem — View harem collection\n"
        "├─➩ /leaderboard [type] — Global rankings (coins/catches)\n"
        "├─➩ /check &lt;id&gt; — Character status\n"
        "├─➩ /search &lt;name&gt; — Database lookup\n"
        "├─➩ /anime &lt;show&gt; — Filter by anime\n"
        "├─➩ /fav &lt;id&gt; — Custom harem banner\n"
        "├─➩ /claim — Free daily character\n"
        "╰───────────────────────────╯\n\n"
        "╭───「 🎮 Games & Arcade 」───╮\n"
        "├─➩ /games — Games Center menu\n"
        "├─➩ /spin — Lucky spin wheel\n"
        "├─➩ /daily — Claim daily bonus coins\n"
        "├─➩ /coinflip &lt;bet&gt; &lt;choice&gt;\n"
        "├─➩ /dice &lt;bet&gt; &lt;choice&gt;\n"
        "├─➩ /trivia — Play anime quizzes\n"
        "├─➩ /mines &lt;bet&gt; &lt;mines&gt;\n"
        "├─➩ /scramble — Word puzzle rewards\n"
        "├─➩ /xo &lt;reply&gt; — Play Tic-Tac-Toe\n"
        "╰───────────────────────────╯\n\n"
        "╭───「 🤝 Commerce & Deals 」───╮\n"
        "├─➩ /pay &lt;user&gt; &lt;amount&gt; — Send coins\n"
        "├─➩ /balance — Check coin balance\n"
        "├─➩ /gift &lt;user&gt; &lt;id&gt; — Gift character\n"
        "├─➩ /shop — Buy profile themes\n"
        "├─➩ /trade &lt;your_id&gt; &lt;their_id&gt;\n"
        "├─➩ /redeem &lt;code&gt; — Claim promo code\n"
        "├─➩ /auction &lt;id&gt; &lt;price&gt; — List character\n"
        "├─➩ /bid &lt;auc_id&gt; &lt;amount&gt; — Bid on active\n"
        "├─➩ /cancelauction &lt;auc_id&gt;\n"
        "├─➩ /auctions — View active/queue\n"
        "╰───────────────────────────╯\n\n"        "📌 <i>Keep chatting in group chats to trigger wild character spawns, and type /guess &lt;name&gt; to collect them!</i>"
        + (f"\n\n👑 <b>Owner:</b> Since you are a bot owner, type /ownerhelp to see creator tools!" if is_admin else "")
    )
    await send_or_edit_start(callback.message, get_cover_media("help"), text, get_back_to_hub_keyboard(), is_callback=True)
    await callback.answer()

@router.message(Command("help"))
async def cmd_help(message: Message):
    is_admin = message.from_user.id in config.ADMIN_IDS if message.from_user else False
    text = (
        "❓ <b>AniVerse Guide & Help Center</b>\n\n"
        "╭───「 🎒 Trainer Utilities 」───╮\n"
        "├─➩ /profile — Stats & themes\n"
        "├─➩ /harem — View harem collection\n"
        "├─➩ /leaderboard [type] — Global rankings (coins/catches)\n"
        "├─➩ /check &lt;id&gt; — Character status\n"
        "├─➩ /search &lt;name&gt; — Database lookup\n"
        "├─➩ /anime &lt;show&gt; — Filter by anime\n"
        "├─➩ /fav &lt;id&gt; — Custom harem banner\n"
        "├─➩ /claim — Free daily character\n"
        "╰───────────────────────────╯\n\n"
        "╭───「 🎮 Games & Arcade 」───╮\n"
        "├─➩ /games — Games Center menu\n"
        "├─➩ /spin — Lucky spin wheel\n"
        "├─➩ /daily — Claim daily bonus coins\n"
        "├─➩ /coinflip &lt;bet&gt; &lt;choice&gt;\n"
        "├─➩ /dice &lt;bet&gt; &lt;choice&gt;\n"
        "├─➩ /trivia — Play anime quizzes\n"
        "├─➩ /mines &lt;bet&gt; &lt;mines&gt;\n"
        "├─➩ /scramble — Word puzzle rewards\n"
        "├─➩ /xo &lt;reply&gt; — Play Tic-Tac-Toe\n"
        "╰───────────────────────────╯\n\n"
        "╭───「 🤝 Commerce & Deals 」───╮\n"
        "├─➩ /pay &lt;user&gt; &lt;amount&gt; — Send coins\n"
        "├─➩ /balance — Check coin balance\n"
        "├─➩ /gift &lt;user&gt; &lt;id&gt; — Gift character\n"
        "├─➩ /shop — Buy profile themes\n"
        "├─➩ /trade &lt;your_id&gt; &lt;their_id&gt;\n"
        "├─➩ /redeem &lt;code&gt; — Claim promo code\n"
        "├─➩ /auction &lt;id&gt; &lt;price&gt; — List character\n"
        "├─➩ /bid &lt;auc_id&gt; &lt;amount&gt; — Bid on active\n"
        "├─➩ /cancelauction &lt;auc_id&gt;\n"
        "├─➩ /auctions — View active/queue\n"
        "╰───────────────────────────╯\n\n"        "📌 <i>Keep chatting in group chats to trigger wild character spawns, and type /guess &lt;name&gt; to collect them!</i>"
        + (f"\n\n👑 <b>Owner:</b> Since you are a bot owner, type /ownerhelp to see creator tools!" if is_admin else "")
    )
    
    is_group = message.chat.type != "private"
    builder = InlineKeyboardBuilder()
    if is_group:
        builder.row(InlineKeyboardButton(text="🗑️ Close Guide", callback_data="close_menu"))
    else:
        builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))
        
    await send_or_edit_start(message, get_cover_media("help"), text, builder.as_markup(), is_callback=False)
