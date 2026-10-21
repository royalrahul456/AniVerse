from utils.emojis import get_emoji
import logging
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update
import config
from database.models import User, Character, UserCharacter, GroupSettings, RarityType, BotAdmin
from utils.formatters import format_blockquote, get_rarity_emoji, escape_html, get_clean_name, RARITY_CACHE
from utils.settings import set_cover_media, get_cover_media
from keyboards.inline import get_back_to_hub_keyboard
from handlers.start import get_or_create_user

logger = logging.getLogger(__name__)
router = Router()

DEFAULT_FALLBACK_PHOTO = "https://cdn.pixabay.com/photo/2022/12/01/04/35/anime-7628313_1280.jpg"
pending_user_media = {}

def clear_character_cache():
    try:
        from handlers.catch import character_cache
        character_cache.clear()
    except Exception:
        pass
def is_owner(message: Message) -> bool:
    if message.from_user and message.from_user.id in config.ADMIN_IDS:
        return True
    if message.sender_chat and message.sender_chat.id in config.ADMIN_IDS:
        return True
    return False

async def is_admin_id(user_id: int, db: AsyncSession) -> bool:
    if user_id in config.ADMIN_IDS or user_id in getattr(config, "DEFAULT_BOT_ADMINS", {}):
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

# Alias for compatibility across commands
is_admin_or_owner = is_admin

class SetCoverStates(StatesGroup):
    waiting_for_media = State()
@router.message(Command("setcover"))
async def cmd_setcover(message: Message, state: FSMContext):
    if not is_owner(message):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can configure cover media!")
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
                await message.reply(f"{get_emoji('success')} <b>{category.upper()}</b> cover updated successfully!", parse_mode="HTML")
                return

    # Otherwise, start interactive wizard
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🌌 Start Hub", callback_data="setcover_cat_start"))
    builder.add(InlineKeyboardButton(text=f"{get_emoji('error')} Tic-Tac-Toe (XO)", callback_data="setcover_cat_xo"))
    builder.add(InlineKeyboardButton(text="🎒 Harem Collection", callback_data="setcover_cat_dex"))
    builder.add(InlineKeyboardButton(text=f"{get_emoji('trophy')} Leaderboards", callback_data="setcover_cat_leaderboard"))
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
    category = callback.data.replace("setcover_cat_", f"")
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
        await message.reply(f"{get_emoji('error')} Cover configuration cancelled.")
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
        await message.reply(f"{get_emoji('warning')} Please upload a valid photo/video/GIF or send a link starting with http!")
        return

    data = await state.get_data()
    category = data["setcover_category"]

    set_cover_media(category, media_value)
    await state.clear()

    card = (
        f"{get_emoji('success')} <b>{category.upper()} BANNER COVER UPDATED!</b>\n\n"
        + format_blockquote(f"The banner cover media for <b>{category.upper()}</b> has been successfully updated!")
    )
    await message.reply(card, parse_mode="HTML")

@router.message(Command("give", "giv", "givechar", "givecoins"))
async def cmd_give(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can use give commands! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
        return
    text = message.text.strip()
    cmd_token = text.split()[0].lower()
    raw_args = text[len(cmd_token):].strip()
    reply = message.reply_to_message

    if not raw_args and not reply:
        card = (
            f"{get_emoji('gift')} <b>OWNER GIVE CONSOLE</b>\n\n"
            + format_blockquote(
                "Grant characters or coins directly to players!\n\n"
                f"{get_emoji('user')} <b>Give Character by ID:</b>\n"
                "• <code>/giv &lt;user_id&gt; &lt;character_id&gt;</code>\n"
                "• <code>/giv char &lt;user_id&gt; &lt;character_id&gt;</code>\n"
                "• Reply to a user's message with: <code>/giv &lt;character_id&gt;</code>\n\n"
                f"{get_emoji('coin')} <b>Give Coins:</b>\n"
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
        await message.reply(f"{get_emoji('warning')} Target user missing! Either reply to a player's message or specify the User ID.\n<i>Example: /giv 6593485710 55</i>", parse_mode="HTML")
        return

    if not value_str or not value_str.isdigit():
        await message.reply(f"{get_emoji('warning')} Please specify a numeric ID/amount for {mode}!", parse_mode="HTML")
        return

    val_num = int(value_str)
    user = await get_or_create_user(db, target_user_id, "", target_user_name or f"")

    if mode == "coins":
        user.coins += val_num
        await db.commit()
        await message.reply(
            f"{get_emoji('success')} <b>GAVE COINS SUCCESSFULLY!</b>\n\n"
            + format_blockquote(f"{get_emoji('coin')} Added <b>{val_num:,} coins</b> to <a href=\"tg://user?id={user.user_id}\">{escape_html(user.first_name)}</a>!\nNew Balance: <code>{user.coins:,} coins</code>"),
            parse_mode="HTML"
        )
    else:
        char_stmt = select(Character).where(Character.id == val_num)
        char_res = await db.execute(char_stmt)
        character = char_res.scalar_one_or_none()

        if not character:
            await message.reply(f"{get_emoji('error')} No character exists with ID <b>#{val_num}</b>!", parse_mode="HTML")
            return

        user.total_catches += 1
        user_char = UserCharacter(user_id=user.user_id, character_id=character.id, nickname=character.name)
        db.add(user_char)
        await db.commit()

        r_emoji = get_rarity_emoji(character.rarity)
        card_text = (
            f"{get_emoji('gift')} <b>CHARACTER GIVEN SUCCESSFULLY!</b>\n\n"
            + format_blockquote(
                f"🌟 <b>Character:</b> {escape_html(character.name)}\n"
                f"{get_emoji('tv')} <b>Anime:</b> {escape_html(character.anime)}\n"
                f"{r_emoji} <b>Rarity:</b> {r_emoji} {character.rarity}\n"
                f"{get_emoji('id')} <b>Character ID:</b> #{character.id}\n"
                f"{get_emoji('user')} <b>Receiver:</b> <a href=\"tg://user?id={user.user_id}\">{escape_html(user.first_name)}</a>"
            )
        )
        media_url = character.image_url if character.image_url else DEFAULT_FALLBACK_PHOTO
        try:
            if media_url.startswith("http"):
                await message.reply_photo(media_url, caption=card_text, parse_mode="HTML")
            else:
                if character.rarity.lower() == "amv":
                    try:
                        await message.reply_video(media_url, caption=card_text, parse_mode="HTML")
                    except Exception:
                        await message.reply_photo(DEFAULT_FALLBACK_PHOTO, caption=card_text, parse_mode="HTML")
                else:
                    try:
                        await message.reply_photo(media_url, caption=card_text, parse_mode="HTML")
                    except Exception:
                        await message.reply_photo(DEFAULT_FALLBACK_PHOTO, caption=card_text, parse_mode="HTML")
        except Exception:
            await message.reply(card_text, parse_mode="HTML")

async def resolve_target_user(target_str: str, db: AsyncSession, bot, entity_user=None) -> tuple[int | None, str | None, str | None]:
    """Resolves a user ID or @username into (user_id, username, first_name)."""
    # 0. If Telegram provided the user entity directly (e.g. text_mention)
    if entity_user:
        return entity_user.id, entity_user.username, entity_user.first_name

    target_str = target_str.strip()
    clean_username = target_str.lstrip("@").lower()

    # 1. Check if configured in DEFAULT_BOT_ADMINS
    default_admins = getattr(config, "DEFAULT_BOT_ADMINS", {})
    for def_id, def_info in default_admins.items():
        if def_info.get("username", "").lower() == clean_username or str(def_id) == target_str:
            return def_id, def_info.get("username"), def_info.get("first_name")

    # 2. Check if numeric user ID
    if target_str.isdigit():
        uid = int(target_str)
        stmt = select(User).where(User.user_id == uid)
        res = await db.execute(stmt)
        u = res.scalar_one_or_none()
        if u:
            return u.user_id, u.username, u.first_name
        try:
            chat = await bot.get_chat(uid)
            return chat.id, chat.username, chat.first_name or f"User {uid}"
        except Exception:
            return uid, None, f"User {uid}"

    # 3. Check by username in database (case-insensitive)
    if clean_username:
        stmt = select(User).where(func.lower(User.username) == clean_username)
        res = await db.execute(stmt)
        u = res.scalar_one_or_none()
        if u:
            return u.user_id, u.username, u.first_name

    # 4. Fallback to Telegram get_chat lookup
    if clean_username:
        try:
            chat = await bot.get_chat(f"@{clean_username}")
            return chat.id, chat.username, chat.first_name or f"@{clean_username}"
        except Exception:
            pass

    return None, None, None

@router.message(Command("transfersnatches", "transfersnatch", "transferall", "transfercatches"))
async def cmd_transfersnatches(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners and admins can transfer snatches!")
        return

    try:
        text = message.text or ""
        tokens = text.strip().split()
        args = tokens[1:]
        reply = message.reply_to_message

        # Helper to extract mention entities if present
        def get_entity_user_for_arg(arg_index: int):
            if not message.entities or not text:
                return None
            # Find offset of the argument
            # We check entities of type text_mention
            current_idx = 0
            for entity in message.entities:
                if entity.type == "text_mention" and entity.user:
                    # check if this entity matches arg
                    entity_str = text[entity.offset:entity.offset + entity.length]
                    if len(args) > arg_index and entity_str == args[arg_index]:
                        return entity.user
            return None

        from_user_id, from_username, from_first_name = None, None, None
        to_user_id, to_username, to_first_name = None, None, None

        if len(args) >= 2:
            # Format: /transfersnatches <from_user> <to_user>
            u1_entity = get_entity_user_for_arg(0)
            u2_entity = get_entity_user_for_arg(1)
            from_user_id, from_username, from_first_name = await resolve_target_user(args[0], db, message.bot, entity_user=u1_entity)
            to_user_id, to_username, to_first_name = await resolve_target_user(args[1], db, message.bot, entity_user=u2_entity)
        elif len(args) == 1 and reply and reply.from_user and not reply.from_user.is_bot:
            # Format: Reply to donor with /transfersnatches <to_user>
            from_user_id = reply.from_user.id
            from_username = reply.from_user.username
            from_first_name = reply.from_user.first_name
            u2_entity = get_entity_user_for_arg(0)
            to_user_id, to_username, to_first_name = await resolve_target_user(args[0], db, message.bot, entity_user=u2_entity)
        else:
            card = (
                f"{get_emoji('energy')} <b>TRANSFER ALL SNATCHES CONSOLE</b>\n\n"
                + format_blockquote(
                    "Transfer all characters/snatches from one trainer to another!\n"
                    "<i>(Bot Owners and Admins only)</i>\n\n"
                    f"{get_emoji('pointer')} <b>Usage Formats:</b>\n"
                    "• <code>/transfersnatches &lt;from_user&gt; &lt;to_user&gt;</code>\n"
                    "• Reply to donor with: <code>/transfersnatches &lt;to_user&gt;</code>\n\n"
                    "<b>Examples:</b>\n"
                    "• <code>/transfersnatches 123456789 8365981430</code>\n"
                    "• <code>/transfersnatches @OldTrainer @Sylveon_sy</code>\n"
                    "• <code>/transfersnatches @OldTrainer 8365981430</code>\n\n"
                    "💡 <i>Accepts either numeric User IDs, @usernames, or message replies!</i>"
                )
            )
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="🛠️ Admin Tools", callback_data="admin_tools"))
            await message.reply(card, parse_mode="HTML", reply_markup=builder.as_markup())
            return

        if not from_user_id:
            await message.reply(
                f"{get_emoji('error')} Could not resolve source trainer (donor) from <code>{escape_html(args[0] if args else 'N/A')}</code>.\n"
                "💡 <i>Make sure the user ID is correct or the user has started the bot so their username can be found.</i>",
                parse_mode="HTML"
            )
            return

        target_arg_to = args[1] if len(args) >= 2 else (args[0] if args else "N/A")
        if not to_user_id:
            await message.reply(
                f"{get_emoji('error')} Could not resolve destination trainer (recipient) from <code>{escape_html(target_arg_to)}</code>.\n"
                "💡 <i>Make sure the user ID is correct or the user has started the bot so their username can be found.</i>",
                parse_mode="HTML"
            )
            return

        if from_user_id == to_user_id:
            await message.reply(f"{get_emoji('error')} Source and destination trainers are the same user (ID: <code>{from_user_id}</code>)!", parse_mode="HTML")
            return

        # Count snatches to transfer
        stmt = select(func.count(UserCharacter.id)).where(UserCharacter.user_id == from_user_id)
        snatches_count = (await db.execute(stmt)).scalar() or 0

        if snatches_count == 0:
            d_name = escape_html(from_first_name or f"User {from_user_id}")
            await message.reply(f"{get_emoji('warning')} <b>{d_name}</b> (<code>{from_user_id}</code>) has <b>0</b> snatches/characters in their collection to transfer.", parse_mode="HTML")
            return

        # Transfer all UserCharacter rows
        await db.execute(
            update(UserCharacter)
            .where(UserCharacter.user_id == from_user_id)
            .values(user_id=to_user_id)
        )

        # Ensure both user objects exist in users table
        from_user_obj = await get_or_create_user(db, from_user_id, from_username or "", from_first_name or f"User {from_user_id}")
        to_user_obj = await get_or_create_user(db, to_user_id, to_username or "", to_first_name or f"User {to_user_id}")

        # Adjust total_catches counts
        to_user_obj.total_catches = (to_user_obj.total_catches or 0) + snatches_count
        from_user_obj.total_catches = max(0, (from_user_obj.total_catches or 0) - snatches_count)

        # Clear favorite character if donor had one set
        from_user_obj.favorite_character_id = None

        await db.commit()

        from_display = f"<a href=\"tg://user?id={from_user_id}\">{escape_html(from_user_obj.first_name)}</a>" + (f" (@{from_user_obj.username})" if from_user_obj.username else "")
        to_display = f"<a href=\"tg://user?id={to_user_id}\">{escape_html(to_user_obj.first_name)}</a>" + (f" (@{to_user_obj.username})" if to_user_obj.username else "")
        admin_name = escape_html(message.from_user.first_name if message.from_user else "Admin")

        card = (
            f"{get_emoji('success')} <b>SNATCHES TRANSFERRED SUCCESSFULLY!</b>\n\n"
            + format_blockquote(
                f"🎒 <b>Total Snatches Transferred:</b> <code>{snatches_count:,}</code> characters\n\n"
                f"📤 <b>From:</b> {from_display}\n"
                f"• ID: <code>{from_user_id}</code>\n"
                f"• Remaining Snatches: <code>0</code>\n\n"
                f"📥 <b>To:</b> {to_display}\n"
                f"• ID: <code>{to_user_id}</code>\n"
                f"• New Total Snatches: <code>{to_user_obj.total_catches:,}</code>\n\n"
                f"👑 <b>Authorized By:</b> {admin_name}"
            )
        )
        await message.reply(card, parse_mode="HTML")

        try:
            dm_notify = (
                f"{get_emoji('gift')} <b>COLLECTION TRANSFER RECEIVED!</b>\n\n"
                + format_blockquote(
                    f"You have received <b>{snatches_count:,}</b> characters/snatches into your harem!\n\n"
                    f"View your updated collection with <code>/harem</code>!"
                )
            )
            await message.bot.send_message(to_user_id, dm_notify, parse_mode="HTML")
        except Exception:
            pass
    except Exception as e:
        logger.exception("Error executing cmd_transfersnatches")
        await db.rollback()
        import html
        err_msg = html.escape(str(e))
        await message.reply(f"{get_emoji('error')} An error occurred while transferring snatches: <code>{err_msg}</code>", parse_mode="HTML")

@router.message(Command("addrarity"))
async def cmd_addrarity(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can add custom rarity types!")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            f"{get_emoji('sparkle')} <b>ADD CUSTOM RARITY CONSOLE</b>\n\n"
            + format_blockquote(
                "Define a new custom rarity tier for your bot!\n\n"
                f"{get_emoji('energy')} <b>Usage:</b> <code>/addrarity Name | Emoji</code>\n"
                "<b>Example:</b> <code>/addrarity Celestial | 🌌</code>"
            ),
            parse_mode="HTML"
        )
        return

    args = [x.strip() for x in parts[1].split("|")]
    if len(args) < 2:
        await message.answer(f"{get_emoji('error')} Please provide at least <b>Name | Emoji</b> separated by <code>|</code>", parse_mode="HTML")
        return

    name = args[0].title()
    emoji = args[1]

    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                custom_id = entity.custom_emoji_id
                emoji_char = message.text[entity.offset : entity.offset + entity.length]
                if emoji_char in emoji:
                    emoji = f'<tg-emoji emoji-id="{custom_id}">{emoji_char}</tg-emoji>'
                    break

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
        f"{get_emoji('sparkle')} <b>CUSTOM RARITY TIER ADDED!</b> {get_emoji('sparkle')}\n\n"
        + format_blockquote(
            f"🏷️ <b>NAME:</b> {name}\n"
            f"{emoji} <b>RARITY EMOJI:</b> {emoji}\n\n"
            f"{get_emoji('energy')} <i>Note: This rarity is not in wild spawn chance yet. Use <code>/addtochance {name}</code> to enable wild spawns!</i>"
        )
    )
    await message.answer(card, parse_mode="HTML")

@router.message(Command("addtochance", "addchance"))
async def cmd_addtochance(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can manage spawn chance!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(f"{get_emoji('warning')} <b>Usage:</b> <code>/addtochance &lt;rarity_name&gt;</code>", parse_mode="HTML")
        return

    rarity_name = parts[1].strip()
    stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        rarity_item = RarityType(name=rarity_name.title(), emoji=f"{get_emoji('sparkle')}", spawn_enabled=True)
        db.add(rarity_item)
    else:
        rarity_item.spawn_enabled = True

    await db.commit()
    await message.reply(f"{get_emoji('target')} <b>{rarity_item.name}</b> [{rarity_item.emoji}] has been added to wild spawn chance!", parse_mode="HTML")

@router.message(Command("removefromchance", "remchance", "delchance"))
async def cmd_removefromchance(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can manage spawn chance!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(f"{get_emoji('warning')} <b>Usage:</b> <code>/removefromchance &lt;rarity_name&gt;</code>", parse_mode="HTML")
        return

    rarity_name = parts[1].strip()
    stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if rarity_item:
        rarity_item.spawn_enabled = False
        await db.commit()

    await message.reply(f"🚫 <b>{rarity_name.title()}</b> has been removed from wild spawn chance!", parse_mode="HTML")

@router.message(Command("addtoclaim", "addclaim"))
async def cmd_addtoclaim(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can manage claim chance!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(f"{get_emoji('warning')} <b>Usage:</b> <code>/addtoclaim &lt;rarity_name&gt;</code>", parse_mode="HTML")
        return

    rarity_name = parts[1].strip()
    stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        rarity_item = RarityType(name=rarity_name.title(), emoji=f"{get_emoji('sparkle')}", claim_enabled=True)
        db.add(rarity_item)
    else:
        rarity_item.claim_enabled = True

    await db.commit()
    await message.reply(f"🎲 <b>{rarity_item.name}</b> [{rarity_item.emoji}] has been added to daily free claim pool!", parse_mode="HTML")

@router.message(Command("removefromclaim", "remclaim", "delclaim"))
async def cmd_removefromclaim(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can manage claim pool!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(f"{get_emoji('warning')} <b>Usage:</b> <code>/removefromclaim &lt;rarity_name&gt;</code>", parse_mode="HTML")
        return

    rarity_name = parts[1].strip()
    stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()
    if rarity_item:
        rarity_item.claim_enabled = False
        await db.commit()
    await message.reply(f"🚫 <b>{rarity_name.title()}</b> has been removed from daily free claim pool!", parse_mode="HTML")

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
    await message.reply(f"{get_emoji('error')} Character registration process has been cancelled.")

async def find_existing_character_anime(name: str, db: AsyncSession) -> str | None:
    if not name:
        return None
    raw_name = name.strip()
    
    # 1. Try exact match first
    stmt = select(Character).where(Character.name.ilike(raw_name))
    res = await db.execute(stmt)
    char = res.scalars().first()
    if char and char.anime:
        return char.anime

    # 2. Try match with clean name (emojis/symbols stripped)
    clean_name = get_clean_name(raw_name)
    if clean_name:
        stmt = select(Character).where(Character.name.ilike(f"%{clean_name}%"))
        res = await db.execute(stmt)
        char = res.scalars().first()
        if char and char.anime:
            return char.anime

        # 3. Try matching distinct words (e.g. 'Luffy' matching 'Monkey D. Luffy')
        words = [w for w in clean_name.split() if len(w) > 2]
        for w in words:
            stmt = select(Character).where(Character.name.ilike(f"%{w}%"))
            res = await db.execute(stmt)
            char = res.scalars().first()
            if char and char.anime:
                return char.anime

    return None
async def send_rarity_keyboard(message: Message, name: str, anime: str, state_data: dict, db: AsyncSession, is_callback: bool = False, callback_query: CallbackQuery = None):
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

    has_media = state_data.get("media_file_id") is not None
    media_status_str = f" (Pre-loaded from reply) {get_emoji('success')}" if has_media else ""

    text = (
        "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"{get_emoji('user')} <b>Name:</b> {escape_html(name)}\n"
        f"🎦 <b>Anime:</b> {escape_html(anime)} (Auto-filled)\n" if state_data.get("anime_autofilled") else
        f"{get_emoji('user')} <b>Name:</b> {escape_html(name)}\n"
        f"🎦 <b>Anime:</b> {escape_html(anime)}\n"
    )
    # Deduplicate fields
    text = (
        "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"{get_emoji('user')} <b>Name:</b> {escape_html(name)}\n"
        f"🎦 <b>Anime:</b> {escape_html(anime)}" + (" (Auto-filled)\n" if state_data.get("anime_autofilled") else "\n") +
        f"📸 <b>Media:</b>{media_status_str}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"{get_emoji('gem')} <b>[Step 3/4] Rarity Tier</b>\n\n"
        "Please select a rarity tier below, or type one manually:"
    )

    if is_callback and callback_query:
        try:
            await callback_query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            await callback_query.message.reply(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await message.reply(text, reply_markup=builder.as_markup(), parse_mode="HTML")

async def save_character_to_db(message: Message, data: dict, db: AsyncSession, bot, from_user) -> bool:
    name = data["name"]
    anime = data["anime"]
    rarity = data["rarity"]
    file_id = data.get("media_file_id")
    media_type = data.get("media_type", "photo")

    target_id = data.get("target_id")
    if target_id:
        existing_stmt = select(Character).where(Character.id == target_id)
        existing_res = await db.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            await message.reply(f"{get_emoji('error')} A character with ID {target_id} was just registered! Aborted.", parse_mode="HTML")
            return False
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
    clear_character_cache()
    r_emoji = get_rarity_emoji(rarity)
    card = (
        "⛩️ <b>CHARACTER FULLY REGISTERED!</b> ⛩️\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        + format_blockquote(
            f"{get_emoji('id')} <b>ID:</b> #{character.id}\n"
            f"{get_emoji('user')} <b>NAME:</b> {escape_html(character.name)}\n"
            f"🎦 <b>ANIME:</b> {escape_html(character.anime)}\n"
            f"{r_emoji} <b>RARITY:</b> {r_emoji} {character.rarity}"
        )
    )

    try:
        if file_id:
            if media_type == "photo":
                await bot.send_photo(chat_id=message.chat.id, photo=file_id, caption=card, parse_mode="HTML")
            elif media_type == "video":
                await bot.send_video(chat_id=message.chat.id, video=file_id, caption=card, parse_mode="HTML")
            elif media_type == "animation":
                await bot.send_animation(chat_id=message.chat.id, animation=file_id, caption=card, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=message.chat.id, text=card, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=message.chat.id, text=card, parse_mode="HTML")
    except Exception:
        try:
            await bot.send_message(chat_id=message.chat.id, text=card, parse_mode="HTML")
        except Exception:
            pass

    # DM Showcase
    if message.chat.type != "private" and from_user and file_id:
        try:
            if media_type in ["video", "animation"]:
                await bot.send_video(from_user.id, file_id, caption=f"📬 <b>Character Showcase (Sent to DM):</b>\n\n{card}", parse_mode="HTML")
            else:
                await bot.send_photo(from_user.id, file_id, caption=f"📬 <b>Character Showcase (Sent to DM):</b>\n\n{card}", parse_mode="HTML")
        except Exception:
            pass

    # Database Channel Announcement Sync
    db_channel = "@AniVersedatabase"
    img_check = f"{get_emoji('success')}" if media_type == "photo" else f"{get_emoji('error')}"
    vid_check = f"{get_emoji('success')}" if media_type in ["video", "animation"] else f"{get_emoji('error')}"
    by_user = "Unknown Admin"
    if from_user:
        by_user = f"@{from_user.username}" if from_user.username else from_user.first_name

    ist_offset = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now_ist = datetime.datetime.now(tz=ist_offset)
    time_str = now_ist.strftime("%d %b %Y, %I:%M %p IST")

    announcement_text = (
        f"{get_emoji('sparkle')} <b>NEW CHARACTER MEDIA ADDED!</b>\n"
        + format_blockquote(
            f"{get_emoji('id')} <b>ID</b>: #{character.id:03d}\n"
            f"📛 <b>Name</b>: {escape_html(character.name)}\n"
            f"{get_emoji('tv')} <b>Anime</b>: {escape_html(character.anime)}\n"
            f"{get_emoji('gem')} <b>Rarity</b>: {r_emoji} {character.rarity}\n"
            f"🖼️ <b>Image</b>: {img_check}\n"
            f"🎥 <b>Video</b>: {vid_check}\n"
            f"{get_emoji('user')} <b>By</b>: {escape_html(by_user)}\n"
            f"⌛️ <b>Time</b>: {time_str}"
        )
    )

    try:
        if file_id:
            if media_type == "photo":
                await bot.send_photo(chat_id=db_channel, photo=file_id, caption=announcement_text, parse_mode="HTML")
            elif media_type == "video":
                await bot.send_video(chat_id=db_channel, video=file_id, caption=announcement_text, parse_mode="HTML")
            elif media_type == "animation":
                await bot.send_animation(chat_id=db_channel, animation=file_id, caption=announcement_text, parse_mode="HTML")
    except Exception as e:
        print(f"Failed to send character sync to database channel: {e}")

    return True

@router.message(Command("addchar"))
async def cmd_addchar(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin(message, db):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners and admins can add characters!")
        return

    if message.chat.type != "private":
        bot_info = await message.bot.get_me()
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="💬 Start in Private Chat", url=f"https://t.me/{bot_info.username}?start=addchar"))
        await message.reply(
            "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n\n"
            f"{get_emoji('warning')} Character registration requires text input steps. To prevent chat clutter and conflicts in groups, please complete this in my **Private Chat (DM)**!\n\n"
            "Click the button below to start:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return
    parts = message.text.split(maxsplit=1)
    target_id = None
    cmd_arg_name = None

    if len(parts) > 1:
        arg = parts[1].strip()
        subparts = arg.split(maxsplit=1)
        if subparts[0].isdigit():
            target_id = int(subparts[0])
            stmt = select(Character).where(Character.id == target_id)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                await message.reply(f"{get_emoji('error')} A character with ID <b>{target_id}</b> already exists!", parse_mode="HTML")
                return
            if len(subparts) > 1:
                cmd_arg_name = subparts[1].strip()
        else:
            cmd_arg_name = arg

    name = cmd_arg_name
    media_file_id = None
    media_type = None

    if message.reply_to_message:
        reply = message.reply_to_message
        if reply.photo:
            media_file_id = reply.photo[-1].file_id
            media_type = "photo"
        elif reply.video:
            media_file_id = reply.video.file_id
            media_type = "video"
        elif reply.animation:
            media_file_id = reply.animation.file_id
            media_type = "animation"
        
        if not name:
            name = (reply.text or reply.caption or "").strip()

    await state.clear()
    
    state_data = {}
    if target_id is not None:
        state_data["target_id"] = target_id
    if media_file_id:
        state_data["media_file_id"] = media_file_id
        state_data["media_type"] = media_type
    
    msg_id_text = f" at ID <b>#{target_id}</b>" if target_id is not None else ""

    if name:
        state_data["name"] = name
        
        anime = await find_existing_character_anime(name, db)
        if anime:
            state_data["anime"] = anime
            state_data["anime_autofilled"] = True
            await state.update_data(**state_data)
            await state.set_state(AddCharStates.waiting_for_rarity)
            await send_rarity_keyboard(message, name, anime, state_data, db)
        else:
            await state.update_data(**state_data)
            await state.set_state(AddCharStates.waiting_for_anime)
            await message.reply(
                "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"{get_emoji('user')} <b>Name:</b> {escape_html(name)}\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"{get_emoji('tv')} <b>[Step 2/4] Anime Series</b>\n\n"
                "Please type the name of the anime series this character belongs to:",
                parse_mode="HTML"
            )
    else:
        if state_data:
            await state.update_data(**state_data)
        await state.set_state(AddCharStates.waiting_for_name)
        await message.reply(
            "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>[Step 1/4] Character Name</b>{msg_id_text}\n\n"
            "Please type the name of the character (or send `/cancel` to abort):",
            parse_mode="HTML"
        )

@router.message(AddCharStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext, db: AsyncSession):
    try:
        if message.text and message.text.strip() == "/cancel":
            await state.clear()
            await message.reply(f"{get_emoji('error')} Character registration process has been cancelled.")
            return

        if message.chat.type in ["group", "supergroup"]:
            is_reply_to_bot = (
                message.reply_to_message 
                and message.reply_to_message.from_user 
                and message.reply_to_message.from_user.is_bot
            )
            is_reply_to_other = (
                message.reply_to_message 
                and not is_reply_to_bot
            )
            if not is_reply_to_bot and not is_reply_to_other:
                return

        name = None
        media_file_id = None
        media_type = None

        if message.reply_to_message:
            reply = message.reply_to_message
            if reply.photo:
                media_file_id = reply.photo[-1].file_id
                media_type = "photo"
            elif reply.video:
                media_file_id = reply.video.file_id
                media_type = "video"
            elif reply.animation:
                media_file_id = reply.animation.file_id
                media_type = "animation"
            
            is_reply_to_bot = (
                reply.from_user 
                and reply.from_user.is_bot
            )
            if not is_reply_to_bot:
                name = (reply.text or reply.caption or f"").strip()

        if not name:
            text_source = message.text or message.caption
            if text_source:
                if text_source.startswith("/"):
                    await message.reply(f"{get_emoji('warning')} Invalid name! Please type a text name for the character:")
                    return
                name = text_source.strip()

        if not name:
            await message.reply(f"{get_emoji('warning')} Could not extract a character name. Please type the name of the character:")
            return

        state_data = await state.get_data()
        state_data["name"] = name
        if media_file_id:
            state_data["media_file_id"] = media_file_id
            state_data["media_type"] = media_type
        await state.update_data(**state_data)

        anime = await find_existing_character_anime(name, db)
        if anime:
            state_data["anime"] = anime
            state_data["anime_autofilled"] = True
            await state.update_data(**state_data)
            await state.set_state(AddCharStates.waiting_for_rarity)
            await send_rarity_keyboard(message, name, anime, state_data, db)
        else:
            await state.set_state(AddCharStates.waiting_for_anime)
            await message.reply(
                "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"{get_emoji('tv')} <b>[Step 2/4] Anime Series</b>\n\n"
                "Please type the name of the anime series this character belongs to:",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error in process_name: {e}", exc_info=True)
        await message.reply(f"{get_emoji('error')} An error occurred in process_name: <code>{escape_html(str(e))}</code>", parse_mode="HTML")

@router.message(AddCharStates.waiting_for_anime)
async def process_anime(message: Message, state: FSMContext, db: AsyncSession):
    try:
        if message.text and message.text.strip() == "/cancel":
            await state.clear()
            await message.reply(f"{get_emoji('error')} Character registration process has been cancelled.")
            return

        if message.chat.type in ["group", "supergroup"]:
            is_reply_to_bot = (
                message.reply_to_message 
                and message.reply_to_message.from_user 
                and message.reply_to_message.from_user.is_bot
            )
            if not is_reply_to_bot:
                return

        if not message.text or message.text.startswith("/"):
            await message.reply(f"{get_emoji('warning')} Invalid anime! Please type the name of the anime series:")
            return

        anime_name = message.text.strip()
        await state.update_data(anime=anime_name)
        await state.set_state(AddCharStates.waiting_for_rarity)

        state_data = await state.get_data()
        name = state_data["name"]
        await send_rarity_keyboard(message, name, anime_name, state_data, db)
    except Exception as e:
        logger.error(f"Error in process_anime: {e}", exc_info=True)
        await message.reply(f"{get_emoji('error')} An error occurred in process_anime: <code>{escape_html(str(e))}</code>", parse_mode="HTML")

@router.callback_query(F.data.startswith("sel_rarity_"))
async def process_rarity_callback(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    try:
        current_state = await state.get_state()
        if current_state != AddCharStates.waiting_for_rarity.state:
            await callback.answer(f"{get_emoji('warning')} This menu is no longer active.", show_alert=True)
            return

        rarity_val = callback.data.replace("sel_rarity_", "").title()
        await state.update_data(rarity=rarity_val)
        
        state_data = await state.get_data()
        
        if state_data.get("media_file_id"):
            await save_character_to_db(callback.message, state_data, db, bot=callback.bot, from_user=callback.from_user)
            await state.clear()
            await callback.answer(f"{get_emoji('success')} Character registered successfully!")
            try:
                await callback.message.delete()
            except Exception:
                pass
            return

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
    except Exception as e:
        logger.error(f"Error in process_rarity_callback: {e}", exc_info=True)
        await callback.answer(f"{get_emoji('error')} Error: {str(e)}", show_alert=True)

@router.message(AddCharStates.waiting_for_rarity)
async def process_rarity_text(message: Message, state: FSMContext, db: AsyncSession, bot):
    try:
        if message.text and message.text.strip() == "/cancel":
            await state.clear()
            await message.reply(f"{get_emoji('error')} Character registration process has been cancelled.")
            return

        if message.chat.type in ["group", "supergroup"]:
            is_reply_to_bot = (
                message.reply_to_message 
                and message.reply_to_message.from_user 
                and message.reply_to_message.from_user.is_bot
            )
            if not is_reply_to_bot:
                return

        if not message.text or message.text.startswith("/"):
            await message.reply(f"{get_emoji('warning')} Invalid option! Please select a rarity tier or type one manually:")
            return

        rarity_val = message.text.strip().title()
        await state.update_data(rarity=rarity_val)
        
        state_data = await state.get_data()
        
        if state_data.get("media_file_id"):
            await save_character_to_db(message, state_data, db, bot, message.from_user)
            await state.clear()
            return

        await state.set_state(AddCharStates.waiting_for_media)
        await message.reply(
            "⛩️ <b>ADD ANIME CHARACTER CONSOLE</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📸 <b>[Step 4/4] Media Upload</b>\n\n"
            f"Selected: <b>{rarity_val}</b>\n"
            "Please upload a photo, video, or GIF for the character:",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in process_rarity_text: {e}", exc_info=True)
        await message.reply(f"{get_emoji('error')} An error occurred in process_rarity_text: <code>{escape_html(str(e))}</code>", parse_mode="HTML")

@router.message(AddCharStates.waiting_for_media, F.photo | F.video | F.animation)
async def process_media(message: Message, state: FSMContext, db: AsyncSession, bot):
    try:
        if message.chat.type in ["group", "supergroup"]:
            is_reply_to_bot = (
                message.reply_to_message 
                and message.reply_to_message.from_user 
                and message.reply_to_message.from_user.is_bot
            )
            if not is_reply_to_bot:
                return

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
            await message.reply(f"{get_emoji('warning')} Please send a valid photo, video, or GIF!")
            return

        data = await state.get_data()
        data["media_file_id"] = file_id
        data["media_type"] = media_type

        success = await save_character_to_db(message, data, db, bot, message.from_user)
        if success:
            await state.clear()
    except Exception as e:
        logger.error(f"Error in process_media: {e}", exc_info=True)
        await message.reply(f"{get_emoji('error')} An error occurred in process_media: <code>{escape_html(str(e))}</code>", parse_mode="HTML")

@router.message(Command("setimg", "updateimg", "setphoto"))
async def cmd_setimg(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can use setimg! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
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
                f"{get_emoji('energy')} <b>Usage:</b>\n"
                "• Reply to a photo/video with: <code>/setimg &lt;character_id&gt;</code>\n"
                "• Or send a photo with caption: <code>/setimg &lt;character_id&gt;</code>\n"
                "• Or provide URL: <code>/setimg &lt;character_id&gt; https://image.url/photo.jpg</code>"
            )
        )
        await message.reply(card, parse_mode="HTML")
        return

    if not char_id_str.isdigit():
        await message.reply(f"{get_emoji('error')} Character ID must be a numeric integer!")
        return

    char_id = int(char_id_str)
    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()

    if not character:
        await message.reply(f"{get_emoji('error')} No character exists with ID <b>#{char_id}</b>!", parse_mode="HTML")
        return

    character.image_url = media_to_set
    await db.commit()
    clear_character_cache()
    r_emoji = get_rarity_emoji(character.rarity)
    card = (
        f"{get_emoji('success')} <b>CHARACTER IMAGE UPDATED!</b>\n\n"
        + format_blockquote(
            f"{get_emoji('id')} <b>ID:</b> #{character.id}\n"
            f"{get_emoji('user')} <b>NAME:</b> {escape_html(character.name)}\n"
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
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can delete characters! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(f"{get_emoji('warning')} <b>Usage:</b> <code>/deletechar &lt;character_id or name&gt;</code>", parse_mode="HTML")
        return

    query_str = parts[1].strip()
    if query_str.isdigit():
        stmt = select(Character).where(Character.id == int(query_str))
    else:
        stmt = select(Character).where(Character.name.ilike(query_str))

    res = await db.execute(stmt)
    character = res.scalar_one_or_none()

    if not character:
        await message.reply(f"{get_emoji('error')} No character found matching <b>{escape_html(query_str)}</b>!", parse_mode="HTML")
        return

    char_id = character.id
    char_name = character.name
    char_anime = character.anime

    await db.execute(delete(UserCharacter).where(UserCharacter.character_id == char_id))
    await db.delete(character)
    await db.commit()
    clear_character_cache()
    card = (
        f"🗑️ <b>CHARACTER DELETED FROM BOT!</b>\n\n"
        + format_blockquote(
            f"{get_emoji('id')} <b>ID:</b> #{char_id}\n"
            f"{get_emoji('user')} <b>NAME:</b> {escape_html(char_name)}\n"
            f"🎦 <b>ANIME:</b> {escape_html(char_anime)}\n\n"
            f"{get_emoji('warning')} Successfully removed character and all user ownership instances from database!"
        )
    )
    await message.reply(card, parse_mode="HTML")

@router.message(Command("setrarity"))
async def cmd_setrarity(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can set rarity! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
        return    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(f"{get_emoji('warning')} <b>Usage:</b> <code>/setrarity &lt;character_id&gt; &lt;new_rarity&gt;</code>", parse_mode="HTML")
        return

    char_id = parts[1]
    new_rarity = parts[2].title()

    stmt = select(Character).where(Character.id == int(char_id)) if char_id.isdigit() else select(Character).where(Character.name.ilike(char_id))
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()

    if not character:
        await message.answer(f"{get_emoji('error')} Character not found!")
        return

    character.rarity = new_rarity
    await db.commit()
    
    r_emoji = get_rarity_emoji(new_rarity)
    await message.answer(f"{get_emoji('success')} Updated <b>{escape_html(character.name)}</b> rarity to {r_emoji} <b>{new_rarity}</b>!", parse_mode="HTML")

@router.message(Command("spawn"))
async def cmd_admin_spawn(message: Message, db: AsyncSession, bot):
    if not await is_admin(message, db):
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can spawn! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
        return    
    parts = message.text.split(maxsplit=1)
    rarity_arg = parts[1].strip() if len(parts) > 1 else None

    from handlers.catch import spawn_character
    success = await spawn_character(message.chat.id, db, bot, custom_rarity=rarity_arg)
    if not success:
        await message.answer(f"{get_emoji('warning')} Could not spawn character. Check if characters exist in database.")

@router.message(Command("stats"))
async def cmd_stats(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can view stats! (Your ID: <code>{message.from_user.id if message.from_user else 'Unknown'}</code>)", parse_mode="HTML")
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
            f"{get_emoji('sparkle')} <b>Total Rarity Types:</b> {rarity_cnt + 5:,}\n"
            f"🎒 <b>Total Caught Characters:</b> {catches_cnt:,}"
        )
    )
    await message.answer(text, parse_mode="HTML")



@router.message(Command("addpremium"))
async def cmd_addpremium(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can manage premium status.")
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
            await message.reply(f"{get_emoji('warning')} Format: <code>/addpremium &lt;user_id&gt; &lt;days&gt;</code> or reply to a user with <code>/addpremium &lt;days&gt;</code>", parse_mode="HTML")
            return
        if not parts[1].isdigit() or not parts[2].isdigit():
            await message.reply(f"{get_emoji('warning')} Both user_id and days must be numbers.", parse_mode="HTML")
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
        f"{get_emoji('crown')} <b>Premium status granted!</b>\n\n"
        f"● <b>User ID:</b> {target_id}\n"
        f"● <b>Days added:</b> {days}\n"
        f"● <b>Remaining time:</b> {delta.days}d {delta.seconds // 3600}h",
        parse_mode="HTML"
    )

@router.message(Command("settag"))
async def cmd_settag(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners and admins can set player tags.")
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
            await message.reply(f"{get_emoji('warning')} Format: <code>/settag &lt;user_id&gt; &lt;tag_text&gt;</code> or reply to a user with <code>/settag &lt;tag_text&gt;</code>", parse_mode="HTML")
            return
        if not parts[1].isdigit():
            await message.reply(f"{get_emoji('warning')} User ID must be a number.", parse_mode="HTML")
            return
        target_id = int(parts[1])
        tag_text = parts[2].strip()

    if not tag_text:
        await message.reply(f"{get_emoji('warning')} Tag text cannot be empty.")
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
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can manage premium status.")
        return
    text = message.text.strip()
    parts = text.split(maxsplit=1)

    target_id = None

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        if len(parts) < 2 or not parts[1].isdigit():
            await message.reply(f"{get_emoji('warning')} Format: <code>/removepremium &lt;user_id&gt;</code> or reply to a user with <code>/removepremium</code>", parse_mode="HTML")
            return
        target_id = int(parts[1])

    target_user = await get_or_create_user(db, target_id, "", "")
    target_user.premium_until = None
    target_user.premium_tag = None
    await db.commit()

    await message.reply(f"{get_emoji('error')} <b>Premium status revoked</b> for user ID {target_id}.", parse_mode="HTML")

@router.message(Command("ownerhelp", "owner", "adminhelp", "admin"))
async def cmd_ownerhelp(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        return
    is_owner_user = is_owner(message)
    console_title = f"{get_emoji('crown')} AniVerse Owner Console" if is_owner_user else "⚙️ AniVerse Admin Console"
    
    card = (
        f"╭───「 {console_title} 」───╮\n"
        "│\n"
        f"│  Welcome, <b>{escape_html(message.from_user.first_name)}</b>!\n"
        "│\n"
        f"│  {get_emoji('energy')} <b>ADMIN COMMANDS (You can use these):</b>\n"
        "│  ├─➩ <code>/stats</code> — View bot stats\n"
        "│  ├─➩ <code>/spawn</code> — Force spawn wild character\n"
        "│  ├─➩ <code>/transfersnatches &lt;from&gt; &lt;to&gt;</code> — Transfer all catches\n"
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
        "│  ├─➩ <code>/editspawnchance</code> — Adjust spawn chance (%)\n"
        "│  ├─➩ <code>/adminlist</code> — View all active admins\n"
    )
    
    if is_owner_user:
        card += (
            "│\n"
            f"│  {get_emoji('crown')} <b>OWNER ONLY COMMANDS:</b>\n"
            "│  ├─➩ <code>/promote &lt;user&gt; &lt;role&gt;</code> — Grant admin\n"
            "│  ├─➩ <code>/demote &lt;user&gt;</code> — Revoke admin role\n"
            "│  ├─➩ <code>/delrarity &lt;rarity&gt;</code> — Delete custom rarity\n"
            "│  ├─➩ <code>/editrarityemoji &lt;rarity&gt; &lt;emoji&gt;</code> — Edit emoji\n"
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
        builder.row(InlineKeyboardButton(text=f"{get_emoji('back')} Back to Hub Menu", callback_data="dm_home"))

    try:
        await message.reply_photo(get_cover_media("start"), caption=card, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await message.reply(card, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "admin_tools")
async def cb_admin_tools(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_id(callback.from_user.id, db):
        await callback.answer(f"{get_emoji('no_entry')} Access denied!", show_alert=True)
        return

    is_owner_user = callback.from_user.id in config.ADMIN_IDS
    console_title = f"{get_emoji('crown')} AniVerse Owner Console" if is_owner_user else "⚙️ AniVerse Admin Console"

    card = (
        f"╭───「 {console_title} 」───╮\n"
        "│\n"
        f"│  Welcome, <b>{escape_html(callback.from_user.first_name)}</b>!\n"
        "│\n"
        f"│  {get_emoji('energy')} <b>Management Commands:</b>\n"
        "│  ├─➩ <code>/stats</code> — Server stats & DB info\n"
        "│  ├─➩ <code>/spawn</code> — Force spawn wild character\n"
        "│  ├─➩ <code>/transfersnatches &lt;from&gt; &lt;to&gt;</code> — Transfer all catches\n"
        "│  ├─➩ <code>/setcover &lt;mode&gt;</code> — Set covers (start, xo, dex)\n"
        "│  │\n"
        "│  🎴 <b>Character Editing:</b>\n"
        "│  ├─➩ <code>/addchar &lt;details&gt;</code> — Create character\n"
        "│  ├─➩ <code>/editchar &lt;id&gt;</code> — Edit character details\n"
        "│  ├─➩ <code>/deletechar &lt;id&gt;</code> — Delete character\n"
        "│  ├─➩ <code>/setimg &lt;id&gt; &lt;url&gt;</code> — Update photo\n"
        "│  ├─➩ <code>/setrarity &lt;id&gt; &lt;rarity&gt;</code> — Update rarity\n"
        "│  ├─➩ <code>/settag &lt;id&gt; &lt;tag&gt;</code> — Update tag\n"
        "│  │\n"
        f"│  {get_emoji('coin')} <b>Player & Wager controls:</b>\n"
        "│  ├─➩ <code>/give &lt;user&gt; &lt;amount/char&gt;</code> — Give coins/chars\n"
        "│  ├─➩ <code>/addpremium &lt;user&gt;</code> — Grant VIP status\n"
        "│  ├─➩ <code>/removepremium &lt;user&gt;</code> — Revoke VIP status\n"
        "│  │\n"
        "│  📈 <b>Database Config:</b>\n"
        "│  ├─➩ <code>/addrarity &lt;rarity&gt; &lt;emoji&gt;</code>\n"
        "│  ├─➩ <code>/addtochance &lt;rarity&gt;</code>\n"
        "│  ├─➩ <code>/removefromchance &lt;rarity&gt;</code>\n"
        "│  \n"
        "╰──────────────────────────╯"
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Transfer Snatches", callback_data="admin_transfersnatches")
    )
    builder.row(InlineKeyboardButton(text=f"{get_emoji('back')} Back to Hub Menu", callback_data="dm_home"))
    
    from handlers.start import send_or_edit_start
    await send_or_edit_start(callback.message, get_cover_media("start"), card, builder.as_markup(), is_callback=True)
    await callback.answer()

@router.callback_query(F.data == "admin_transfersnatches")
async def cb_admin_transfersnatches(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_id(callback.from_user.id, db):
        await callback.answer(f"{get_emoji('no_entry')} Access denied!", show_alert=True)
        return

    card = (
        f"{get_emoji('energy')} <b>TRANSFER ALL SNATCHES CONSOLE</b>\n\n"
        + format_blockquote(
            "Transfer all characters/snatches from one trainer to another!\n"
            "<i>(Bot Owners and Admins only)</i>\n\n"
            f"{get_emoji('pointer')} <b>How to use:</b>\n"
            "• Type in chat: <code>/transfersnatches &lt;from_user&gt; &lt;to_user&gt;</code>\n"
            "• Or reply to a donor's message with: <code>/transfersnatches &lt;to_user&gt;</code>\n\n"
            "<b>Examples:</b>\n"
            "• <code>/transfersnatches 123456789 8365981430</code>\n"
            "• <code>/transfersnatches @OldTrainer @Sylveon_sy</code>\n"
            "• <code>/transfersnatches @OldTrainer 8365981430</code>\n\n"
            "💡 <i>Accepts either numeric Telegram User IDs, @usernames, or message replies!</i>"
        )
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛠️ Admin Tools", callback_data="admin_tools"))
    builder.row(InlineKeyboardButton(text=f"{get_emoji('back')} Back to Hub Menu", callback_data="dm_home"))

    from handlers.start import send_or_edit_start
    await send_or_edit_start(callback.message, get_cover_media("start"), card, builder.as_markup(), is_callback=True)
    await callback.answer()

@router.message(Command("spawnchance", "spawnchances"))
async def cmd_spawnchance(message: Message, db: AsyncSession):
    stmt = select(RarityType).where(RarityType.spawn_enabled == True)
    res = await db.execute(stmt)
    rarities = res.scalars().all()
    
    if not rarities:
        await message.reply(f"{get_emoji('warning')} No rarities are currently enabled for wild spawn.")
        return
        
    lines = []
    # Sort by percentage descending
    rarities.sort(key=lambda x: x.weight, reverse=True)
    
    for r in rarities:
        from utils.formatters import get_rarity_emoji
        r_emoji = get_rarity_emoji(r.name)
        lines.append(f"{r_emoji} <b>{r.name}</b>: <b>{r.weight}%</b>")        
    text = (
        f"{get_emoji('target')} <b>WILD CHARACTER SPAWN CHANCES</b>\n\n"
        + format_blockquote("\n".join(lines))
    )
    await message.reply(text, parse_mode="HTML")
class EditSpawnChanceStates(StatesGroup):
    waiting_for_weight = State()

class EditClaimChanceStates(StatesGroup):
    waiting_for_claim_weight = State()
@router.message(Command("editspawnchance", "setspawnchance"))
async def cmd_editspawnchance(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can edit spawn chance!")
        return

    parts = message.text.strip().split()
    if len(parts) >= 3:
        # Support quick command line method: /editspawnchance Rarity Percentage
        rarity_name = parts[1].strip()
        pct_str = parts[2].strip()

        if not pct_str.isdigit():
            await message.reply(f"{get_emoji('error')} Percentage must be a valid positive number.")
            return

        pct = int(pct_str)
        if pct < 0:
            await message.reply(f"{get_emoji('error')} Percentage cannot be negative.")
            return

        stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
        res = await db.execute(stmt)
        rarity_item = res.scalar_one_or_none()

        if not rarity_item:
            await message.reply(f"{get_emoji('error')} Rarity tier '<b>{escape_html(rarity_name)}</b>' not found. Add it first using /addrarity.", parse_mode="HTML")
            return

        rarity_item.weight = pct
        await db.commit()

        await message.reply(f"{get_emoji('success')} Updated spawn chance for <b>{escape_html(rarity_item.name)}</b> to <b>{pct}%</b>!", parse_mode="HTML")
        return

    # Show interactive menu - ONLY show rarities where spawn_enabled == True
    stmt = select(RarityType).where(RarityType.spawn_enabled == True)
    res = await db.execute(stmt)
    rarities = res.scalars().all()
    if not rarities:
        await message.reply(f"{get_emoji('warning')} No rarities are currently enabled for wild spawn.")
        return

    builder = InlineKeyboardBuilder()
    for r in rarities:
        from utils.formatters import get_rarity_emoji
        r_emoji = get_rarity_emoji(r.name)
        builder.row(InlineKeyboardButton(
            text=f"{r_emoji} {r.name} ({r.weight}%)",
            callback_data=f"spawn_edit_sel:{r.id}"
        ))
    builder.row(InlineKeyboardButton(text=f"{get_emoji('error')} Cancel", callback_data="spawn_edit_cancel"))

    text = (
        f"{get_emoji('target')} <b>ANIVERSE SPAWN CHANCE EDITOR</b>\n\n"
        + format_blockquote(
            "Select a rarity tier below to adjust its spawn probability percentage.\n\n"
            f"{get_emoji('warning')} Only rarities enabled for wild spawns are listed here. To enable a new rarity, use <code>/addtochance &lt;rarity&gt;</code>."
        )
    )
    await message.reply(text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "spawn_edit_cancel")
async def cb_spawn_edit_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(f"{get_emoji('error')} Spawn chance editing cancelled.")
    await callback.answer()
@router.callback_query(F.data.startswith("spawn_edit_sel:"))
async def cb_spawn_edit_sel(callback: CallbackQuery, db: AsyncSession, state: FSMContext):
    if not await is_admin_id(callback.from_user.id, db):
        await callback.answer("Unauthorized!", show_alert=True)
        return

    rarity_id = int(callback.data.split(":")[1])
    stmt = select(RarityType).where(RarityType.id == rarity_id)
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        await callback.answer(f"{get_emoji('error')} Rarity not found.", show_alert=True)
        return

    await state.set_state(EditSpawnChanceStates.waiting_for_weight)
    await state.update_data(edit_rarity_id=rarity_id)

    from utils.formatters import get_rarity_emoji
    r_emoji = get_rarity_emoji(rarity_item.name)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"{get_emoji('error')} Cancel", callback_data="spawn_edit_cancel"))

    text = (
        f"⚙️ <b>Adjusting Spawn Chance:</b> {r_emoji} <b>{rarity_item.name}</b>\n\n"
        + format_blockquote(
            f"{get_emoji('user')} Administrator: {escape_html(callback.from_user.first_name)}\n"
            f"📊 Current Chance: <code>{rarity_item.weight}%</code>\n\n"
            f"{get_emoji('pointer')} Please type and send the **new percentage** (positive integer, e.g. 20 for 20%) in the chat."
        )
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()
@router.message(EditSpawnChanceStates.waiting_for_weight)
async def process_spawn_edit_weight(message: Message, db: AsyncSession, state: FSMContext):
    if not await is_admin(message, db):
        await message.reply(f"{get_emoji('no_entry')} Unauthorized!")
        await state.clear()
        return

    data = await state.get_data()
    rarity_id = data.get("edit_rarity_id")

    pct_str = message.text.strip()
    if not pct_str.isdigit():
        await message.reply(f"{get_emoji('error')} Invalid input! Please send a valid positive number for percentage.")
        return

    pct = int(pct_str)
    if pct < 0:
        await message.reply(f"{get_emoji('error')} Percentage cannot be negative. Please enter a valid positive number.")
        return

    stmt = select(RarityType).where(RarityType.id == rarity_id)
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        await message.reply(f"{get_emoji('error')} Rarity not found. State cleared.")
        await state.clear()
        return

    old_pct = rarity_item.weight
    rarity_item.weight = pct
    await db.commit()
    await state.clear()

    # Get direct percentages for enabled spawn chances
    stmt_all = select(RarityType).where(RarityType.spawn_enabled == True)
    res_all = await db.execute(stmt_all)
    rarities = res_all.scalars().all()

    lines = []
    rarities.sort(key=lambda x: x.weight, reverse=True)
    
    for r in rarities:
        from utils.formatters import get_rarity_emoji
        r_emoji = get_rarity_emoji(r.name)
        lines.append(f"{r_emoji} <b>{r.name}</b>: <b>{r.weight}%</b>")

    text = (
        f"{get_emoji('success')} <b>SPAWN CHANCE UPDATED!</b>\n\n"
        + format_blockquote(
            f"{get_emoji('gem')} <b>Rarity:</b> {escape_html(rarity_item.name)}\n"
            f"📉 Old Chance: <code>{old_pct}%</code>\n"
            f"📈 New Chance: <code>{pct}%</code>\n\n"
            f"{get_emoji('target')} <b>Current Spawn Probabilities:</b>\n"
            + "\n".join(lines)
        )
    )
    await message.reply(text, parse_mode="HTML")

@router.message(Command("editclaimchance", "setclaimchance"))
async def cmd_editclaimchance(message: Message, db: AsyncSession):
    if not await is_admin(message, db):
        await message.answer(f"{get_emoji('no_entry')} Only bot owners and admins can edit claim chances!")
        return

    parts = message.text.strip().split()
    if len(parts) >= 3:
        rarity_name = parts[1].strip()
        weight_str = parts[2].strip()

        if not weight_str.isdigit():
            await message.reply(f"{get_emoji('error')} Chance value must be a valid positive number.")
            return

        weight = int(weight_str)
        if weight < 0:
            await message.reply(f"{get_emoji('error')} Chance value cannot be negative.")
            return

        stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
        res = await db.execute(stmt)
        rarity_item = res.scalar_one_or_none()

        if not rarity_item:
            await message.reply(f"{get_emoji('error')} Rarity tier '<b>{escape_html(rarity_name)}</b>' not found.", parse_mode="HTML")
            return

        rarity_item.claim_weight = weight
        await db.commit()

        await message.reply(f"{get_emoji('success')} Updated daily claim chance for <b>{escape_html(rarity_item.name)}</b> to <b>{weight}</b>!", parse_mode="HTML")
        return

    stmt = select(RarityType).where(RarityType.claim_enabled == True)
    res = await db.execute(stmt)
    rarities = res.scalars().all()
    if not rarities:
        await message.reply(f"{get_emoji('warning')} No rarities are currently enabled for daily claim pool.")
        return

    builder = InlineKeyboardBuilder()
    for r in rarities:
        from utils.formatters import get_rarity_emoji
        r_emoji = get_rarity_emoji(r.name)
        builder.row(InlineKeyboardButton(
            text=f"{r_emoji} {r.name} ({r.claim_weight})",
            callback_data=f"claim_edit_sel:{r.id}"
        ))
    builder.row(InlineKeyboardButton(text=f"{get_emoji('error')} Cancel", callback_data="claim_edit_cancel"))

    text = (
        "🎲 <b>ANIVERSE CLAIM CHANCE EDITOR</b>\n\n"
        + format_blockquote(
            "Select a rarity tier below to adjust its daily claim probability chance value.\n\n"
            f"{get_emoji('warning')} Only rarities enabled for daily claims are listed here. To enable a new rarity, use <code>/addtoclaim &lt;rarity&gt;</code>."
        )
    )
    await message.reply(text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "claim_edit_cancel")
async def cb_claim_edit_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(f"{get_emoji('error')} Claim weight editing cancelled.")
    await callback.answer()

@router.callback_query(F.data.startswith("claim_edit_sel:"))
async def cb_claim_edit_sel(callback: CallbackQuery, db: AsyncSession, state: FSMContext):
    if not await is_admin_id(callback.from_user.id, db):
        await callback.answer("Unauthorized!", show_alert=True)
        return

    rarity_id = int(callback.data.split(":")[1])
    stmt = select(RarityType).where(RarityType.id == rarity_id)
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        await callback.answer(f"{get_emoji('error')} Rarity not found.", show_alert=True)
        return

    await state.set_state(EditClaimChanceStates.waiting_for_claim_weight)
    await state.update_data(edit_claim_rarity_id=rarity_id)

    from utils.formatters import get_rarity_emoji
    r_emoji = get_rarity_emoji(rarity_item.name)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"{get_emoji('error')} Cancel", callback_data="claim_edit_cancel"))

    text = (
        f"⚙️ <b>Adjusting Claim Chance:</b> {r_emoji} <b>{rarity_item.name}</b>\n\n"
        + format_blockquote(
            f"{get_emoji('user')} Administrator: {escape_html(callback.from_user.first_name)}\n"
            f"📊 Current Claim Value: <code>{rarity_item.claim_weight}</code>\n\n"
            f"{get_emoji('pointer')} Please type and send the **new chance value** (positive integer) in the chat."
        )
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@router.message(EditClaimChanceStates.waiting_for_claim_weight)
async def process_claim_edit_weight(message: Message, db: AsyncSession, state: FSMContext):
    if not await is_admin(message, db):
        await message.reply(f"{get_emoji('no_entry')} Unauthorized!")
        await state.clear()
        return

    data = await state.get_data()
    rarity_id = data.get("edit_claim_rarity_id")

    weight_str = message.text.strip()
    if not weight_str.isdigit():
        await message.reply(f"{get_emoji('error')} Invalid input! Please send a valid positive number for chance value.")
        return

    weight = int(weight_str)
    if weight < 0:
        await message.reply(f"{get_emoji('error')} Value cannot be negative.")
        return

    stmt = select(RarityType).where(RarityType.id == rarity_id)
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        await message.reply(f"{get_emoji('error')} Rarity not found. State cleared.")
        await state.clear()
        return

    old_weight = rarity_item.claim_weight
    rarity_item.claim_weight = weight
    await db.commit()
    await state.clear()

    stmt_all = select(RarityType).where(RarityType.claim_enabled == True)
    res_all = await db.execute(stmt_all)
    rarities = res_all.scalars().all()

    lines = []
    rarities.sort(key=lambda x: x.claim_weight, reverse=True)
    
    for r in rarities:
        from utils.formatters import get_rarity_emoji
        r_emoji = get_rarity_emoji(r.name)
        lines.append(f"{r_emoji} <b>{r.name}</b>: <b>{r.claim_weight}</b>")

    text = (
        f"{get_emoji('success')} <b>DAILY CLAIM CHANCE UPDATED!</b>\n\n"
        + format_blockquote(
            f"{get_emoji('gem')} <b>Rarity:</b> {escape_html(rarity_item.name)}\n"
            f"📉 Old Value: <code>{old_weight}</code>\n"
            f"📈 New Value: <code>{weight}</code>\n\n"
            f"{get_emoji('target')} <b>Current Daily Claim Chances:</b>\n"
            + "\n".join(lines)
        )
    )
    await message.reply(text, parse_mode="HTML")

# --- EDIT CHARACTER INTERACTIVE TOOL ---
DEFAULT_CHAR_PHOTO = "https://cdn.pixabay.com/photo/2022/12/01/04/35/anime-7628313_1280.jpg"

@router.message(Command("editchar", "editcharacter"))
async def cmd_editchar(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin(message, db):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners and admins can edit characters!")
        return

    if message.chat.type != "private":
        bot_info = await message.bot.get_me()
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📝 Edit in Private Chat", url=f"https://t.me/{bot_info.username}?start=editchar"))
        await message.reply(
            "⛩️ <b>EDIT ANIME CHARACTER CONSOLE</b>\n\n"
            f"{get_emoji('warning')} Character editing requires multiple interaction steps. To prevent group chat clutter, please complete this in my **Private Chat (DM)**!\n\n"
            "Click the button below to edit:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.reply(f"{get_emoji('warning')} <b>Usage:</b> <code>/editchar &lt;character_id&gt;</code>", parse_mode="HTML")
        return
    char_id_str = parts[1].strip()
    if not char_id_str.isdigit():
        await message.reply(f"{get_emoji('error')} Character ID must be a valid number.")
        return

    char_id = int(char_id_str)
    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()

    if not character:
        await message.reply(f"{get_emoji('error')} Character ID #{char_id} not found in database.")
        return

    await send_edit_char_menu(message, character, db, is_callback=False)

async def send_edit_char_menu(message_obj, character: Character, db: AsyncSession, is_callback: bool = False):
    r_emoji = get_rarity_emoji(character.rarity)
    card = (
        "⚙️ <b>EDIT CHARACTER CONSOLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        + format_blockquote(
            f"{get_emoji('id')} <b>ID:</b> #{character.id}\n"
            f"{get_emoji('user')} <b>NAME:</b> {escape_html(character.name)}\n"
            f"🎦 <b>ANIME:</b> {escape_html(character.anime)}\n"
            f"{r_emoji} <b>RARITY:</b> {r_emoji} {character.rarity}"
        )
        + "\n\nSelect which field you want to edit below:"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"{get_emoji('user')} Edit Name", callback_data=f"edit_name_{character.id}"),
        InlineKeyboardButton(text="🎦 Edit Anime", callback_data=f"edit_anime_{character.id}")
    )
    builder.row(
        InlineKeyboardButton(text=f"{get_emoji('gem')} Edit Rarity", callback_data=f"edit_rarity_{character.id}"),
        InlineKeyboardButton(text="📸 Edit Media", callback_data=f"edit_media_{character.id}")
    )
    builder.row(InlineKeyboardButton(text=f"{get_emoji('back')} Close Menu", callback_data="close_edit_menu"))
    
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
    
    await callback.message.reply(f"{get_emoji('tv')} Please type the **new anime name** for the character (or send `/cancel` to abort):")
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

    await callback.message.reply(f"{get_emoji('gem')} Please select a new rarity tier, or type one manually:", reply_markup=builder.as_markup())
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
            await message.reply(f"{get_emoji('error')} Edit cancelled.")
            return
        await message.reply(f"{get_emoji('warning')} Invalid name! Please type a new name:")
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
        clear_character_cache()
        await message.reply(f"{get_emoji('success')} Character name updated to <b>{escape_html(new_name)}</b>!", parse_mode="HTML")
        await send_edit_char_menu(message, character, db, is_callback=False)
        by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        await send_character_edit_announcement(message.bot, character, "Name", old_name, new_name, by_user)
    else:
        await message.reply(f"{get_emoji('error')} Error: Character not found.")
    await state.clear()

@router.message(EditCharStates.waiting_for_new_anime, F.text)
async def process_edit_anime(message: Message, state: FSMContext, db: AsyncSession):
    if message.text.startswith("/"):
        if message.text == "/cancel":
            await state.clear()
            await message.reply(f"{get_emoji('error')} Edit cancelled.")
            return
        await message.reply(f"{get_emoji('warning')} Invalid name! Please type a new anime:")
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
        clear_character_cache()
        await message.reply(f"{get_emoji('success')} Character anime updated to <b>{escape_html(new_anime)}</b>!", parse_mode="HTML")
        await send_edit_char_menu(message, character, db, is_callback=False)
        by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        await send_character_edit_announcement(message.bot, character, "Anime", old_anime, new_anime, by_user)
    else:
        await message.reply(f"{get_emoji('error')} Error: Character not found.")
    await state.clear()

@router.callback_query(F.data.startswith("sel_new_rarity_"))
async def process_edit_rarity_cb(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    current_state = await state.get_state()
    if current_state != EditCharStates.waiting_for_new_rarity.state:
        await callback.answer(f"{get_emoji('warning')} This edit menu is no longer active.", show_alert=True)
        return

    new_rarity = callback.data.replace("sel_new_rarity_", f"").title()
    data = await state.get_data()
    char_id = data["edit_char_id"]

    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()
    if character:
        old_rarity = character.rarity
        character.rarity = new_rarity
        await db.commit()
        clear_character_cache()
        await callback.message.reply(f"{get_emoji('success')} Character rarity updated to <b>{new_rarity}</b>!", parse_mode="HTML")
        await send_edit_char_menu(callback.message, character, db, is_callback=False)
        by_user = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.first_name
        await send_character_edit_announcement(callback.bot, character, "Rarity", old_rarity, new_rarity, by_user)
    else:
        await callback.message.reply(f"{get_emoji('error')} Error: Character not found.")
    await state.clear()
    await callback.answer()

@router.message(EditCharStates.waiting_for_new_rarity, F.text)
async def process_edit_rarity_text(message: Message, state: FSMContext, db: AsyncSession):
    if message.text.startswith("/"):
        if message.text == "/cancel":
            await state.clear()
            await message.reply(f"{get_emoji('error')} Edit cancelled.")
            return
        await message.reply(f"{get_emoji('warning')} Invalid option! Please select a rarity or type one manually:")
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
        clear_character_cache()
        await message.reply(f"{get_emoji('success')} Character rarity updated to <b>{new_rarity}</b>!", parse_mode="HTML")
        await send_edit_char_menu(message, character, db, is_callback=False)
        by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        await send_character_edit_announcement(message.bot, character, "Rarity", old_rarity, new_rarity, by_user)
    else:
        await message.reply(f"{get_emoji('error')} Error: Character not found.")
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
        await message.reply(f"{get_emoji('warning')} Please send a valid photo, video, or GIF!")
        return

    data = await state.get_data()
    char_id = data["edit_char_id"]

    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()
    if character:
        character.image_url = file_id
        await db.commit()
        clear_character_cache()
        await message.reply(f"{get_emoji('success')} Character media has been updated successfully!", parse_mode="HTML")
        await send_edit_char_menu(message, character, db, is_callback=False)
        by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        await send_character_edit_announcement(message.bot, character, "Media", "Old Media File", "New Media File", by_user)
    else:
        await message.reply(f"{get_emoji('error')} Error: Character not found.")
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
                f"{get_emoji('id')} <b>ID</b>: #{character.id:03d}\n"
                f"📛 <b>Name</b>: {escape_html(character.name)}\n"
                f"{get_emoji('tv')} <b>Anime</b>: {escape_html(character.anime)}\n"
                f"{get_emoji('gem')} <b>Rarity</b>: {r_emoji} {character.rarity}\n\n"
                f"{get_emoji('user')} <b>By</b>: {escape_html(by_user_str)}\n"
                f"⌛️ <b>Time</b>: {time_str}"
            )
        )
    else:
        announcement_text = (
            "⚙️ <b>CHARACTER DETAILS EDITED / UPDATED!</b>\n"
            + format_blockquote(
                f"{get_emoji('id')} <b>ID</b>: #{character.id:03d}\n"
                f"📛 <b>Name</b>: {escape_html(character.name)}\n"
                f"{get_emoji('tv')} <b>Anime</b>: {escape_html(character.anime)}\n"
                f"{get_emoji('gem')} <b>Rarity</b>: {r_emoji} {character.rarity}\n\n"
                f"📝 <b>Edited Field</b>: {field_name}\n"
                f"{get_emoji('error')} <b>Old Value</b>: {escape_html(old_val)}\n"
                f"{get_emoji('success')} <b>New Value</b>: {escape_html(new_val)}\n\n"
                f"{get_emoji('user')} <b>By</b>: {escape_html(by_user_str)}\n"
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
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can promote admins!")
        return

    parts = message.text.strip().split()
    target_user_id = None
    target_username = None
    target_first_name = None
    role = None

    if message.reply_to_message:
        if len(parts) < 2:
            await message.reply(f"{get_emoji('warning')} <b>Usage:</b> Reply to someone with <code>/promote &lt;snradmin or jradmin&gt;</code>", parse_mode="HTML")
            return
        role = parts[1].strip().lower()
        target_user_id = message.reply_to_message.from_user.id
        target_username = message.reply_to_message.from_user.username
        target_first_name = message.reply_to_message.from_user.first_name
    else:
        if len(parts) < 3:
            await message.reply(f"{get_emoji('warning')} <b>Usage:</b> <code>/promote &lt;@username or user_id&gt; &lt;snradmin or jradmin&gt;</code>", parse_mode="HTML")
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
                await message.reply(f"{get_emoji('error')} Trainer with username <b>{target_str}</b> not found in bot database.", parse_mode="HTML")
                return
        else:
            await message.reply(f"{get_emoji('error')} Please provide a valid `@username` or numerical `user_id`.", parse_mode="HTML")
            return

    if role not in ["snradmin", "jradmin"]:
        await message.reply(f"{get_emoji('error')} Invalid role! Choose either <code>snradmin</code> or <code>jradmin</code>.", parse_mode="HTML")
        return

    if target_user_id in config.ADMIN_IDS:
        await message.reply(f"{get_emoji('error')} This user is a bot owner! They already have full privileges.")
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
        f"{get_emoji('success')} <b>PROMOTION SUCCESSFUL!</b>\n\n"
        + format_blockquote(
            f"{get_emoji('user')} <b>Trainer:</b> <a href=\"tg://user?id={target_user_id}\">{escape_html(target_first_name)}</a>\n"
            f"{get_emoji('id')} <b>ID:</b> <code>{target_user_id}</code>\n"
            f"🛡️ <b>Assigned Role:</b> <code>{role}</code>"
        )
    )
    await message.reply(text, parse_mode="HTML")

    dm_text = (
        f"{get_emoji('party')} <b>CONGRATULATIONS! You have been promoted to {role.upper()}!</b>\n\n"
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
        await message.reply(f"{get_emoji('warning')} Promoted successfully, but could not send DM to user (they might have blocked the bot): {e}")

@router.message(Command("demote"))
async def cmd_demote(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can demote admins!")
        return

    parts = message.text.strip().split()
    target_user_id = None
    target_first_name = None

    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_first_name = message.reply_to_message.from_user.first_name
    else:
        if len(parts) < 2:
            await message.reply(f"{get_emoji('warning')} <b>Usage:</b> Reply to someone with <code>/demote</code> or type <code>/demote &lt;@username or user_id&gt;</code>", parse_mode="HTML")
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
                await message.reply(f"{get_emoji('error')} Trainer with username <b>{target_str}</b> not found.", parse_mode="HTML")
                return
        else:
            await message.reply(f"{get_emoji('error')} Please provide a valid `@username` or numerical `user_id`.", parse_mode="HTML")
            return

    stmt = delete(BotAdmin).where(BotAdmin.user_id == target_user_id)
    res = await db.execute(stmt)
    
    if res.rowcount > 0:
        await db.commit()
        if not target_first_name:
            target_first_name = f"User {target_user_id}"
        await message.reply(f"{get_emoji('success')} Successfuly demoted <a href=\"tg://user?id={target_user_id}\">{escape_html(target_first_name)}</a>! They no longer have bot admin privileges.", parse_mode="HTML")
    else:
        await message.reply(f"{get_emoji('error')} User is not an active admin in the database.")

@router.message(Command("adminlist", "admins"))
async def cmd_adminlist(message: Message, db: AsyncSession):
    stmt = select(BotAdmin)
    res = await db.execute(stmt)
    admins = list(res.scalars().all())

    db_admin_ids = {a.user_id for a in admins}
    
    # Merge default config admins if not already loaded in db query
    for def_id, def_info in config.DEFAULT_BOT_ADMINS.items():
        if def_id not in db_admin_ids:
            # Create a mock-like or temporary instance for display
            admins.append(BotAdmin(user_id=def_id, role=def_info.get("role", "snradmin")))
            db_admin_ids.add(def_id)

    admin_ids = list(db_admin_ids)
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
        def_info = config.DEFAULT_BOT_ADMINS.get(a.user_id, {})
        first_name = u.first_name if (u and u.first_name) else def_info.get("first_name", f"Admin {a.user_id}")
        uname = u.username if (u and u.username) else def_info.get("username", "")
        
        name = escape_html(first_name)
        username_text = f" (@{uname})" if uname else ""
        line = f"• {name}{username_text} (<code>{a.user_id}</code>)"
        if a.role == "snradmin":
            snr_list.append(line)
        else:
            jr_list.append(line)

    text = f"{get_emoji('crown')} <b>ANIVERSE BOT ADMINISTRATIVE STAFF</b>\n\n"
    
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
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can delete custom rarities!")
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            f"{get_emoji('warning')} <b>Usage:</b>\n"
            f"{get_emoji('pointer')} <code>/delrarity &lt;rarity_name&gt;</code>\n\n"
            "Example: <code>/delrarity Divine</code>",
            parse_mode="HTML"
        )
        return

    rarity_name = parts[1].strip()
    stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        await message.reply(f"{get_emoji('error')} Rarity tier '<b>{escape_html(rarity_name)}</b>' not found in database.", parse_mode="HTML")
        return

    actual_name = rarity_item.name
    await db.delete(rarity_item)
    await db.commit()

    RARITY_CACHE.pop(actual_name.title(), None)

    await message.reply(f"{get_emoji('success')} Custom rarity tier '<b>{escape_html(actual_name)}</b>' has been deleted successfully and cache cleared!", parse_mode="HTML")

@router.message(Command("editrarityemoji", "editrarity"))
async def cmd_editrarityemoji(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can edit custom rarity emojis!")
        return

    parts = message.text.strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.reply(
            f"{get_emoji('warning')} <b>Usage:</b>\n"
            f"{get_emoji('pointer')} <code>/editrarityemoji &lt;rarity_name&gt; &lt;new_emoji&gt;</code>\n\n"
            "Example: <code>/editrarityemoji Divine 💌</code>",
            parse_mode="HTML"
        )
        return

    rarity_name = parts[1].strip()
    new_emoji = parts[2].strip()

    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                custom_id = entity.custom_emoji_id
                # Only use it if it's part of the new_emoji text
                # We can just extract the exact text from the entity
                emoji_char = message.text[entity.offset : entity.offset + entity.length]
                if emoji_char in new_emoji:
                    new_emoji = f'<tg-emoji emoji-id="{custom_id}">{emoji_char}</tg-emoji>'
                    break

    stmt = select(RarityType).where(RarityType.name.ilike(rarity_name))
    res = await db.execute(stmt)
    rarity_item = res.scalar_one_or_none()

    if not rarity_item:
        await message.reply(f"{get_emoji('error')} Rarity tier '<b>{escape_html(rarity_name)}</b>' not found in database. Add it first using /addrarity.", parse_mode="HTML")
        return

    old_emoji = rarity_item.emoji
    rarity_item.emoji = new_emoji
    await db.commit()

    RARITY_CACHE[rarity_item.name.title()] = {"emoji": new_emoji}

    await message.reply(
        f"{get_emoji('success')} Emoji updated for <b>{escape_html(rarity_item.name)}</b> rarity!\n"
        f"• {get_emoji('pointer')} <b>Old Emoji:</b> {old_emoji}\n"
        f"• {get_emoji('pointer')} <b>New Emoji:</b> {new_emoji}",
        parse_mode="HTML"
    )

@router.message(Command("autoemojis"))
async def cmd_autoemojis(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can auto-map bot emojis!")
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            f"{get_emoji('warning')} <b>Usage:</b>\n"
            f"{get_emoji('pointer')} <code>/autoemojis &lt;Sticker_Pack_Name&gt;</code>\n\n"
            f"Example: <code>/autoemojis CoolUIEmojis</code>",
            parse_mode="HTML"
        )
        return

    pack_name = parts[1].strip()
    
    # Try parsing full link if provided
    if "addstickers/" in pack_name:
        pack_name = pack_name.split("addstickers/")[-1].split("?")[0]
    elif "addemoji/" in pack_name:
        pack_name = pack_name.split("addemoji/")[-1].split("?")[0]
    
    pack_name = pack_name.strip("/")

    try:
        pack = await message.bot.get_sticker_set(pack_name)
    except Exception as e:
        await message.reply(f"{get_emoji('error')} Failed to fetch pack. Ensure the name is correct.\nError: {e}")
        return

    if pack.sticker_type != "custom_emoji":
        await message.reply(f"{get_emoji('error')} This pack is not a custom emoji pack! Type: {pack.sticker_type}")
        return

    from utils.emojis import DEFAULT_EMOJIS, load_emojis
    from database.models import BotEmoji
    
    emoji_to_key = {v: k for k, v in DEFAULT_EMOJIS.items()}
    
    mapped_count = 0
    mapped_keys = []

    try:
        for sticker in pack.stickers:
            if sticker.emoji in emoji_to_key and sticker.custom_emoji_id:
                key = emoji_to_key[sticker.emoji]
                
                tag = f'<tg-emoji emoji-id="{sticker.custom_emoji_id}">{sticker.emoji}</tg-emoji>'
                
                stmt = select(BotEmoji).where(BotEmoji.key == key)
                res = await db.execute(stmt)
                existing = res.scalar_one_or_none()
                
                if existing:
                    existing.emoji = tag
                else:
                    db.add(BotEmoji(key=key, emoji=tag))
                
                mapped_count += 1
                mapped_keys.append(key)
                # Remove from mapping so we only map the first matching sticker in the pack
                del emoji_to_key[sticker.emoji]

        await db.commit()
        await load_emojis(db)  # Reload into cache

        if mapped_count > 0:
            keys_str = ", ".join(mapped_keys)
            await message.reply(f"{get_emoji('success')} <b>Successfully auto-mapped {mapped_count} emojis!</b>\n\nAssigned: {keys_str}", parse_mode="HTML")
        else:
            await message.reply(f"{get_emoji('warning')} Found the pack, but no standard UI emojis ({''.join(DEFAULT_EMOJIS.values())}) matched the stickers inside.")
    except Exception as e:
        await db.rollback()
        import html
        safe_error = html.escape(str(e))
        await message.reply(f"{get_emoji('error')} An unexpected database error occurred during mapping:\n\n<code>{safe_error}</code>", parse_mode="HTML")

@router.message(Command("toggleemojis", ignore_mention=True))
@router.message(Command("togglepremiumemojis", ignore_mention=True))
async def cmd_toggle_emojis(message: Message, db: AsyncSession):
    if not await is_admin_or_owner(message, db):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners and administrators can toggle premium emojis!")
        return

    from utils.emoji_patch import is_premium_emojis_enabled, set_premium_emojis_status
    current = is_premium_emojis_enabled()
    new_status = not current
    set_premium_emojis_status(new_status)

    status_str = "Enabled 🟢 (Custom Telegram Premium Emojis)" if new_status else "Disabled 🔴 (Standard Clean Unicode Emojis)"
    await message.reply(
        f"✨ <b>Premium Emoji Mode</b> is now <b>{status_str}</b>.\n\n"
        f"<i>Saved in settings! The setting will persist across all future bot restarts & updates.</i>",
        parse_mode="HTML"
    )

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, db: AsyncSession):
    if not is_owner(message):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can use the broadcast tool!")
        return

    raw_text = (message.text or "").strip()
    words = raw_text.split()
    # words[0] is "/broadcast"

    # Default target mode is 'all'
    target_mode = "all"
    msg_text = None

    if len(words) > 1 and words[1].lower() in ("groups", "group", "gc", "gcs"):
        target_mode = "groups"
        msg_text = raw_text.split(None, 2)[2] if len(words) > 2 else None
    elif len(words) > 1 and words[1].lower() in ("users", "user", "dm", "dms", "private"):
        target_mode = "users"
        msg_text = raw_text.split(None, 2)[2] if len(words) > 2 else None
    elif len(words) > 1 and words[1].lower() == "all":
        target_mode = "all"
        msg_text = raw_text.split(None, 2)[2] if len(words) > 2 else None
    else:
        # Default: everything after /broadcast is the message, broadcast to ALL
        msg_text = raw_text.split(None, 1)[1] if len(words) > 1 else None

    # If neither text nor replied message was provided, show usage guide
    if not msg_text and not message.reply_to_message:
        await message.reply(
            f"📢 <b>Universal Global Broadcast Tool</b>\n\n"
            f"Send announcements to groups, private users, or both!\n\n"
            f"<b>Usage Modes:</b>\n"
            f"• <code>/broadcast &lt;message&gt;</code> — Send to <b>ALL</b> (Groups + Users)\n"
            f"• <code>/broadcast groups &lt;message&gt;</code> — Send <b>ONLY to Group Chats</b>\n"
            f"• <code>/broadcast users &lt;message&gt;</code> — Send <b>ONLY to Private DMs</b>\n\n"
            f"📸 <b>Media / Forwarded Messages:</b>\n"
            f"Reply to any photo, video, audio, or message with:\n"
            f"<code>/broadcast</code> (to all), <code>/broadcast groups</code>, or <code>/broadcast users</code>",
            parse_mode="HTML"
        )
        return

    import asyncio
    chat_ids = set()

    # 1. Fetch group IDs if needed
    if target_mode in ("groups", "all"):
        stmt_g = select(GroupSettings.chat_id)
        res_g = await db.execute(stmt_g)
        for gid in res_g.scalars().all():
            if gid:
                chat_ids.add(gid)

    # 2. Fetch user IDs if needed (filter out group IDs if any)
    if target_mode in ("users", "all"):
        stmt_u = select(User.user_id).where(User.user_id > 0)
        res_u = await db.execute(stmt_u)
        for uid in res_u.scalars().all():
            if uid:
                chat_ids.add(uid)

    total_targets = len(chat_ids)
    if total_targets == 0:
        await message.reply(f"{get_emoji('warning')} No destination chats found for target mode: <code>{target_mode}</code>.")
        return

    mode_label = {
        "all": "Groups & Users",
        "groups": "Group Chats only",
        "users": "Private Users only"
    }.get(target_mode, target_mode)

    status_msg = await message.reply(
        f"⏳ <b>Starting Broadcast...</b>\n\n"
        f"🎯 <b>Target:</b> {mode_label}\n"
        f"📬 <b>Total Chats:</b> {total_targets:,}\n"
        f"<i>Please wait, broadcasting safely with rate-limit protection...</i>",
        parse_mode="HTML"
    )

    success_count = 0
    fail_count = 0

    for cid in chat_ids:
        try:
            if message.reply_to_message:
                await message.reply_to_message.copy_to(cid)
            else:
                await message.bot.send_message(cid, msg_text, parse_mode="HTML")
            success_count += 1
        except Exception:
            fail_count += 1

        # Safe rate limit: 20 msgs/second avoids Telegram bans
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ <b>Broadcast Completed!</b>\n\n"
        f"🎯 <b>Target Mode:</b> {mode_label}\n"
        f"📣 <b>Delivered:</b> {success_count:,} chats\n"
        f"❌ <b>Failed / Blocked:</b> {fail_count:,} chats",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────
#  /getemoji  – Check key name and custom ID of any emoji
#  /mapemoji  – Direct update or key map of custom emoji
#  /setemojiid – Direct manual numeric ID mapper
#  /emojiaudit – Complete emoji audit in Telegram
#  /listmapped & /delmapped – Manage DB custom mappings
# ─────────────────────────────────────────────────────────────

LIVE_BOT_EMOJIS = {
    "party": "🎉", "info": "ℹ️", "id": "🆔", "circle": "⭕",
    "bag": "🎒", "star2": "🌟", "common": "⚪", "galaxy": "🌌",
    "name_badge": "📛", "video_frame": "🎦", "bird": "🐦",
    "number": "🔢", "bat": "🦇", "xo_empty": "⬜", "leaf": "🍃",
    "bubbles": "🫧", "card_game": "🎴", "outbox": "📤",
    "inbox": "📥", "mailbox": "📬", "video_cam": "📹",
    "repeat": "🔁", "abc": "🔤", "crystal": "🔮",
    "black_square": "🔳", "clock": "🕒", "bow": "🙇",
    "planet": "🪐", "stop_btn": "⏹️", "sort": "⇅",
}

@router.message(Command("getemoji", "emojiname", ignore_mention=True))
async def cmd_get_emoji_info(message: Message, db: AsyncSession):
    """Send an emoji (standard or custom) to check its registered key and active ID."""
    if not await is_admin_or_owner(message, db):
        await message.reply(f"{get_emoji('no_entry')} Only bot admins can check emoji keys!")
        return

    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            f"{get_emoji('info')} <b>Usage:</b>\n"
            f"Send <code>/getemoji &lt;emoji&gt;</code> to check its key name!\n\n"
            f"<i>Example:</i> <code>/getemoji 🪙</code> or <code>/getemoji 📛</code>",
            parse_mode="HTML"
        )
        return

    target_text = parts[1].strip()
    from utils.emojis import DEFAULT_EMOJIS, PREMIUM_EMOJI_IDS, EMOJI_CACHE
    from utils.emoji_patch import EMOJI_MAPPING

    custom_id = None
    custom_char = None
    if message.entities:
        for ent in message.entities:
            if ent.type == "custom_emoji" and ent.custom_emoji_id:
                custom_id = ent.custom_emoji_id
                custom_char = message.text[ent.offset:ent.offset + ent.length]
                break

    clean_target = target_text.replace('️', '')
    matched_keys = []
    for k, v in DEFAULT_EMOJIS.items():
        if v == target_text or v.replace('️', '') == clean_target:
            matched_keys.append(k)

    for k, v in LIVE_BOT_EMOJIS.items():
        if (v == target_text or v.replace('️', '') == clean_target) and k not in matched_keys:
            matched_keys.append(k)

    active_id = custom_id or PREMIUM_EMOJI_IDS.get(target_text) or PREMIUM_EMOJI_IDS.get(clean_target) or EMOJI_MAPPING.get(target_text) or EMOJI_MAPPING.get(clean_target)

    if matched_keys:
        primary_key = matched_keys[0]
        keys_str = ", ".join(f"<code>{k}</code>" for k in matched_keys)
        await message.reply(
            f"{get_emoji('search')} <b>Emoji Detected!</b>\n\n"
            f"• <b>Symbol:</b> {target_text}\n"
            f"• <b>Key Name:</b> {keys_str}\n"
            f"• <b>Current Custom ID:</b> <code>{active_id or 'None (Standard Unicode)'}</code>\n\n"
            f"💡 <b>To update this emoji directly:</b>\n"
            f"Send: <code>/mapemoji [your_new_custom_emoji]</code> (auto-detects!)\n"
            f"Or: <code>/mapemoji {primary_key} [your_new_custom_emoji]</code>",
            parse_mode="HTML"
        )
    else:
        await message.reply(
            f"{get_emoji('warning')} <b>Unregistered Symbol</b>\n\n"
            f"Symbol: {target_text}\n"
            f"Custom ID: <code>{custom_id or 'None'}</code>\n\n"
            f"To bind this symbol to a new key: <code>/mapemoji &lt;new_key&gt; {target_text}</code>",
            parse_mode="HTML"
        )

@router.message(Command("mapemoji", ignore_mention=True))
async def cmd_mapemoji(message: Message, db: AsyncSession):
    """Directly map or update a custom emoji.
    
    Usage:
      1. /mapemoji <custom_emoji> (Auto-detects matching key!)
      2. /mapemoji <key> <custom_emoji> (Explicit key)
    """
    if not await is_admin_or_owner(message, db):
        await message.reply(f"{get_emoji('no_entry')} Only bot admins can map custom emojis!")
        return

    parts = (message.text or "").strip().split(maxsplit=2)

    if len(parts) < 2:
        from utils.emoji_patch import EMOJI_MAPPING
        from utils.emojis import PREMIUM_EMOJI_IDS, DEFAULT_EMOJIS

        all_premium_chars = set(EMOJI_MAPPING.keys()) | set(PREMIUM_EMOJI_IDS.keys())
        all_premium_chars |= {k.replace('️', '') for k in all_premium_chars}

        missing_lines = []
        for k, v in sorted(LIVE_BOT_EMOJIS.items()):
            clean = v.replace('️', '')
            if v not in all_premium_chars and clean not in all_premium_chars:
                missing_lines.append(f"  {v}  <code>{k}</code>")

        for k, v in DEFAULT_EMOJIS.items():
            clean = v.replace('️', '')
            if v not in all_premium_chars and clean not in all_premium_chars:
                line = f"  {v}  <code>{k}</code>"
                if line not in missing_lines:
                    missing_lines.append(line)

        missing_text = "\n".join(missing_lines[:30]) if missing_lines else "  <i>All mapped! 🎉</i>"

        await message.reply(
            f"{get_emoji('sparkle')} <b>Map Custom Emoji (Instant!)</b>\n\n"
            f"<b>Two simple ways to update:</b>\n"
            f"1️⃣ <b>Direct update (Auto-detects!):</b>\n"
            f"   Send <code>/mapemoji [custom_emoji]</code>\n"
            f"   <i>Example:</i> <code>/mapemoji 🪙</code> (with your custom coin!)\n\n"
            f"2️⃣ <b>Specify key name:</b>\n"
            f"   Send <code>/mapemoji &lt;key&gt; [custom_emoji]</code>\n"
            f"   <i>Example:</i> <code>/mapemoji name_badge 📛</code>\n\n"
            f"🔍 <i>Don't know an emoji's key? Check it with <code>/getemoji &lt;emoji&gt;</code>!</i>\n\n"
            f"{get_emoji('warning')} <b>Currently Missing ({len(missing_lines)}):</b>\n"
            f"{missing_text}",
            parse_mode="HTML"
        )
        return

    from utils.emojis import DEFAULT_EMOJIS, EMOJI_CACHE, PREMIUM_EMOJI_IDS
    from utils.emoji_patch import EMOJI_MAPPING, ALL_EMOJIS_SET
    from database.models import BotEmoji

    custom_emoji_id = None
    emoji_char = None

    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji" and entity.custom_emoji_id:
                emoji_char = message.text[entity.offset:entity.offset + entity.length]
                custom_emoji_id = entity.custom_emoji_id
                break

    if len(parts) >= 3:
        key = parts[1].strip().lower()
    else:
        raw_target = parts[1].strip()
        candidate = emoji_char or raw_target
        clean_c = candidate.replace('️', '')
        
        detected_key = None
        for k, v in DEFAULT_EMOJIS.items():
            if v == candidate or v.replace('️', '') == clean_c:
                detected_key = k
                break
        if not detected_key:
            for k, v in LIVE_BOT_EMOJIS.items():
                if v == candidate or v.replace('️', '') == clean_c:
                    detected_key = k
                    break
        key = detected_key or clean_c

    if not custom_emoji_id:
        if len(parts) >= 3:
            emoji_char = parts[2].strip()
        else:
            emoji_char = parts[1].strip()
        await message.reply(
            f"{get_emoji('warning')} <b>No custom emoji detected!</b>\n\n"
            f"You sent <code>{emoji_char}</code> as a regular Unicode emoji.\n"
            f"Pick the animated/custom version from your Telegram emoji picker!\n\n"
            f"<i>Or if you have the ID number, use:</i>\n"
            f"<code>/setemojiid {key} &lt;id_number&gt; {emoji_char}</code>",
            parse_mode="HTML"
        )
        return

    tag = f'<tg-emoji emoji-id="{custom_emoji_id}">{emoji_char}</tg-emoji>'

    try:
        stmt = select(BotEmoji).where(BotEmoji.key == key)
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()

        old_tag = None
        if existing:
            old_tag = existing.emoji
            existing.emoji = tag
        else:
            db.add(BotEmoji(key=key, emoji=tag))

        await db.commit()

        from utils.emoji_patch import rebuild_emoji_regex
        EMOJI_CACHE[key] = tag
        if emoji_char:
            EMOJI_CACHE[emoji_char] = tag
            EMOJI_CACHE[emoji_char.replace('️', '')] = tag
            EMOJI_MAPPING[emoji_char] = custom_emoji_id
            EMOJI_MAPPING[emoji_char.replace('️', '')] = custom_emoji_id
            ALL_EMOJIS_SET.add(emoji_char)
            ALL_EMOJIS_SET.add(emoji_char.replace('️', ''))

        PREMIUM_EMOJI_IDS[key] = custom_emoji_id
        if emoji_char:
            PREMIUM_EMOJI_IDS[emoji_char] = custom_emoji_id
            
        rebuild_emoji_regex()

        action = "Updated" if old_tag else "Added"
        await message.reply(
            f"{get_emoji('success')} <b>Custom Emoji {action}!</b>\n\n"
            f"🔑 <b>Key:</b> <code>{key}</code>\n"
            f"✨ <b>Emoji:</b> {tag}\n"
            f"🆔 <b>ID:</b> <code>{custom_emoji_id}</code>\n"
            f"{'🔄 <b>Old:</b> ' + old_tag + chr(10) if old_tag else ''}"
            f"\n<i>Live — active immediately across all bot commands!</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        import html
        await message.reply(f"{get_emoji('error')} Error saving emoji: <code>{html.escape(str(e))}</code>", parse_mode="HTML")

@router.message(Command("setemojiid", ignore_mention=True))
async def cmd_setemojiid(message: Message, db: AsyncSession):
    """Manually map a premium emoji by providing its numeric ID."""
    if not await is_admin_or_owner(message, db):
        await message.reply(f"{get_emoji('no_entry')} Only bot admins can map custom emojis!")
        return

    parts = (message.text or "").strip().split(maxsplit=3)
    if len(parts) < 4:
        await message.reply(
            f"{get_emoji('info')} <b>Usage:</b>\n"
            f"<code>/setemojiid &lt;key&gt; &lt;emoji_id&gt; &lt;fallback_emoji&gt;</code>\n\n"
            f"<b>Example:</b>\n"
            f"<code>/setemojiid party 5368324170671202286 🎉</code>",
            parse_mode="HTML"
        )
        return

    key = parts[1].strip().lower()
    emoji_id_str = parts[2].strip()
    fallback = parts[3].strip()

    if not emoji_id_str.isdigit():
        await message.reply(f"{get_emoji('error')} Emoji ID must be a number! Got: <code>{emoji_id_str}</code>", parse_mode="HTML")
        return

    emoji_id = emoji_id_str
    tag = f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

    from database.models import BotEmoji
    from utils.emojis import EMOJI_CACHE, PREMIUM_EMOJI_IDS
    from utils.emoji_patch import EMOJI_MAPPING, ALL_EMOJIS_SET

    try:
        stmt = select(BotEmoji).where(BotEmoji.key == key)
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()

        old_tag = None
        if existing:
            old_tag = existing.emoji
            existing.emoji = tag
        else:
            db.add(BotEmoji(key=key, emoji=tag))

        await db.commit()

        EMOJI_CACHE[key] = tag
        EMOJI_CACHE[fallback] = tag
        EMOJI_CACHE[fallback.replace('️', '')] = tag
        EMOJI_MAPPING[fallback] = emoji_id
        EMOJI_MAPPING[fallback.replace('️', '')] = emoji_id
        ALL_EMOJIS_SET.add(fallback)
        ALL_EMOJIS_SET.add(fallback.replace('️', ''))
        PREMIUM_EMOJI_IDS[key] = emoji_id
        PREMIUM_EMOJI_IDS[fallback] = emoji_id

        action = "Updated" if old_tag else "Added"
        await message.reply(
            f"{get_emoji('success')} <b>Premium Emoji {action}!</b>\n\n"
            f"🔑 <b>Key:</b> <code>{key}</code>\n"
            f"✨ <b>Preview:</b> {tag}\n"
            f"🆔 <b>ID:</b> <code>{emoji_id}</code>\n"
            f"{'🔄 <b>Old:</b> ' + old_tag + chr(10) if old_tag else ''}"
            f"\n<i>Live — active immediately!</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        import html
        await message.reply(f"{get_emoji('error')} Failed: <code>{html.escape(str(e))}</code>", parse_mode="HTML")

@router.message(Command("emojiaudit", ignore_mention=True))
async def cmd_emojiaudit(message: Message, db: AsyncSession):
    """Show full premium emoji coverage report in Telegram."""
    if not await is_admin_or_owner(message, db):
        await message.reply(f"{get_emoji('no_entry')} Only bot admins can view the emoji audit!")
        return

    from utils.emoji_patch import EMOJI_MAPPING
    from utils.emojis import PREMIUM_EMOJI_IDS, DEFAULT_EMOJIS

    all_premium_chars = set(EMOJI_MAPPING.keys()) | set(PREMIUM_EMOJI_IDS.keys())
    all_premium_chars |= {k.replace('️', '') for k in all_premium_chars}

    missing = []
    covered = []

    for k, v in DEFAULT_EMOJIS.items():
        clean = v.replace('️', '')
        if v in all_premium_chars or clean in all_premium_chars or k in PREMIUM_EMOJI_IDS:
            covered.append((k, v))
        else:
            missing.append((k, v))

    extra_hardcoded = {
        "🎒": "bag", "🌟": "star2", "🌌": "galaxy",
        "📛": "name_badge", "🎦": "video_frame", "🐦": "bird",
        "🔢": "number", "🦇": "bat", "🎴": "card_game",
        "📤": "outbox", "📥": "inbox", "📬": "mailbox", "📹": "video_cam",
        "🔁": "repeat", "🔤": "abc", "🔮": "crystal",
        "🔳": "black_square", "🕒": "clock", "🙇": "bow", "🪐": "planet",
        "🍃": "leaf", "🫧": "bubbles", "⬜": "xo_empty",
    }

    extra_missing = []
    extra_covered = []
    for em, desc in sorted(extra_hardcoded.items()):
        clean = em.replace('️', '')
        if em in all_premium_chars or clean in all_premium_chars:
            extra_covered.append((em, desc))
        else:
            extra_missing.append((em, desc))

    total_missing = len(missing) + len(extra_missing)
    total_covered = len(covered) + len(extra_covered)

    lines = [
        f"{get_emoji('stats')} <b>Premium Emoji Audit</b>\n",
        f"✅ <b>Covered:</b> {total_covered}   ❌ <b>Missing:</b> {total_missing}\n",
        f"\n<b>❌ Missing Premium IDs:</b>",
    ]

    for k, v in missing:
        lines.append(f"  {v} <code>{k}</code>  → /mapemoji {k} [custom_emoji]")
    for em, desc in extra_missing:
        lines.append(f"  {em} <code>{desc}</code>  → /mapemoji {desc} [custom_emoji]")

    lines.append(f"\n<b>✅ Already Mapped ({total_covered}):</b>")
    for k, v in covered[:15]:
        lines.append(f"  {v} ✓")
    if len(covered) > 15:
        lines.append(f"  <i>...and {len(covered)-15} more</i>")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "\n<i>...truncated</i>"

    await message.reply(text, parse_mode="HTML")

@router.message(Command("listmapped", ignore_mention=True))
async def cmd_listmapped(message: Message, db: AsyncSession):
    """List all custom emoji mappings saved in the database."""
    if not await is_admin_or_owner(message, db):
        await message.reply(f"{get_emoji('no_entry')} Only bot admins can view emoji mappings!")
        return

    from database.models import BotEmoji
    stmt = select(BotEmoji)
    res = await db.execute(stmt)
    emojis = res.scalars().all()

    if not emojis:
        await message.reply(
            f"{get_emoji('warning')} No custom emoji mappings saved in database yet.\n\n"
            f"Use <code>/mapemoji</code> or <code>/setemojiid</code> to add some!",
            parse_mode="HTML"
        )
        return

    lines = [f"{get_emoji('sparkle')} <b>Saved Custom Emoji Mappings ({len(emojis)})</b>\n"]
    for em in sorted(emojis, key=lambda x: x.key):
        lines.append(f"  <code>{em.key}</code> → {em.emoji}")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "\n<i>...truncated</i>"

    await message.reply(text, parse_mode="HTML")

@router.message(Command("delmapped", ignore_mention=True))
async def cmd_delmapped(message: Message, db: AsyncSession):
    """Delete a custom emoji mapping from the database."""
    if not is_owner(message):
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can delete emoji mappings!")
        return

    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(f"{get_emoji('warning')} <b>Usage:</b> <code>/delmapped &lt;key&gt;</code>", parse_mode="HTML")
        return

    key = parts[1].strip().lower()
    from database.models import BotEmoji
    from utils.emojis import EMOJI_CACHE

    stmt = select(BotEmoji).where(BotEmoji.key == key)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if not existing:
        await message.reply(f"{get_emoji('error')} No mapping found for key <code>{key}</code>.", parse_mode="HTML")
        return

    old_tag = existing.emoji
    await db.delete(existing)
    await db.commit()
    EMOJI_CACHE.pop(key, None)

    await message.reply(
        f"{get_emoji('success')} Mapping deleted!\n\n"
        f"🔑 <b>Key:</b> <code>{key}</code>\n"
        f"🗑️ <b>Removed:</b> {old_tag}",
        parse_mode="HTML"
    )
