from utils.emojis import get_emoji
import time
import datetime
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
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

def get_uptime_str() -> str:
    uptime_seconds = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    
    return " ".join(parts)

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
async def cmd_start(message: Message, state: FSMContext, db: AsyncSession):
    # Ensure user is registered in db
    await get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    parts = message.text.strip().split()
    if len(parts) > 1:
        start_arg = parts[1].strip()
        if start_arg == "addchar":
            message.text = "/addchar"
            from handlers.admin import cmd_addchar
            await cmd_addchar(message, state, db)
            return
        elif start_arg == "editchar":
            message.text = "/editchar"
            from handlers.admin import cmd_editchar
            await cmd_editchar(message, state, db)
            return
    
    cover_media = get_cover_media("start")
    bot_info = await message.bot.get_me()    
    
    # Calculate Ping for start message
    start_ping_time = time.time()
    # Dummy async call to measure ping to telegram servers
    _ = await message.bot.get_me()
    ping_ms = round((time.time() - start_ping_time) * 1000, 2)
    uptime_str = get_uptime_str()
    
    caption = (
        f"🍃 Greetings, I'm <b>AniVerse Bot</b> 🫧\n"
        f"───────── ▨ ─────────\n"
        f"◎ <b>WHERE:</b> I spawn waifus in your chat for users to grab.\n"
        f"◎ <b>HOW TO USE:</b> Add me to your group and use /help for commands.\n"
        f"───────── ▨ ─────────\n"
        f"⚡ <b>PING:</b> {ping_ms} ms\n"
        f"⏳ <b>UPTIME:</b> {uptime_str}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Add to your GC", url=f"https://t.me/{bot_info.username}?startgroup=true"),
        InlineKeyboardButton(text="⚡ Ping", callback_data="ping_bot")
    )
    
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
        f"{get_emoji('party')} <b>Welcome to AniVerse Universe!</b>\n\n"
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

def build_help_text(is_admin: bool) -> str:
    text = (
        "❓ <b>AniVerse Guide & Help Center</b>\n\n"
        "╭───「 🎒 Trainer Utilities 」───╮\n"
        "├─➩ /profile — Stats & themes\n"
        "├─➩ /harem — View harem collection\n"
        "├─➩ /leaderboard [type] — Global rankings (coins/catches)\n"
        "├─➩ /check &lt;id&gt; — Character status & owners\n"
        "├─➩ /search &lt;name&gt; — Database lookup\n"
        "├─➩ /anime &lt;show&gt; — Filter by anime\n"
        "├─➩ /fav &lt;id&gt; — Custom harem cover banner\n"
        "├─➩ /claim — Free daily character\n"
        "╰───────────────────────────╯\n\n"
        "╭───「 🎮 Games & Arcade 」───╮\n"
        "├─➩ /games — Games Center menu\n"
        "├─➩ /spin — Lucky spin wheel\n"
        "├─➩ /daily — Claim daily bonus coins\n"
        "├─➩ /coinflip &lt;bet&gt; &lt;choice&gt; — Bet coins\n"
        "├─➩ /dice &lt;bet&gt; &lt;choice&gt; — Dice roll\n"
        "├─➩ /dart — Animated dart arena\n"
        "├─➩ /trivia — Play anime quizzes\n"
        "├─➩ /mines &lt;bet&gt; &lt;mines&gt; — Mines arcade\n"
        "├─➩ /scramble — Word puzzle rewards\n"
        "├─➩ /xo &lt;reply&gt; — Play Tic-Tac-Toe\n"
        "├─➩ /nameguess — Start manual guessing game\n"
        "├─➩ /togglenameguess — Toggle auto-guessing game loop\n"
        "╰───────────────────────────╯\n\n"
        "╭───「 ⚙️ Group Spawns 」───╮\n"
        "├─➩ /guess &lt;name&gt; — Catch wild character\n"
        "├─➩ /spawnsettings — View group spawn progress\n"
        "├─➩ /setspawn &lt;val&gt; — Set threshold / on / off\n"
        "├─➩ /togglespawn — Quick toggle wild spawns\n"
        "╰───────────────────────────╯\n\n"
        "╭───「 🤝 Commerce & Deals 」───╮\n"
        "├─➩ /pay &lt;user&gt; &lt;amount&gt; — Send coins\n"
        "├─➩ /balance — Check coin balance\n"
        "├─➩ /gift &lt;user&gt; &lt;id&gt; — Gift character\n"
        "├─➩ /shop — Buy profile themes\n"
        "├─➩ /trade &lt;your_id&gt; &lt;their_id&gt; — Trade\n"
        "├─➩ /redeem &lt;code&gt; — Claim promo code\n"
        "├─➩ /auction &lt;id&gt; &lt;price&gt; — List character\n"
        "├─➩ /bid &lt;auc_id&gt; &lt;amount&gt; — Bid on active\n"
        "├─➩ /cancelauction &lt;auc_id&gt; — Cancel auction\n"
        "├─➩ /auctions — View active auctions\n"
        "╰───────────────────────────╯"
    )
    if is_admin:
        text += (
            "\n\n"
            f"╭───「 {get_emoji('crown')} Owner & Admin Tools 」───╮\n"
            "├─➩ /addchar — Add new character\n"
            "├─➩ /editchar — Edit character details\n"
            "├─➩ /deletechar &lt;id&gt; — Delete character\n"
            "├─➩ /setimg &lt;id&gt; — Update character media\n"
            "├─➩ /give &lt;user&gt; &lt;id/coins&gt; — Grant item\n"
            "├─➩ /setcover &lt;start/help&gt; — Set bot banners\n"
            "├─➩ /spawn — Force spawn character\n"
            "├─➩ /stats — View bot statistics\n"
            "├─➩ /addtochance &lt;rarity&gt; — Enable spawn chance\n"
            "├─➩ /removefromchance &lt;rarity&gt; — Disable spawn chance\n"
            "├─➩ /addtoclaim &lt;rarity&gt; — Enable claim pool\n"
            "├─➩ /removefromclaim &lt;rarity&gt; — Disable claim pool\n"
            "├─➩ /promote &lt;user&gt; — Promote admin\n"
            "├─➩ /demote &lt;user&gt; — Demote admin\n"
            "├─➩ /adminlist — View bot admin staff\n"
            "├─➩ /ownerhelp — Full creator guide\n"
            "╰───────────────────────────╯"
        )
    text += "\n\n📌 <i>Keep chatting in group chats to trigger wild character spawns, and type /guess &lt;name&gt; to collect them!</i>"
    return text

@router.callback_query(F.data == "dm_help")
async def cb_dm_help(callback: CallbackQuery):
    from keyboards.inline import get_back_to_hub_keyboard
    is_admin = callback.from_user.id in config.ADMIN_IDS if callback.from_user else False
    text = build_help_text(is_admin)
    cover_media = get_cover_media("help")
    await send_or_edit_start(callback.message, cover_media, text, get_back_to_hub_keyboard(), is_callback=True)
    await callback.answer()

@router.message(Command("help"))
async def cmd_help(message: Message):
    is_admin = message.from_user.id in config.ADMIN_IDS if message.from_user else False
    text = build_help_text(is_admin)
    cover_media = get_cover_media("help")
    
    is_group = message.chat.type != "private"
    builder = InlineKeyboardBuilder()
    if is_group:
        builder.row(InlineKeyboardButton(text="🗑️ Close Guide", callback_data="close_menu"))
    else:
        builder.row(InlineKeyboardButton(text=f"{get_emoji('back')} Back to Hub Menu", callback_data="dm_home"))
        
    await send_or_edit_start(message, cover_media, text, builder.as_markup(), is_callback=False)

@router.message(Command("ping"))
async def cmd_ping(message: Message):
    start_ping_time = time.time()
    _ = await message.bot.get_me()
    ping_ms = round((time.time() - start_ping_time) * 1000, 2)
    uptime_str = get_uptime_str()
    
    text = (
    parts = message.text.strip().split()
    if len(parts) > 1:
        start_arg = parts[1].strip()
        if start_arg == "addchar":
            message.text = "/addchar"
            from handlers.admin import cmd_addchar
            await cmd_addchar(message, state, db)
            return
        elif start_arg == "editchar":
            message.text = "/editchar"
            from handlers.admin import cmd_editchar
            await cmd_editchar(message, state, db)
            return
    
    cover_media = get_cover_media("start")
    bot_info = await message.bot.get_me()    
    
    # Calculate Ping for start message
    start_ping_time = time.time()
    # Dummy async call to measure ping to telegram servers
    _ = await message.bot.get_me()
    ping_ms = round((time.time() - start_ping_time) * 1000, 2)
    uptime_str = get_uptime_str()
    
    caption = (
        f"🍃 Greetings, I'm <b>AniVerse Bot</b> 🫧\n"
        f"───────── ▨ ─────────\n"
        f"◎ <b>WHERE:</b> I spawn waifus in your chat for users to grab.\n"
        f"◎ <b>HOW TO USE:</b> Add me to your group and use /help for commands.\n"
        f"───────── ▨ ─────────\n"
        f"⚡ <b>PING:</b> {ping_ms} ms\n"
        f"⏳ <b>UPTIME:</b> {uptime_str}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Add to your GC", url=f"https://t.me/{bot_info.username}?startgroup=true"),
        InlineKeyboardButton(text="⚡ Ping", callback_data="ping_bot")
    )
    
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
        f"{get_emoji('party')} <b>Welcome to AniVerse Universe!</b>\n\n"
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

def build_help_text(is_admin: bool) -> str:
    text = (
        "❓ <b>AniVerse Guide & Help Center</b>\n\n"
        "╭───「 🎒 Trainer Utilities 」───╮\n"
        "├─➩ /profile — Stats & themes\n"
        "├─➩ /harem — View harem collection\n"
        "├─➩ /leaderboard [type] — Global rankings (coins/catches)\n"
        "├─➩ /check &lt;id&gt; — Character status & owners\n"
        "├─➩ /search &lt;name&gt; — Database lookup\n"
        "├─➩ /anime &lt;show&gt; — Filter by anime\n"
        "├─➩ /fav &lt;id&gt; — Custom harem cover banner\n"
        "├─➩ /claim — Free daily character\n"
        "╰───────────────────────────╯\n\n"
        "╭───「 🎮 Games & Arcade 」───╮\n"
        "├─➩ /games — Games Center menu\n"
        "├─➩ /spin — Lucky spin wheel\n"
        "├─➩ /daily — Claim daily bonus coins\n"
        "├─➩ /coinflip &lt;bet&gt; &lt;choice&gt; — Bet coins\n"
        "├─➩ /dice &lt;bet&gt; &lt;choice&gt; — Dice roll\n"
        "├─➩ /dart — Animated dart arena\n"
        "├─➩ /trivia — Play anime quizzes\n"
        "├─➩ /mines &lt;bet&gt; &lt;mines&gt; — Mines arcade\n"
        "├─➩ /scramble — Word puzzle rewards\n"
        "├─➩ /xo &lt;reply&gt; — Play Tic-Tac-Toe\n"
        "├─➩ /nameguess — Start manual guessing game\n"
        "├─➩ /togglenameguess — Toggle auto-guessing game loop\n"
        "╰───────────────────────────╯\n\n"
        "╭───「 ⚙️ Group Spawns 」───╮\n"
        "├─➩ /guess &lt;name&gt; — Catch wild character\n"
        "├─➩ /spawnsettings — View group spawn progress\n"
        "├─➩ /setspawn &lt;val&gt; — Set threshold / on / off\n"
        "├─➩ /togglespawn — Quick toggle wild spawns\n"
        "╰───────────────────────────╯\n\n"
        "╭───「 🤝 Commerce & Deals 」───╮\n"
        "├─➩ /pay &lt;user&gt; &lt;amount&gt; — Send coins\n"
        "├─➩ /balance — Check coin balance\n"
        "├─➩ /gift &lt;user&gt; &lt;id&gt; — Gift character\n"
        "├─➩ /shop — Buy profile themes\n"
        "├─➩ /trade &lt;your_id&gt; &lt;their_id&gt; — Trade\n"
        "├─➩ /redeem &lt;code&gt; — Claim promo code\n"
        "├─➩ /auction &lt;id&gt; &lt;price&gt; — List character\n"
        "├─➩ /bid &lt;auc_id&gt; &lt;amount&gt; — Bid on active\n"
        "├─➩ /cancelauction &lt;auc_id&gt; — Cancel auction\n"
        "├─➩ /auctions — View active auctions\n"
        "╰───────────────────────────╯"
    )
    if is_admin:
        text += (
            "\n\n"
            f"╭───「 {get_emoji('crown')} Owner & Admin Tools 」───╮\n"
            "├─➩ /addchar — Add new character\n"
            "├─➩ /editchar — Edit character details\n"
            "├─➩ /deletechar &lt;id&gt; — Delete character\n"
            "├─➩ /setimg &lt;id&gt; — Update character media\n"
            "├─➩ /give &lt;user&gt; &lt;id/coins&gt; — Grant item\n"
            "├─➩ /setcover &lt;start/help&gt; — Set bot banners\n"
            "├─➩ /spawn — Force spawn character\n"
            "├─➩ /stats — View bot statistics\n"
            "├─➩ /addtochance &lt;rarity&gt; — Enable spawn chance\n"
            "├─➩ /removefromchance &lt;rarity&gt; — Disable spawn chance\n"
            "├─➩ /addtoclaim &lt;rarity&gt; — Enable claim pool\n"
            "├─➩ /removefromclaim &lt;rarity&gt; — Disable claim pool\n"
            "├─➩ /promote &lt;user&gt; — Promote admin\n"
            "├─➩ /demote &lt;user&gt; — Demote admin\n"
            "├─➩ /adminlist — View bot admin staff\n"
            "├─➩ /ownerhelp — Full creator guide\n"
            "╰───────────────────────────╯"
        )
    text += "\n\n📌 <i>Keep chatting in group chats to trigger wild character spawns, and type /guess &lt;name&gt; to collect them!</i>"
    return text

@router.callback_query(F.data == "dm_help")
async def cb_dm_help(callback: CallbackQuery):
    from keyboards.inline import get_back_to_hub_keyboard
    is_admin = callback.from_user.id in config.ADMIN_IDS if callback.from_user else False
    text = build_help_text(is_admin)
    cover_media = get_cover_media("help")
    await send_or_edit_start(callback.message, cover_media, text, get_back_to_hub_keyboard(), is_callback=True)
    await callback.answer()

@router.message(Command("help"))
async def cmd_help(message: Message):
    is_admin = message.from_user.id in config.ADMIN_IDS if message.from_user else False
    text = build_help_text(is_admin)
    cover_media = get_cover_media("help")
    
    is_group = message.chat.type != "private"
    builder = InlineKeyboardBuilder()
    if is_group:
        builder.row(InlineKeyboardButton(text="🗑️ Close Guide", callback_data="close_menu"))
    else:
        builder.row(InlineKeyboardButton(text=f"{get_emoji('back')} Back to Hub Menu", callback_data="dm_home"))
        
    await send_or_edit_start(message, cover_media, text, builder.as_markup(), is_callback=False)

@router.message(Command("ping"))
async def cmd_ping(message: Message):
    start_ping_time = time.time()
    _ = await message.bot.get_me()
    ping_ms = round((time.time() - start_ping_time) * 1000, 2)
    uptime_str = get_uptime_str()
    
    text = (
        f"⚡ <b>PING:</b> {ping_ms} ms\n"
        f"⏳ <b>UPTIME:</b> {uptime_str}"
    )
    await message.reply(text, parse_mode="HTML")

@router.callback_query(F.data == "ping_bot")
async def cb_ping(callback: CallbackQuery):
    start_ping_time = time.time()
    _ = await callback.bot.get_me()
    ping_ms = round((time.time() - start_ping_time) * 1000, 2)
    uptime_str = get_uptime_str()
    
    # Update the caption of the start message
    caption = (
        f"🍃 Greetings, I'm <b>AniVerse Bot</b> 🫧\n"
        + format_blockquote(
            f"───────── ▨ ─────────\n"
            f"◎ <b>WHERE:</b> I spawn waifus in your chat for users to grab.\n"
            f"◎ <b>HOW TO USE:</b> Add me to your group and use /help for commands.\n"
            f"───────── ▨ ─────────\n"
            f"⚡ <b>PING:</b> {ping_ms} ms\n"
            f"⏳ <b>UPTIME:</b> {uptime_str}"
        )
    )
    
    bot_info = await callback.bot.get_me()
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Add to your GC", url=f"https://t.me/{bot_info.username}?startgroup=true"),
        InlineKeyboardButton(text="⚡ Ping", callback_data="ping_bot")
    )
    
    try:
        if callback.message.photo or callback.message.video or callback.message.animation:
            await callback.message.edit_caption(caption=caption, reply_markup=builder.as_markup(), parse_mode="HTML")
        else:
            await callback.message.edit_text(text=caption, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer("Ping updated!", show_alert=False)
    except Exception:
        # Message content is the same, so Telegram throws MessageNotModified
        await callback.answer("Ping is unchanged!", show_alert=False)
