import logging
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
import config
from database.models import User, Character, UserCharacter, GroupSettings, RarityType, BotAdmin
from utils.formatters import format_blockquote, get_rarity_emoji, escape_html, RARITY_CACHE
from utils.settings import set_cover_media, get_cover_media
from keyboards.inline import get_back_to_hub_keyboard
from handlers.start import get_or_create_user

logger = logging.getLogger(__name__)
router = Router()

DEFAULT_FALLBACK_PHOTO = "https://cdn.pixabay.com/photo/2022/12/01/04/35/anime-7628313_1280.jpg"
pending_user_media = {}

def is_owner(message: Message) -> bool:
    if message.from_user and message.from_user.id in config.ADMIN_IDS:
        return True
    if message.sender_chat and message.sender_chat.id in config.ADMIN_IDS:
        return True
    return False

async def is_admin_id(user_id: int, db: AsyncSession) -> bool:
    if user_id in config.ADMIN_IDS:
        return True
    stmt = select(BotAdmin).where(BotAdmin.user_id == user_id)
    res = await db.execute(stmt)
    return res.scalar_one_or_none() is not None

async def is_admin(message: Message, db: AsyncSession) -> bool:
    if is_owner(message):
        return True
    if message.from_user:
        return await is_admin_id(message.from_user.id, db)
    return False

class SetCoverStates(StatesGroup):
    waiting_for_media = State()
@router.message(Command("setcover"))
async def cmd_setcover(message: Message, state: FSMContext):
    if not is_owner(message):
        await message.reply("⛔ Only bot owners can configure cover media!")
        return
    # Check if they already provided media directly in the message/reply
    media_value = None
    if message.photo:
        media_value = message.photo[-1].file_id
    elif message.video:
        media_value = message.video.file_id
    elif message.animation:
        media_value = message.animation.file_id
    elif message.reply_to_message:
        if message.reply_to_message.photo:
            media_value = message.reply_to_message.photo[-1].file_id
        elif message.reply_to_message.video:
            media_value = message.reply_to_message.video.file_id
        elif message.reply_to_message.animation:
            media_value = message.reply_to_message.animation.file_id

    parts = message.text.strip().split() if message.text else []
    
    # If they already attached media or link, check if they specified category
    if len(parts) > 1 and (media_value or any(p.startswith("http") for p in parts)):
        category = parts[1].lower()
        if category in ["start", "xo", "dex", "leaderboard", "help"]:
            # Extract link if no file_id
            if not media_value:
                for p in parts:
                    if p.startswith("http"):
                        media_value = p
                        break
            if media_value:
                set_cover_media(category, media_value)
                await message.reply(f"✅ <b>{category.upper()}</b> cover updated successfully!", parse_mode="HTML")
                return

    # Otherwise, start interactive wizard
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🌌 Start Hub", callback_data="setcover_cat_start"))
    builder.add(InlineKeyboardButton(text="❌ Tic-Tac-Toe (XO)", callback_data="setcover_cat_xo"))
    builder.add(InlineKeyboardButton(text="🎒 Harem Collection", callback_data="setcover_cat_dex"))
    builder.add(InlineKeyboardButton(text="🏆 Leaderboards", callback_data="setcover_cat_leaderboard"))
    builder.add(InlineKeyboardButton(text="❓ Help Guide", callback_data="setcover_cat_help"))
    builder.adjust(1)

    await message.reply(
        "🖼️ <b>ANIVERSE COVER MEDIA CONSOLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "Please select the cover category you want to update:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("setcover_cat_"))
async def process_setcover_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("setcover_cat_", "")
    await state.update_data(setcover_category=category)
    await state.set_state(SetCoverStates.waiting_for_media)
    
    label = "HAREM" if category == "dex" else category.upper()
    text = (
        "🖼️ <b>ANIVERSE COVER MEDIA CONSOLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"Category: <b>{label}</b>\n\n"
        "Please upload a photo, video, GIF, or send an image URL to set as the cover (or send `/cancel` to abort):"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.reply(text, parse_mode="HTML")
    await callback.answer()

@router.message(SetCoverStates.waiting_for_media)
async def process_setcover_media(message: Message, state: FSMContext):
    if message.text and message.text == "/cancel":
        await state.clear()
        await message.reply("❌ Cover configuration cancelled.")
        return

    media_value = None
    if message.photo:
        media_value = message.photo[-1].file_id
    elif message.video:
        media_value = message.video.file_id
    elif message.animation:
        media_value = message.animation.file_id
    elif message.text and message.text.strip().startswith("http"):
        media_value = message.text.strip()

    if not media_value:
        await message.reply("⚠️ Please upload a valid photo/video/GIF or send a link starting with http!")
        return

    data = await state.get_data()
    category = data["setcover_category"]

    set_cover_media(category, media_value)
    await state.clear()

    card = (
        f"✅ <b>{category.upper()} BANNER COVER UPDATED!</b>\n\n"
        + format_blockquote(f"The banner cover media for <b>{category.upper()}</b> has been successfully updated!")
    )
    await message.reply(card, parse_mode="HTML")

@router.message(Command("give", "giv", "givechar", "givecoins"))
async def cmd_give(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply(f"⛔ Only bot owners can use give commands! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
        return
    text = message.text.strip()
    cmd_token = text.split()[0].lower()
    raw_args = text[len(cmd_token):].strip()
    reply = message.reply_to_message

    if not raw_args and not reply:
        card = (
            "🎁 <b>OWNER GIVE CONSOLE</b>\n\n"
            + format_blockquote(
                "Grant characters or coins directly to players!\n\n"
                "👤 <b>Give Character by ID:</b>\n"
                "• <code>/giv &lt;user_id&gt; &lt;character_id&gt;</code>\n"
                "• <code>/giv char &lt;user_id&gt; &lt;character_id&gt;</code>\n"
                "• Reply to a user's message with: <code>/giv &lt;character_id&gt;</code>\n\n"
                "💰 <b>Give Coins:</b>\n"
                "• <code>/giv coins &lt;user_id&gt; &lt;amount&gt;</code>\n"
                "• Reply to a user's message with: <code>/giv coins &lt;amount&gt;</code>"
            )
        )
        await message.reply(card, parse_mode="HTML")
        return

    tokens = [t for t in raw_args.split() if t]
    mode = "char"
    if "coin" in cmd_token:
        mode = "coins"

    if tokens and tokens[0].lower() in ["coin", "coins"]:
        mode = "coins"
        tokens = tokens[1:]
    elif tokens and tokens[0].lower() in ["char", "character"]:
        mode = "char"
        tokens = tokens[1:]

    target_user_id = None
    target_user_name = "Player"
    value_str = None

    if len(tokens) >= 2 and tokens[0].isdigit() and tokens[1].isdigit():
        target_user_id = int(tokens[0])
        value_str = tokens[1]
    elif reply and reply.from_user and not reply.from_user.is_bot:
        target_user_id = reply.from_user.id
        target_user_name = reply.from_user.first_name
        if tokens:
            value_str = tokens[0]
    else:
        if len(tokens) >= 2:
            target_user_id = int(tokens[0]) if tokens[0].isdigit() else None
            value_str = tokens[1]
        elif len(tokens) == 1:
            value_str = tokens[0]

    if not target_user_id:
        await message.reply("⚠️ Target user missing! Either reply to a player's message or specify the User ID.\n<i>Example: /giv 6593485710 55</i>", parse_mode="HTML")
        return

    if not value_str or not value_str.isdigit():
        await message.reply(f"⚠️ Please specify a numeric ID/amount for {mode}!", parse_mode="HTML")
        return

    val_num = int(value_str)
    user = await get_or_create_user(db, target_user_id, "", target_user_name or "")

    if mode == "coins":
        user.coins += val_num
        await db.commit()
        await message.reply(
            f"✅ <b>GAVE COINS SUCCESSFULLY!</b>\n\n"
            + format_blockquote(f"💰 Added <b>{val_num:,} coins</b> to <a href=\"tg://user?id={user.user_id}\">{escape_html(user.first_name)}</a>!\nNew Balance: <code>{user.coins:,} coins</code>"),
            parse_mode="HTML"
        )
    else:
        char_stmt = select(Character).where(Character.id == val_num)
        char_res = await db.execute(char_stmt)
        character = char_res.scalar_one_or_none()

        if not character:
            await message.reply(f"❌ No character exists with ID <b>#{val_num}</b>!", parse_mode="HTML")
            return

        user.total_catches += 1
        user_char = UserCharacter(user_id=user.user_id, character_id=character.id, nickname=character.name)
        db.add(user_char)
        await db.commit()

        r_emoji = get_rarity_emoji(character.rarity)
        await message.reply(
            f"✅ <b>GAVE CHARACTER SUCCESSFULLY!</b>\n\n"
            + format_blockquote(
                f"🌟 Added <b>{escape_html(character.name)}</b> [{character.anime}] to <a href=\"tg://user?id={user.user_id}\">{escape_html(user.first_name)}</a>'s harem!\n"
                f"{r_emoji} <b>Rarity:</b> {r_emoji} {character.rarity}\n"
                f"🆔 <b>Character ID:</b> #{character.id}"
            ),
            parse_mode="HTML"
        )

@router.message(Command("addrarity"))
async def cmd_addrarity(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer("⛔ Only bot owners and admins can add custom rarity types!")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "✨ <b>ADD CUSTOM RARITY CONSOLE</b>\n\n"
            + format_blockquote(
                "Define a new custom rarity tier for your bot!\n\n"
                "⚡ <b>Usage:</b> <code>/addrarity Name | Emoji</code>\n"
                "<b>Example:</b> <code>/addrarity Celestial | 🌌</code>"
            ),
            parse_mode="HTML"
        )
        return

    args = [x.strip() for x in parts[1].split("|")]
    if len(args) < 2:
        await message.answer("❌ Please provide at least <b>Name | Emoji</b> separated by <code>|</code>", parse_mode="HTML")
        return

    name = args[0].title()
    emoji = args[1]

    stmt = select(RarityType).where(RarityType.name.ilike(name))
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.emoji = emoji
    else:
        new_rarity = RarityType(name=name, emoji=emoji, spawn_enabled=False)
        db.add(new_rarity)

    await db.commit()
    from utils.formatters import RARITY_CACHE
    RARITY_CACHE[name] = {"emoji": emoji}

    card = (
        f"✨ <b>CUSTOM RARITY TIER ADDED!</b> ✨\n\n"
        + format_blockquote(
            f"🏷️ <b>NAME:</b> {name}\n"
            f"{emoji} <b>RARITY EMOJI:</b> {emoji}\n\n"
            f"⚡ <i>Note: This rarity is not in wild spawn chance yet. Use <code>/addtochance {name}</code> to enable wild spawns!</i>"
        )
    )
    await message.answer(card, parse_mode="HTML")

@router.message(Command("addtochance", "addchance"))
async def cmd_addtochance(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer("⛔ Only bot owners and admins can manage spawn chance!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⚠️ <b>Usage:</b> <code>/addtochance &lt;rarity_name&gt;</code>", parse_mode="HTML")
        return

    rarity_name = parts[1].strip()
    stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        rarity_item = RarityType(name=rarity_name.title(), emoji="✨", spawn_enabled=True)
        db.add(rarity_item)
    else:
        rarity_item.spawn_enabled = True

    await db.commit()
    await message.reply(f"🎯 <b>{rarity_item.name}</b> [{rarity_item.emoji}] has been added to wild spawn chance!", parse_mode="HTML")

@router.message(Command("removefromchance", "remchance", "delchance"))
async def cmd_removefromchance(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer("⛔ Only bot owners and admins can manage spawn chance!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⚠️ <b>Usage:</b> <code>/removefromchance &lt;rarity_name&gt;</code>", parse_mode="HTML")
        return

    rarity_name = parts[1].strip()
    stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if rarity_item:
        rarity_item.spawn_enabled = False
        await db.commit()

    await message.reply(f"🚫 <b>{rarity_name.title()}</b> has been removed from wild spawn chance!", parse_mode="HTML")

class AddCharStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_anime = State()
    waiting_for_rarity = State()
    waiting_for_media = State()

class EditCharStates(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_new_anime = State()
    waiting_for_new_rarity = State()
    waiting_for_new_media = State()
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.reply("❌ Character registration process has been cancelled.")
@router.message(Command("addchar"))
async def cmd_addchar(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin(message, db):
        await message.reply("⛔ Only bot owners and admins can add characters!")
        return
    parts = message.text.split(maxsplit=1)
    target_id = None
    if len(parts) > 1:
        arg = parts[1].strip()
        if arg.isdigit():
            target_id = int(arg)
            stmt = select(Character).where(Character.id == target_id)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                await message.reply(f"❌ A character with ID <b>{target_id}</b> already exists!", parse_mode="HTML")
                return

    await state.clear()
    await state.set_state(AddCharStates.waiting_for_name)
    if target_id is not None:
        await state.update_data(target_id=target_id)
        msg_id_text = f" at ID <b>#{target_id}</b>"
    else:
        msg_id_text = ""

    await message.reply(
        "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>[Step 1/4] Character Name</b>{msg_id_text}\n\n"
        "Please type the name of the character (or send `/cancel` to abort):",
        parse_mode="HTML"
    )
@router.message(AddCharStates.waiting_for_name, F.text)
async def process_name(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        if message.text == "/cancel":
            return
        await message.reply("⚠️ Invalid name! Please type a text name for the character:")
        return

    await state.update_data(name=message.text.strip())
    await state.set_state(AddCharStates.waiting_for_anime)
    await message.reply(
        "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📺 <b>[Step 2/4] Anime Series</b>\n\n"
        "Please type the name of the anime series this character belongs to:",
        parse_mode="HTML"
    )

@router.message(AddCharStates.waiting_for_anime, F.text)
async def process_anime(message: Message, state: FSMContext, db: AsyncSession):
    if message.text.startswith("/"):
        if message.text == "/cancel":
            return
        await message.reply("⚠️ Invalid anime! Please type the name of the anime series:")
        return

    await state.update_data(anime=message.text.strip())
    await state.set_state(AddCharStates.waiting_for_rarity)

    # Fetch available rarities
    default_rarities = ["Common", "Rare", "Epic", "Legendary", "Mythical"]
    custom_stmt = select(RarityType)
    custom_res = await db.execute(custom_stmt)
    custom_rarities = [r.name.title() for r in custom_res.scalars().all()]
    all_rarities = list(set(default_rarities + custom_rarities))

    builder = InlineKeyboardBuilder()
    for r in sorted(all_rarities):
        emoji = get_rarity_emoji(r)
        builder.add(InlineKeyboardButton(text=f"{emoji} {r}", callback_data=f"sel_rarity_{r.lower()}"))
    builder.adjust(2)

    await message.reply(
        "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💎 <b>[Step 3/4] Rarity Tier</b>\n\n"
        "Please select a rarity tier below, or type one manually:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(AddCharStates.waiting_for_rarity, F.data.startswith("sel_rarity_"))
async def process_rarity_callback(callback: CallbackQuery, state: FSMContext):
    rarity_val = callback.data.replace("sel_rarity_", "").title()
    await state.update_data(rarity=rarity_val)
    await state.set_state(AddCharStates.waiting_for_media)
    
    text = (
        "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📸 <b>[Step 4/4] Media Upload</b>\n\n"
        f"Selected Rarity: <b>{rarity_val}</b>\n"
        "Please upload a photo, video, or GIF for the character (or send `/cancel` to abort):"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.reply(text, parse_mode="HTML")
    await callback.answer()

@router.message(AddCharStates.waiting_for_rarity, F.text)
async def process_rarity_text(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        if message.text == "/cancel":
            return
        await message.reply("⚠️ Invalid option! Please select a rarity tier or type one manually:")
        return

    rarity_val = message.text.strip().title()
    await state.update_data(rarity=rarity_val)
    await state.set_state(AddCharStates.waiting_for_media)
    await message.reply(
        "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📸 <b>[Step 4/4] Media Upload</b>\n\n"
        f"Selected: <b>{rarity_val}</b>\n"
        "Please upload a photo, video, or GIF for the character:",
        parse_mode="HTML"
    )

@router.message(AddCharStates.waiting_for_media, F.photo | F.video | F.animation)
async def process_media(message: Message, state: FSMContext, db: AsyncSession, bot):
    file_id = None
    media_type = None

    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
    elif message.animation:
        file_id = message.animation.file_id
        media_type = "animation"

    if not file_id:
        await message.reply("⚠️ Please send a valid photo, video, or GIF!")
        return

    data = await state.get_data()
    name = data["name"]
    anime = data["anime"]
    rarity = data["rarity"]

    target_id = data.get("target_id")
    if target_id:
        existing_stmt = select(Character).where(Character.id == target_id)
        existing_res = await db.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            await message.reply(f"❌ A character with ID {target_id} was just registered! Aborted.")
            await state.clear()
            return
        character = Character(
            id=target_id,
            name=name,
            anime=anime,
            rarity=rarity,
            image_url=file_id
        )
    else:
        character = Character(
            name=name,
            anime=anime,
            rarity=rarity,
            image_url=file_id
        )
    db.add(character)
    await db.commit()
    await state.clear()

    r_emoji = get_rarity_emoji(rarity)
    card = (
        "⛩️ <b>CHARACTER FULLY REGISTERED!</b> ⛩️\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        + format_blockquote(
            f"🆔 <b>ID:</b> #{character.id}\n"
            f"👤 <b>NAME:</b> {escape_html(character.name)}\n"
            f"🎦 <b>ANIME:</b> {escape_html(character.anime)}\n"
            f"{r_emoji} <b>RARITY:</b> {r_emoji} {character.rarity}"
        )
    )

    try:
        if media_type == "photo":
            await message.reply_photo(file_id, caption=card, parse_mode="HTML")
        elif media_type == "video":
            await message.reply_video(file_id, caption=card, parse_mode="HTML")
        elif media_type == "animation":
            await message.reply_animation(file_id, caption=card, parse_mode="HTML")
    except Exception:
        await message.reply(card, parse_mode="HTML")

    if message.chat.type != "private":
        try:
            if media_type in ["video", "animation"]:
                await bot.send_video(message.from_user.id, file_id, caption=f"📬 <b>Character Showcase (Sent to DM):</b>\n\n{card}", parse_mode="HTML")
            else:
                await bot.send_photo(message.from_user.id, file_id, caption=f"📬 <b>Character Showcase (Sent to DM):</b>\n\n{card}", parse_mode="HTML")
        except Exception:
            pass

    # Database Channel Announcement Sync
    db_channel = "@AniVersedatabase"
    img_check = "✅" if media_type == "photo" else "❌"
    vid_check = "✅" if media_type in ["video", "animation"] else "❌"
    by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

    ist_offset = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now_ist = datetime.datetime.now(tz=ist_offset)
    time_str = now_ist.strftime("%d %b %Y, %I:%M %p IST")

    announcement_text = (
        "✨ <b>NEW CHARACTER MEDIA ADDED!</b>\n"
        + format_blockquote(
            f"🆔 <b>ID</b>: #{character.id:03d}\n"
            f"📛 <b>Name</b>: {escape_html(character.name)}\n"
            f"📺 <b>Anime</b>: {escape_html(character.anime)}\n"
            f"💎 <b>Rarity</b>: {r_emoji} {character.rarity}\n"
            f"🖼️ <b>Image</b>: {img_check}\n"
            f"🎥 <b>Video</b>: {vid_check}\n"
            f"👤 <b>By</b>: {escape_html(by_user)}\n"
            f"⌛️ <b>Time</b>: {time_str}"        )
    )

    try:
        if media_type == "photo":
            await bot.send_photo(chat_id=db_channel, photo=file_id, caption=announcement_text, parse_mode="HTML")
        elif media_type == "video":
            await bot.send_video(chat_id=db_channel, video=file_id, caption=announcement_text, parse_mode="HTML")
        elif media_type == "animation":
            await bot.send_animation(chat_id=db_channel, animation=file_id, caption=announcement_text, parse_mode="HTML")
    except Exception as e:
        print(f"Failed to send character sync to database channel: {e}")

@router.message(Command("setimg", "updateimg", "setphoto"))
async def cmd_setimg(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"⛔ Only bot owners and admins can use setimg! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
        return
    parts = message.text.split()[1:]
    reply = message.reply_to_message
    file_id = None
    url_val = None
    char_id_str = parts[0] if parts else None

    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.animation:
        file_id = message.animation.file_id
    elif reply:
        if reply.photo:
            file_id = reply.photo[-1].file_id
        elif reply.video:
            file_id = reply.video.file_id
        elif reply.animation:
            file_id = reply.animation.file_id
        elif reply.text and reply.text.startswith("http"):
            url_val = reply.text.strip()
    
    if not file_id and len(parts) >= 2 and parts[1].startswith("http"):
        url_val = parts[1].strip()

    media_to_set = file_id or url_val

    if not char_id_str or not media_to_set:
        card = (
            "🖼️ <b>UPDATE CHARACTER IMAGE CONSOLE</b>\n\n"
            + format_blockquote(
                "Update the image or media file for any character!\n\n"
                "⚡ <b>Usage:</b>\n"
                "• Reply to a photo/video with: <code>/setimg &lt;character_id&gt;</code>\n"
                "• Or send a photo with caption: <code>/setimg &lt;character_id&gt;</code>\n"
                "• Or provide URL: <code>/setimg &lt;character_id&gt; https://image.url/photo.jpg</code>"
            )
        )
        await message.reply(card, parse_mode="HTML")
        return

    if not char_id_str.isdigit():
        await message.reply("❌ Character ID must be a numeric integer!")
        return

    char_id = int(char_id_str)
    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()

    if not character:
        await message.reply(f"❌ No character exists with ID <b>#{char_id}</b>!", parse_mode="HTML")
        return

    character.image_url = media_to_set
    await db.commit()

    r_emoji = get_rarity_emoji(character.rarity)
    card = (
        f"✅ <b>CHARACTER IMAGE UPDATED!</b>\n\n"
        + format_blockquote(
            f"🆔 <b>ID:</b> #{character.id}\n"
            f"👤 <b>NAME:</b> {escape_html(character.name)}\n"
            f"🎦 <b>ANIME:</b> {escape_html(character.anime)}\n"
            f"{r_emoji} <b>RARITY:</b> {r_emoji} {character.rarity}"
        )
    )
    try:
        await message.reply_photo(media_to_set, caption=card, parse_mode="HTML")
    except Exception:
        try:
            await message.reply_video(media_to_set, caption=card, parse_mode="HTML")
        except Exception:
            await message.reply(card, parse_mode="HTML")

@router.message(Command("deletechar", "delchar", "removechar"))
async def cmd_deletechar(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"⛔ Only bot owners and admins can delete characters! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⚠️ <b>Usage:</b> <code>/deletechar &lt;character_id or name&gt;</code>", parse_mode="HTML")
        return

    query_str = parts[1].strip()
    if query_str.isdigit():
        stmt = select(Character).where(Character.id == int(query_str))
    else:
        stmt = select(Character).where(Character.name.ilike(query_str))

    res = await db.execute(stmt)
    character = res.scalar_one_or_none()

    if not character:
        await message.reply(f"❌ No character found matching <b>{escape_html(query_str)}</b>!", parse_mode="HTML")
        return

    char_id = character.id
    char_name = character.name
    char_anime = character.anime

    await db.execute(delete(UserCharacter).where(UserCharacter.character_id == char_id))
    await db.delete(character)
    await db.commit()

    card = (
        f"🗑️ <b>CHARACTER DELETED FROM BOT!</b>\n\n"
        + format_blockquote(
            f"🆔 <b>ID:</b> #{char_id}\n"
            f"👤 <b>NAME:</b> {escape_html(char_name)}\n"
            f"🎦 <b>ANIME:</b> {escape_html(char_anime)}\n\n"
            f"⚠️ Successfully removed character and all user ownership instances from database!"
        )
    )
    await message.reply(card, parse_mode="HTML")

@router.message(Command("setrarity"))
async def cmd_setrarity(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"⛔ Only bot owners and admins can set rarity! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
        return    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("⚠️ <b>Usage:</b> <code>/setrarity &lt;character_id&gt; &lt;new_rarity&gt;</code>", parse_mode="HTML")
        return

    char_id = parts[1]
    new_rarity = parts[2].title()

    stmt = select(Character).where(Character.id == int(char_id)) if char_id.isdigit() else select(Character).where(Character.name.ilike(char_id))
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()

    if not character:
        await message.answer("❌ Character not found!")
        return

    character.rarity = new_rarity
    await db.commit()
    
    r_emoji = get_rarity_emoji(new_rarity)
    await message.answer(f"✅ Updated <b>{escape_html(character.name)}</b> rarity to {r_emoji} <b>{new_rarity}</b>!", parse_mode="HTML")

@router.message(Command("spawn"))
async def cmd_admin_spawn(message: Message, db: AsyncSession, bot):
    if not await is_admin(message, db):
        await message.answer(f"⛔ Only bot owners and admins can spawn! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
        return    
    parts = message.text.split(maxsplit=1)
    rarity_arg = parts[1].strip() if len(parts) > 1 else None

    from handlers.catch import spawn_character
    success = await spawn_character(message.chat.id, db, bot, custom_rarity=rarity_arg)
    if not success:
        await message.answer("⚠️ Could not spawn character. Check if characters exist in database.")

@router.message(Command("stats"))
async def cmd_stats(message: Message, db: AsyncSession):
    if not is_admin(message):
        await message.answer(f"⛔ Only bot owners can view stats! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
        return

    users_cnt = (await db.execute(select(func.count(User.user_id)))).scalar()
    chars_cnt = (await db.execute(select(func.count(Character.id)))).scalar()
    catches_cnt = (await db.execute(select(func.count(UserCharacter.id)))).scalar()
    rarity_cnt = (await db.execute(select(func.count(RarityType.id)))).scalar()

    text = (
        "📊 <b>AniVerse System Statistics</b>\n\n"
        + format_blockquote(
            f"👥 <b>Total Registered Players:</b> {users_cnt:,}\n"
            f"⛩️ <b>Total Anime Characters:</b> {chars_cnt:,}\n"
            f"✨ <b>Total Rarity Types:</b> {rarity_cnt + 5:,}\n"
            f"🎒 <b>Total Caught Characters:</b> {catches_cnt:,}"
        )
    )
    await message.answer(text, parse_mode="HTML")

@router.callback_query(F.data == "admin_tools")
async def cb_admin_tools(callback: CallbackQuery):
    if not is_admin(callback.message):
        await callback.answer("Unauthorized!", show_alert=True)
        return

    text = (
        "🛠️ <b>AniVerse Telegram Admin Tools</b>\n\n"
        + format_blockquote(
            "🎁 <b>Give Characters & Coins:</b>\n<code>/giv char &lt;user_id&gt; &lt;char_id&gt;</code>\n<code>/giv coins &lt;user_id&gt; &lt;amount&gt;</code>\n\n"
            "🎯 <b>Spawn Chance Controls:</b>\n<code>/addtochance &lt;rarity&gt;</code>\n<code>/removefromchance &lt;rarity&gt;</code>\n\n"
            "🖼️ <b>Update Character Image:</b>\n<code>/setimg &lt;char_id&gt;</code> (reply or photo URL)\n\n"
            "🗑️ <b>Delete Character:</b>\n<code>/deletechar &lt;char_id_or_name&gt;</code>\n\n"
            "⚡ <b>Add Custom Rarity Tier:</b>\n<code>/addrarity Name | Emoji</code>\n\n"
            "⚡ <b>Add Anime Character:</b>\n<code>/addchar Name | Anime | Rarity</code>\n\n"
            "🌀 <b>Force Spawn:</b>\n<code>/spawn [rarity]</code>"
        )
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
    await callback.answer()

@router.message(Command("addpremium"))
async def cmd_addpremium(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply("⛔ Only bot owners can manage premium status.")
        return
    text = message.text.strip()
    parts = text.split(maxsplit=2)
    
    target_id = None
    days = 30

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if len(parts) > 1 and parts[1].isdigit():
            days = int(parts[1])
    else:
        if len(parts) < 3:
            await message.reply("⚠️ Format: <code>/addpremium &lt;user_id&gt; &lt;days&gt;</code> or reply to a user with <code>/addpremium &lt;days&gt;</code>", parse_mode="HTML")
            return
        if not parts[1].isdigit() or not parts[2].isdigit():
            await message.reply("⚠️ Both user_id and days must be numbers.", parse_mode="HTML")
            return
        target_id = int(parts[1])
        days = int(parts[2])

    target_user = await get_or_create_user(db, target_id, "", "")
    now = datetime.datetime.utcnow()
    current_expiry = target_user.premium_until if (target_user.premium_until and target_user.premium_until > now) else now
    target_user.premium_until = current_expiry + datetime.timedelta(days=days)
    await db.commit()

    delta = target_user.premium_until - now
    await message.reply(
        f"👑 <b>Premium status granted!</b>\n\n"
        f"● <b>User ID:</b> {target_id}\n"
        f"● <b>Days added:</b> {days}\n"
        f"● <b>Remaining time:</b> {delta.days}d {delta.seconds // 3600}h",
        parse_mode="HTML"
    )

@router.message(Command("settag"))
async def cmd_settag(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.reply("⛔ Only bot owners and admins can set player tags.")
        return
    text = message.text.strip()
    parts = text.split(maxsplit=2)

    target_id = None
    tag_text = None

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if len(parts) > 1:
            tag_text = text[len(parts[0]):].strip()
    else:
        if len(parts) < 3:
            await message.reply("⚠️ Format: <code>/settag &lt;user_id&gt; &lt;tag_text&gt;</code> or reply to a user with <code>/settag &lt;tag_text&gt;</code>", parse_mode="HTML")
            return
        if not parts[1].isdigit():
            await message.reply("⚠️ User ID must be a number.", parse_mode="HTML")
            return
        target_id = int(parts[1])
        tag_text = parts[2].strip()

    if not tag_text:
        await message.reply("⚠️ Tag text cannot be empty.")
        return

    target_user = await get_or_create_user(db, target_id, "", "")
    target_user.premium_tag = tag_text
    await db.commit()

    await message.reply(
        f"🏷️ <b>User tag updated!</b>\n\n"
        f"● <b>User ID:</b> {target_id}\n"
        f"● <b>New tag:</b> {escape_html(tag_text)}",
        parse_mode="HTML"
    )

@router.message(Command("removepremium", "delpremium"))
async def cmd_removepremium(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply("⛔ Only bot owners can manage premium status.")
        return
    text = message.text.strip()
    parts = text.split(maxsplit=1)

    target_id = None

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        if len(parts) < 2 or not parts[1].isdigit():
            await message.reply("⚠️ Format: <code>/removepremium &lt;user_id&gt;</code> or reply to a user with <code>/removepremium</code>", parse_mode="HTML")
            return
        target_id = int(parts[1])

    target_user = await get_or_create_user(db, target_id, "", "")
    target_user.premium_until = None
    target_user.premium_tag = None
    await db.commit()

    await message.reply(f"❌ <b>Premium status revoked</b> for user ID {target_id}.", parse_mode="HTML")

@router.message(Command("ownerhelp", "owner", "adminhelp", "admin"))
async def cmd_ownerhelp(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        return
    is_owner_user = is_owner(message)
    console_title = "👑 AniVerse Owner Console" if is_owner_user else "⚙️ AniVerse Admin Console"
    
    card = (
        f"╭───「 {console_title} 」───╮\n"
        "│\n"
        f"│  Welcome, <b>{escape_html(message.from_user.first_name)}</b>!\n"
        "│\n"
        "│  ⚡ <b>ADMIN COMMANDS (You can use these):</b>\n"
        "│  ├─➩ <code>/stats</code> — View bot stats\n"
        "│  ├─➩ <code>/spawn</code> — Force spawn wild character\n"
        "│  ├─➩ <code>/addchar &lt;details&gt;</code> — Create character\n"
        "│  ├─➩ <code>/editchar &lt;id&gt;</code> — Edit name/anime/rarity/media\n"
        "│  ├─➩ <code>/deletechar &lt;id&gt;</code> — Delete character\n"
        "│  ├─➩ <code>/setimg &lt;id&gt;</code> — Update character media\n"
        "│  ├─➩ <code>/setrarity &lt;id&gt; &lt;rarity&gt;</code> — Update rarity\n"
        "│  ├─➩ <code>/settag &lt;id&gt; &lt;tag&gt;</code> — Update player tag\n"
        "│  ├─➩ <code>/addrarity &lt;name&gt; | &lt;emoji&gt;</code> — Add new rarity\n"
        "│  ├─➩ <code>/addtochance &lt;rarity&gt;</code> — Enable wild spawn\n"
        "│  ├─➩ <code>/removefromchance &lt;rarity&gt;</code> — Disable spawn\n"
        "│  ├─➩ <code>/spawnchance</code> — View spawn percentages\n"
        "│  ├─➩ <code>/editspawnchance &lt;rarity&gt; &lt;weight&gt;</code>\n"
        "│  ├─➩ <code>/adminlist</code> — View all active admins\n"
    )
    
    if is_owner_user:
        card += (
            "│\n"
            "│  👑 <b>OWNER ONLY COMMANDS:</b>\n"
            "│  ├─➩ <code>/promote &lt;user&gt; &lt;role&gt;</code> — Grant admin\n"
            "│  ├─➩ <code>/demote &lt;user&gt;</code> — Revoke admin role\n"
            "│  ├─➩ <code>/setcover &lt;mode&gt;</code> — Set covers (start, xo, dex)\n"
            "│  ├─➩ <code>/give &lt;user&gt; &lt;amount/char&gt;</code> — Give coins/chars\n"
            "│  ├─➩ <code>/addpremium &lt;user&gt;</code> — Grant VIP status\n"
            "│  ├─➩ <code>/removepremium &lt;user&gt;</code> — Revoke VIP status\n"
        )
        
    card += "│  \n╰──────────────────────────╯"
    is_group = message.chat.type != "private"
    builder = InlineKeyboardBuilder()
    if is_group:
        builder.row(InlineKeyboardButton(text="🗑️ Close Menu", callback_data="close_menu"))
    else:
        builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))

    try:
        await message.reply_photo(get_cover_media("start"), caption=card, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await message.reply(card, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "admin_tools")
async def cb_admin_tools(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return

    card = (
        "╭───「 👑 AniVerse Owner Console 」───╮\n"
        "│\n"
        f"│  Welcome Creator, <b>{escape_html(callback.from_user.first_name)}</b>!\n"
        "│\n"
        "│  🔧 <b>Management Commands:</b>\n"
        "│  ├─➩ <code>/stats</code> — Server stats & DB info\n"
        "│  ├─➩ <code>/spawn</code> — Force spawn wild character\n"
        "│  ├─➩ <code>/setcover &lt;mode&gt;</code> — Set covers (start, xo, dex)\n"
        "│  │\n"
        "│  🎴 <b>Character Editing:</b>\n"
        "│  ├─➩ <code>/addchar &lt;details&gt;</code> — Create character\n"
        "│  ├─➩ <code>/deletechar &lt;id&gt;</code> — Delete character\n"
        "│  ├─➩ <code>/setimg &lt;id&gt; &lt;url&gt;</code> — Update photo\n"
        "│  ├─➩ <code>/setrarity &lt;id&gt; &lt;rarity&gt;</code> — Update rarity\n"
        "│  ├─➩ <code>/settag &lt;id&gt; &lt;tag&gt;</code> — Update tag\n"
        "│  │\n"
        "│  💰 <b>Player & Wager controls:</b>\n"
        "│  ├─➩ <code>/give &lt;user&gt; &lt;amount/char&gt;</code> — Give coins/chars\n"
        "│  ├─➩ <code>/addpremium &lt;user&gt;</code> — Grant VIP status\n"
        "│  ├─➩ <code>/removepremium &lt;user&gt;</code> — Revoke VIP status\n"
        "│  │\n"
        "│  📈 <b>Database Config:</b>\n"
        "│  ├─➩ <code>/addrarity &lt;rarity&gt; &lt;chance&gt;</code>\n"
        "│  ├─➩ <code>/addchance &lt;id&gt; &lt;chance&gt;</code>\n"
        "│  \n"
        "╰──────────────────────────╯"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))
    
    from handlers.start import send_or_edit_start
    await send_or_edit_start(callback.message, get_cover_media("start"), card, builder.as_markup(), is_callback=True)
    await callback.answer()

@router.message(Command("spawnchance", "spawnchances"))
async def cmd_spawnchance(message: Message, db: AsyncSession):
    stmt = select(RarityType).where(RarityType.spawn_enabled == True)
    res = await db.execute(stmt)
    rarities = res.scalars().all()
    
    if not rarities:
        await message.reply("⚠️ No rarities are currently enabled for wild spawn.")
        return
        
    total_weight = sum(r.weight for r in rarities)
    
    lines = []
    # Sort by weight descending
    rarities.sort(key=lambda x: x.weight, reverse=True)
    
    for r in rarities:
        pct = (r.weight / total_weight) * 100 if total_weight > 0 else 0
        from utils.formatters import get_rarity_emoji
        r_emoji = get_rarity_emoji(r.name)
        lines.append(f"{r_emoji} <b>{r.name}</b>: <b>{pct:.2f}%</b>")        
    text = (
        "🎯 <b>WILD CHARACTER SPAWN CHANCES</b>\n\n"
        + format_blockquote("\n".join(lines))
    )
    await message.reply(text, parse_mode="HTML")

@router.message(Command("editspawnchance", "setspawnchance"))
async def cmd_editspawnchance(message: Message, db: AsyncSession):
    if not is_admin(message):
        await message.answer("⛔ Only bot owners can edit spawn chance!")
        return

    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.reply(
            "⚠️ <b>Usage:</b>\n"
            "👉 <code>/editspawnchance &lt;rarity_name&gt; &lt;weight&gt;</code>\n\n"
            "Example: <code>/editspawnchance Epic 20</code>",
            parse_mode="HTML"
        )
        return

    rarity_name = parts[1].strip()
    weight_str = parts[2].strip()

    if not weight_str.isdigit():
        await message.reply("❌ Weight must be a valid positive number.")
        return

    weight = int(weight_str)
    if weight < 0:
        await message.reply("❌ Weight cannot be negative.")
        return

    stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        await message.reply(f"❌ Rarity tier '<b>{escape_html(rarity_name)}</b>' not found. Add it first using /addrarity.", parse_mode="HTML")
        return

    rarity_item.weight = weight
    await db.commit()

# --- EDIT CHARACTER INTERACTIVE TOOL ---

DEFAULT_CHAR_PHOTO = "https://cdn.pixabay.com/photo/2022/12/01/04/35/anime-7628313_1280.jpg"

@router.message(Command("editchar", "editcharacter"))
async def cmd_editchar(message: Message, db: AsyncSession):
    if not is_admin(message):
        await message.reply("⛔ Only bot owners can edit characters!")
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.reply("⚠️ <b>Usage:</b> <code>/editchar &lt;character_id&gt;</code>", parse_mode="HTML")
        return

    char_id_str = parts[1].strip()
    if not char_id_str.isdigit():
        await message.reply("❌ Character ID must be a valid number.")
        return

    char_id = int(char_id_str)
    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()

    if not character:
        await message.reply(f"❌ Character ID #{char_id} not found in database.")
        return

    await send_edit_char_menu(message, character, db, is_callback=False)

async def send_edit_char_menu(message_obj, character: Character, db: AsyncSession, is_callback: bool = False):
    r_emoji = get_rarity_emoji(character.rarity)
    card = (
        "⚙️ <b>EDIT CHARACTER CONSOLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        + format_blockquote(
            f"🆔 <b>ID:</b> #{character.id}\n"
            f"👤 <b>NAME:</b> {escape_html(character.name)}\n"
            f"🎦 <b>ANIME:</b> {escape_html(character.anime)}\n"
            f"{r_emoji} <b>RARITY:</b> {r_emoji} {character.rarity}"
        )
        + "\n\nSelect which field you want to edit below:"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Edit Name", callback_data=f"edit_name_{character.id}"),
        InlineKeyboardButton(text="🎦 Edit Anime", callback_data=f"edit_anime_{character.id}")
    )
    builder.row(
        InlineKeyboardButton(text="💎 Edit Rarity", callback_data=f"edit_rarity_{character.id}"),
        InlineKeyboardButton(text="📸 Edit Media", callback_data=f"edit_media_{character.id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Close Menu", callback_data="close_edit_menu"))
    
    photo = character.image_url if character.image_url else DEFAULT_CHAR_PHOTO
    
    if is_callback:
        try:
            await message_obj.edit_caption(caption=card, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            try:
                await message_obj.edit_text(card, parse_mode="HTML", reply_markup=builder.as_markup())
            except Exception:
                pass
    else:
        try:
            await message_obj.reply_photo(photo, caption=card, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            try:
                await message_obj.reply_video(photo, caption=card, parse_mode="HTML", reply_markup=builder.as_markup())
            except Exception:
                await message_obj.reply(card, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "close_edit_menu")
async def cb_close_edit_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("Edit menu closed.")

@router.callback_query(F.data.startswith("edit_name_"))
async def cb_edit_name(callback: CallbackQuery, state: FSMContext):
    char_id = int(callback.data.split("_")[2])
    await state.set_state(EditCharStates.waiting_for_new_name)
    await state.update_data(edit_char_id=char_id, edit_message_id=callback.message.message_id, edit_chat_id=callback.message.chat.id)
    
    await callback.message.reply("📝 Please type the **new name** for the character (or send `/cancel` to abort):")
    await callback.answer()

@router.callback_query(F.data.startswith("edit_anime_"))
async def cb_edit_anime(callback: CallbackQuery, state: FSMContext):
    char_id = int(callback.data.split("_")[2])
    await state.set_state(EditCharStates.waiting_for_new_anime)
    await state.update_data(edit_char_id=char_id, edit_message_id=callback.message.message_id, edit_chat_id=callback.message.chat.id)
    
    await callback.message.reply("📺 Please type the **new anime name** for the character (or send `/cancel` to abort):")
    await callback.answer()

@router.callback_query(F.data.startswith("edit_rarity_"))
async def cb_edit_rarity(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    char_id = int(callback.data.split("_")[2])
    await state.set_state(EditCharStates.waiting_for_new_rarity)
    await state.update_data(edit_char_id=char_id, edit_message_id=callback.message.message_id, edit_chat_id=callback.message.chat.id)
    
    default_rarities = ["Common", "Rare", "Epic", "Legendary", "Mythical"]
    custom_stmt = select(RarityType)
    custom_res = await db.execute(custom_stmt)
    custom_rarities = [r.name.title() for r in custom_res.scalars().all()]
    all_rarities = list(set(default_rarities + custom_rarities))

    builder = InlineKeyboardBuilder()
    for r in sorted(all_rarities):
        emoji = get_rarity_emoji(r)
        builder.add(InlineKeyboardButton(text=f"{emoji} {r}", callback_data=f"sel_new_rarity_{r.lower()}"))
    builder.adjust(2)

    await callback.message.reply("💎 Please select a new rarity tier, or type one manually:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("edit_media_"))
async def cb_edit_media(callback: CallbackQuery, state: FSMContext):
    char_id = int(callback.data.split("_")[2])
    await state.set_state(EditCharStates.waiting_for_new_media)
    await state.update_data(edit_char_id=char_id, edit_message_id=callback.message.message_id, edit_chat_id=callback.message.chat.id)
    
    await callback.message.reply("📸 Please upload/send the **new photo, video, or GIF** for the character:")
    await callback.answer()

@router.message(EditCharStates.waiting_for_new_name, F.text)
async def process_edit_name(message: Message, state: FSMContext, db: AsyncSession):
    if message.text.startswith("/"):
        if message.text == "/cancel":
            await state.clear()
            await message.reply("❌ Edit cancelled.")
            return
        await message.reply("⚠️ Invalid name! Please type a new name:")
        return

    new_name = message.text.strip()
    data = await state.get_data()
    char_id = data["edit_char_id"]
    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()
    if character:
        old_name = character.name
        character.name = new_name
        await db.commit()
        await message.reply(f"✅ Character name updated to <b>{escape_html(new_name)}</b>!", parse_mode="HTML")
        await send_edit_char_menu(message, character, db, is_callback=False)
        by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        await send_character_edit_announcement(message.bot, character, "Name", old_name, new_name, by_user)
    else:
        await message.reply("❌ Error: Character not found.")
    await state.clear()

@router.message(EditCharStates.waiting_for_new_anime, F.text)
async def process_edit_anime(message: Message, state: FSMContext, db: AsyncSession):
    if message.text.startswith("/"):
        if message.text == "/cancel":
            await state.clear()
            await message.reply("❌ Edit cancelled.")
            return
        await message.reply("⚠️ Invalid name! Please type a new anime:")
        return

    new_anime = message.text.strip()
    data = await state.get_data()
    char_id = data["edit_char_id"]

    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()
    if character:
        old_anime = character.anime
        character.anime = new_anime
        await db.commit()
        await message.reply(f"✅ Character anime updated to <b>{escape_html(new_anime)}</b>!", parse_mode="HTML")
        await send_edit_char_menu(message, character, db, is_callback=False)
        by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        await send_character_edit_announcement(message.bot, character, "Anime", old_anime, new_anime, by_user)
    else:
        await message.reply("❌ Error: Character not found.")
    await state.clear()

@router.callback_query(EditCharStates.waiting_for_new_rarity, F.data.startswith("sel_new_rarity_"))
async def process_edit_rarity_cb(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    new_rarity = callback.data.replace("sel_new_rarity_", "").title()
    data = await state.get_data()
    char_id = data["edit_char_id"]

    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()
    if character:
        old_rarity = character.rarity
        character.rarity = new_rarity
        await db.commit()
        await callback.message.reply(f"✅ Character rarity updated to <b>{new_rarity}</b>!", parse_mode="HTML")
        await send_edit_char_menu(callback.message, character, db, is_callback=False)
        by_user = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.first_name
        await send_character_edit_announcement(callback.bot, character, "Rarity", old_rarity, new_rarity, by_user)
    else:
        await callback.message.reply("❌ Error: Character not found.")
    await state.clear()
    await callback.answer()

@router.message(EditCharStates.waiting_for_new_rarity, F.text)
async def process_edit_rarity_text(message: Message, state: FSMContext, db: AsyncSession):
    if message.text.startswith("/"):
        if message.text == "/cancel":
            await state.clear()
            await message.reply("❌ Edit cancelled.")
            return
        await message.reply("⚠️ Invalid option! Please select a rarity or type one manually:")
        return

    new_rarity = message.text.strip().title()
    data = await state.get_data()
    char_id = data["edit_char_id"]

    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()
    if character:
        old_rarity = character.rarity
        character.rarity = new_rarity
        await db.commit()
        await message.reply(f"✅ Character rarity updated to <b>{new_rarity}</b>!", parse_mode="HTML")
        await send_edit_char_menu(message, character, db, is_callback=False)
        by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        await send_character_edit_announcement(message.bot, character, "Rarity", old_rarity, new_rarity, by_user)
    else:
        await message.reply("❌ Error: Character not found.")
    await state.clear()

@router.message(EditCharStates.waiting_for_new_media, F.photo | F.video | F.animation)
async def process_edit_media(message: Message, state: FSMContext, db: AsyncSession):
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.animation:
        file_id = message.animation.file_id

    if not file_id:
        await message.reply("⚠️ Please send a valid photo, video, or GIF!")
        return

    data = await state.get_data()
    char_id = data["edit_char_id"]

    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()
    if character:
        character.image_url = file_id
        await db.commit()
        await message.reply("✅ Character media has been updated successfully!", parse_mode="HTML")
        await send_edit_char_menu(message, character, db, is_callback=False)
        by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        await send_character_edit_announcement(message.bot, character, "Media", "Old Media File", "New Media File", by_user)
    else:
        await message.reply("❌ Error: Character not found.")
    await state.clear()

async def send_character_edit_announcement(bot, character: Character, field_name: str, old_val: str, new_val: str, by_user_str: str):
    db_channel = "@AniVersedatabase"
    r_emoji = get_rarity_emoji(character.rarity)
    
    ist_offset = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now_ist = datetime.datetime.now(tz=ist_offset)
    time_str = now_ist.strftime("%d %b %Y, %I:%M %p IST")
    
    photo = character.image_url if character.image_url else "https://cdn.pixabay.com/photo/2022/12/01/04/35/anime-7628313_1280.jpg"
    
    if field_name == "Media":
        announcement_text = (
            "⚙️ <b>CHARACTER MEDIA UPDATED!</b>\n"
            + format_blockquote(
                f"🆔 <b>ID</b>: #{character.id:03d}\n"
                f"📛 <b>Name</b>: {escape_html(character.name)}\n"
                f"📺 <b>Anime</b>: {escape_html(character.anime)}\n"
                f"💎 <b>Rarity</b>: {r_emoji} {character.rarity}\n\n"
                f"👤 <b>By</b>: {escape_html(by_user_str)}\n"
                f"⌛️ <b>Time</b>: {time_str}"
            )
        )
    else:
        announcement_text = (
            "⚙️ <b>CHARACTER DETAILS EDITED / UPDATED!</b>\n"
            + format_blockquote(
                f"🆔 <b>ID</b>: #{character.id:03d}\n"
                f"📛 <b>Name</b>: {escape_html(character.name)}\n"
                f"📺 <b>Anime</b>: {escape_html(character.anime)}\n"
                f"💎 <b>Rarity</b>: {r_emoji} {character.rarity}\n\n"
                f"📝 <b>Edited Field</b>: {field_name}\n"
                f"❌ <b>Old Value</b>: {escape_html(old_val)}\n"
                f"✅ <b>New Value</b>: {escape_html(new_val)}\n\n"
                f"👤 <b>By</b>: {escape_html(by_user_str)}\n"
                f"⌛️ <b>Time</b>: {time_str}"
            )
        )

    try:
        try:
            await bot.send_photo(chat_id=db_channel, photo=photo, caption=announcement_text, parse_mode="HTML")
        except Exception:
            try:
                await bot.send_video(chat_id=db_channel, video=photo, caption=announcement_text, parse_mode="HTML")
            except Exception:
                try:
                    await bot.send_animation(chat_id=db_channel, animation=photo, caption=announcement_text, parse_mode="HTML")
                except Exception:
                    await bot.send_message(chat_id=db_channel, text=announcement_text, parse_mode="HTML")
    except Exception as e:
        print(f"Failed to send character edit sync to database channel: {e}")
# --- ROLE PROMOTION & DEMOTION SYSTEM ---

@router.message(Command("promote"))
async def cmd_promote(message: Message, db: AsyncSession, bot):
    if not is_owner(message):
        await message.reply("⛔ Only bot owners can promote admins!")
        return

    parts = message.text.strip().split()
    target_user_id = None
    target_username = None
    target_first_name = None
    role = None

    if message.reply_to_message:
        if len(parts) < 2:
            await message.reply("⚠️ <b>Usage:</b> Reply to someone with <code>/promote &lt;snradmin or jradmin&gt;</code>", parse_mode="HTML")
            return
        role = parts[1].strip().lower()
        target_user_id = message.reply_to_message.from_user.id
        target_username = message.reply_to_message.from_user.username
        target_first_name = message.reply_to_message.from_user.first_name
    else:
        if len(parts) < 3:
            await message.reply("⚠️ <b>Usage:</b> <code>/promote &lt;@username or user_id&gt; &lt;snradmin or jradmin&gt;</code>", parse_mode="HTML")
            return
        target_str = parts[1].strip()
        role = parts[2].strip().lower()

        if target_str.isdigit():
            target_user_id = int(target_str)
        elif target_str.startswith("@"):
            username = target_str[1:]
            stmt = select(User).where(User.username.ilike(username))
            res = await db.execute(stmt)
            target_user = res.scalar_one_or_none()
            if target_user:
                target_user_id = target_user.user_id
                target_username = target_user.username
                target_first_name = target_user.first_name
            else:
                await message.reply(f"❌ Trainer with username <b>{target_str}</b> not found in bot database.", parse_mode="HTML")
                return
        else:
            await message.reply("❌ Please provide a valid `@username` or numerical `user_id`.", parse_mode="HTML")
            return

    if role not in ["snradmin", "jradmin"]:
        await message.reply("❌ Invalid role! Choose either <code>snradmin</code> or <code>jradmin</code>.", parse_mode="HTML")
        return

    if target_user_id in config.ADMIN_IDS:
        await message.reply("❌ This user is a bot owner! They already have full privileges.")
        return

    if not target_first_name:
        stmt = select(User).where(User.user_id == target_user_id)
        res = await db.execute(stmt)
        target_user = res.scalar_one_or_none()
        if target_user:
            target_first_name = target_user.first_name
            target_username = target_user.username
        else:
            target_first_name = f"User {target_user_id}"

    stmt = select(BotAdmin).where(BotAdmin.user_id == target_user_id)
    res = await db.execute(stmt)
    admin_item = res.scalar_one_or_none()

    if admin_item:
        admin_item.role = role
    else:
        admin_item = BotAdmin(user_id=target_user_id, role=role)
        db.add(admin_item)

    await db.commit()

    text = (
        f"✅ <b>PROMOTION SUCCESSFUL!</b>\n\n"
        + format_blockquote(
            f"👤 <b>Trainer:</b> <a href=\"tg://user?id={target_user_id}\">{escape_html(target_first_name)}</a>\n"
            f"🆔 <b>ID:</b> <code>{target_user_id}</code>\n"
            f"🛡️ <b>Assigned Role:</b> <code>{role}</code>"
        )
    )
    await message.reply(text, parse_mode="HTML")

    dm_text = (
        f"🎉 <b>CONGRATULATIONS! You have been promoted to {role.upper()}!</b>\n\n"
        + format_blockquote(
            f"As a <b>{role}</b>, you have privileges to manage characters and database configuration!\n\n"
            "🔧 <b>Your Privileges & Commands:</b>\n"
            "• <code>/addchar</code> — Add a new character to database (supports custom IDs)\n"
            "• <code>/editchar &lt;id&gt;</code> — Interactive console to edit character details\n"
            "• <code>/deletechar &lt;id&gt;</code> — Delete a character and its user ownership instances\n"
            "• <code>/setimg &lt;id&gt;</code> — Update character media (reply or URL)\n"
            "• <code>/setrarity &lt;id&gt; &lt;rarity&gt;</code> — Update character rarity tier\n"
            "• <code>/settag &lt;id&gt; &lt;tag&gt;</code> — Edit trainer premium tags\n"
            "• <code>/addrarity Name | Emoji</code> — Register a custom rarity tier\n"
            "• <code>/addtochance &lt;rarity&gt;</code> — Enable wild spawn for a rarity\n"
            "• <code>/removefromchance &lt;rarity&gt;</code> — Disable spawn for a rarity\n"
            "• <code>/spawnchance</code> — Check spawn percentages\n"
            "• <code>/editspawnchance &lt;rarity&gt; &lt;weight&gt;</code> — Modify spawn chance weight\n"
            "• <code>/spawn</code> — Force spawn a character\n"
            "• <code>/adminlist</code> — View all active admins\n"
            "• <code>/admin</code> — Open Admin Console\n\n"
            "Thank you for keeping the AniVerse database clean and updated!"
        )
    )
    try:
        await bot.send_message(chat_id=target_user_id, text=dm_text, parse_mode="HTML")
    except Exception as e:
        await message.reply(f"⚠️ Promoted successfully, but could not send DM to user (they might have blocked the bot): {e}")

@router.message(Command("demote"))
async def cmd_demote(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply("⛔ Only bot owners can demote admins!")
        return

    parts = message.text.strip().split()
    target_user_id = None
    target_first_name = None

    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_first_name = message.reply_to_message.from_user.first_name
    else:
        if len(parts) < 2:
            await message.reply("⚠️ <b>Usage:</b> Reply to someone with <code>/demote</code> or type <code>/demote &lt;@username or user_id&gt;</code>", parse_mode="HTML")
            return
        target_str = parts[1].strip()

        if target_str.isdigit():
            target_user_id = int(target_str)
        elif target_str.startswith("@"):
            username = target_str[1:]
            stmt = select(User).where(User.username.ilike(username))
            res = await db.execute(stmt)
            target_user = res.scalar_one_or_none()
            if target_user:
                target_user_id = target_user.user_id
                target_first_name = target_user.first_name
            else:
                await message.reply(f"❌ Trainer with username <b>{target_str}</b> not found.", parse_mode="HTML")
                return
        else:
            await message.reply("❌ Please provide a valid `@username` or numerical `user_id`.", parse_mode="HTML")
            return

    stmt = delete(BotAdmin).where(BotAdmin.user_id == target_user_id)
    res = await db.execute(stmt)
    
    if res.rowcount > 0:
        await db.commit()
        if not target_first_name:
            target_first_name = f"User {target_user_id}"
        await message.reply(f"✅ Successfuly demoted <a href=\"tg://user?id={target_user_id}\">{escape_html(target_first_name)}</a>! They no longer have bot admin privileges.", parse_mode="HTML")
    else:
        await message.reply("❌ User is not an active admin in the database.")

@router.message(Command("adminlist", "admins"))
async def cmd_adminlist(message: Message, db: AsyncSession):
    stmt = select(BotAdmin)
    res = await db.execute(stmt)
    admins = res.scalars().all()

    admin_ids = [a.user_id for a in admins]
    user_map = {}
    if admin_ids:
        u_stmt = select(User).where(User.user_id.in_(admin_ids))
        u_res = await db.execute(u_stmt)
        for u in u_res.scalars().all():
            user_map[u.user_id] = u

    owners_list = []
    for o_id in config.ADMIN_IDS:
        stmt_u = select(User).where(User.user_id == o_id)
        res_u = await db.execute(stmt_u)
        user_u = res_u.scalar_one_or_none()
        name = escape_html(user_u.first_name) if user_u else f"Owner ID {o_id}"
        owners_list.append(f"• {name} (<code>{o_id}</code>)")

    snr_list = []
    jr_list = []
    for a in admins:
        u = user_map.get(a.user_id)
        name = escape_html(u.first_name) if u else f"User ID {a.user_id}"
        username_text = f" (@{u.username})" if u and u.username else ""
        line = f"• {name}{username_text} (<code>{a.user_id}</code>)"
        if a.role == "snradmin":
            snr_list.append(line)
        else:
            jr_list.append(line)

    text = "👑 <b>ANIVERSE BOT ADMINISTRATIVE STAFF</b>\n\n"
    
    text += "🛡️ <b>Owners & Creators:</b>\n"
    if owners_list:
        text += format_blockquote("\n".join(owners_list)) + "\n\n"
    else:
        text += "• None\n\n"

    text += "🛡️ <b>Senior Admins (snradmin):</b>\n"
    if snr_list:
        text += format_blockquote("\n".join(snr_list)) + "\n\n"
    else:
        text += format_blockquote("No senior admins registered.") + "\n\n"

    text += "🛡️ <b>Junior Admins (jradmin):</b>\n"
    if jr_list:
        text += format_blockquote("\n".join(jr_list)) + "\n"
    else:
        text += format_blockquote("No junior admins registered.") + "\n"

    await message.reply(text, parse_mode="HTML")

# --- OWNER ONLY RARITY EDIT & DELETE COMMANDS ---

@router.message(Command("delrarity", "deleterarity"))
async def cmd_delrarity(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply("⛔ Only bot owners can delete custom rarities!")
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            "⚠️ <b>Usage:</b>\n"
            "👉 <code>/delrarity &lt;rarity_name&gt;</code>\n\n"
            "Example: <code>/delrarity Divine</code>",
            parse_mode="HTML"
        )
        return

    rarity_name = parts[1].strip()
    stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        await message.reply(f"❌ Rarity tier '<b>{escape_html(rarity_name)}</b>' not found in database.", parse_mode="HTML")
        return

    actual_name = rarity_item.name
    await db.delete(rarity_item)
    await db.commit()

    RARITY_CACHE.pop(actual_name.title(), None)

    await message.reply(f"✅ Custom rarity tier '<b>{escape_html(actual_name)}</b>' has been deleted successfully and cache cleared!", parse_mode="HTML")

@router.message(Command("editrarityemoji", "editrarity"))
async def cmd_editrarityemoji(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply("⛔ Only bot owners can edit custom rarity emojis!")
        return

    parts = message.text.strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.reply(
            "⚠️ <b>Usage:</b>\n"
            "👉 <code>/editrarityemoji &lt;rarity_name&gt; &lt;new_emoji&gt;</code>\n\n"
            "Example: <code>/editrarityemoji Divine 💌</code>",
            parse_mode="HTML"
        )
        return

    rarity_name = parts[1].strip()
    new_emoji = parts[2].strip()

    stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        await message.reply(f"❌ Rarity tier '<b>{escape_html(rarity_name)}</b>' not found in database. Add it first using /addrarity.", parse_mode="HTML")
        return

    old_emoji = rarity_item.emoji
    rarity_item.emoji = new_emoji
    await db.commit()

    RARITY_CACHE[rarity_item.name.title()] = {"emoji": new_emoji}

    await message.reply(
        f"✅ Emoji updated for <b>{escape_html(rarity_item.name)}</b> rarity!\n"
        f"• <b>Old Emoji:</b> {old_emoji}\n"
        f"• <b>New Emoji:</b> {new_emoji}",
        parse_mode="HTML"
    )
