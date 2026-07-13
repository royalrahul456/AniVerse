import random
import time
import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
import config
from database.models import User, Character, UserCharacter, ActiveSpawn, GroupSettings, RarityType
from utils.formatters import format_blockquote, get_rarity_emoji, escape_html
from handlers.start import get_or_create_user

router = Router()

character_cache = {}
group_settings_cache = {}

async def get_cached_characters(db: AsyncSession):
    global character_cache
    if not character_cache:
        stmt = select(Character)
        res = await db.execute(stmt)
        chars = res.scalars().all()
        character_cache = {c.id: c for c in chars}
    return list(character_cache.values())

async def get_enabled_spawn_rarities(db: AsyncSession) -> set:
    default_rarities = {"common", "rare", "epic", "legendary", "mythical"}
    stmt = select(RarityType).where(RarityType.spawn_enabled == True)
    res = await db.execute(stmt)
    custom_enabled = {r.name.lower() for r in res.scalars().all()}
    return default_rarities.union(custom_enabled)

async def spawn_character(chat_id: int, db: AsyncSession, bot, custom_rarity: str = None) -> bool:
    characters = await get_cached_characters(db)
    if not characters:
        return False

    if custom_rarity:
        filtered = [c for c in characters if c.rarity.lower() == custom_rarity.lower()]
        if not filtered:
            return False
        character = random.choice(filtered)
    else:
        allowed_rarities = await get_enabled_spawn_rarities(db)
        eligible_chars = [c for c in characters if c.rarity.lower() in allowed_rarities]
        if not eligible_chars:
            return False
        character = random.choice(eligible_chars)

    await db.execute(delete(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id))
    
    active_spawn = ActiveSpawn(chat_id=chat_id, character_id=character.id)
    db.add(active_spawn)
    await db.commit()

    r_emoji = get_rarity_emoji(character.rarity)
    caption = (
        f"╭───「 ⛩️ Character Spawn 」───╮\n"
        f"│\n"
        f"│  ✨ A wild character has appeared!\n"
        f"│\n"
        f"│  📺 <b>Anime:</b> {escape_html(character.anime)}\n"
        f"│  {r_emoji} <b>Rarity:</b> {r_emoji} {character.rarity}\n"
        f"│\n"
        f"│  🎯 Use <code>/guess &lt;name&gt;</code> to collect!\n"
        f"│\n"
        f"╰───────────────────────────╯"
    )
    
    msg = None
    try:
        if character.image_url:
            try:
                msg = await bot.send_photo(chat_id, character.image_url, caption=caption, parse_mode="HTML")
            except Exception:
                try:
                    msg = await bot.send_video(chat_id, character.image_url, caption=caption, parse_mode="HTML")
                except Exception:
                    try:
                        msg = await bot.send_animation(chat_id, character.image_url, caption=caption, parse_mode="HTML")
                    except Exception:
                        msg = await bot.send_message(chat_id, caption, parse_mode="HTML")
        else:
            msg = await bot.send_message(chat_id, caption, parse_mode="HTML")
        
        if msg:
            active_spawn.message_id = msg.message_id
            await db.commit()
    except Exception:
        pass
    return True

def is_not_command(message: Message) -> bool:
    return message.text is not None and not message.text.startswith("/")

@router.message(F.chat.type.in_({"group", "supergroup"}), is_not_command)
async def group_message_monitor(message: Message, db: AsyncSession, bot):
    if not message.text:
        return
    
    chat_id = message.chat.id
    if chat_id not in group_settings_cache:
        stmt = select(GroupSettings).where(GroupSettings.chat_id == chat_id)
        res = await db.execute(stmt)
        settings = res.scalar_one_or_none()
        if not settings:
            settings = GroupSettings(chat_id=chat_id, spawn_threshold=10, message_counter=0)
            db.add(settings)
            await db.commit()
        group_settings_cache[chat_id] = {
            "threshold": settings.spawn_threshold,
            "counter": settings.message_counter,
            "enabled": settings.spawns_enabled
        }
    
    cache = group_settings_cache[chat_id]
    if not cache["enabled"]:
        return

    cache["counter"] += 1
    if cache["counter"] >= cache["threshold"]:
        cache["counter"] = 0
        stmt = select(GroupSettings).where(GroupSettings.chat_id == chat_id)
        res = await db.execute(stmt)
        settings = res.scalar_one_or_none()
        if settings:
            settings.message_counter = 0
            await db.commit()
        await spawn_character(chat_id, db, bot)

@router.message(Command("guess", "catch", "snatch"))
async def cmd_catch(message: Message, db: AsyncSession, bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    nickname = escape_html(message.from_user.first_name if message.from_user else "Trainer")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⚠️ <b>Format:</b> <code>/snatch &lt;character_name&gt;</code>", parse_mode="HTML")
        return

    guess = parts[1].strip().lower()

    spawn_stmt = select(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id)
    spawn_res = await db.execute(spawn_stmt)
    spawn = spawn_res.scalar_one_or_none()

    if not spawn:
        if message.chat.type == "private":
            await message.reply("⚠️ Wild characters only spawn in group chats during active conversations.", parse_mode="HTML")
        else:
            await message.reply("⚠️ There are no active wild characters here! Keep chatting to spawn one.")
        return

    char_stmt = select(Character).where(Character.id == spawn.character_id)
    char_res = await db.execute(char_stmt)
    character = char_res.scalar_one()

    actual_name = character.name.lower()
    if guess != actual_name and guess not in actual_name:
        await message.reply("❌ That is not the correct character name! Try again.")
        return

    user = await get_or_create_user(db, user_id, message.from_user.username if message.from_user else "", message.from_user.first_name if message.from_user else "")
    
    coins_won = random.randint(config.CATCH_REWARD_MIN, config.CATCH_REWARD_MAX)
    user.coins += coins_won
    user.total_catches += 1

    user_char = UserCharacter(user_id=user_id, character_id=character.id, nickname=character.name)
    db.add(user_char)

    spawn_time = spawn.spawned_at
    seconds_taken = int((time.time() - spawn_time.timestamp())) if spawn_time else 5

    await db.delete(spawn)
    await db.commit()

    await message.reply(f"🎉 <b>+{coins_won} coins!</b> Balance: <code>{user.coins:,}</code>", parse_mode="HTML")

    r_emoji = get_rarity_emoji(character.rarity)
    card_text = (
        f"💥 🌟 <b>{nickname}</b> collected <b>{escape_html(character.name)}</b>!\n\n"
        + format_blockquote(
            f"⛔ <b>NAME:</b> {escape_html(character.name)}\n"
            f"🎦 <b>ANIME:</b> {escape_html(character.anime)}\n"
            f"{r_emoji} <b>RARITY:</b> {r_emoji} {character.rarity}\n"
            f"⏱️ <b>TIME:</b> {seconds_taken}s"
        )
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📖 View Harem", callback_data="dm_bag_1"))
    await message.reply(card_text, parse_mode="HTML", reply_markup=builder.as_markup())

async def is_user_allowed(message: Message, bot) -> bool:
    if message.from_user.id in config.ADMIN_IDS:
        return True
    if message.chat.type == "private":
        return True
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

@router.message(Command("spawnsettings"))
async def cmd_spawnsettings(message: Message, db: AsyncSession, bot):
    if message.chat.type == "private":
        await message.reply("⚠️ This command can only be used in group chats.")
        return

    if not await is_user_allowed(message, bot):
        await message.reply("⚠️ Only group administrators or the bot owner can view spawn settings.")
        return

    chat_id = message.chat.id
    stmt = select(GroupSettings).where(GroupSettings.chat_id == chat_id)
    res = await db.execute(stmt)
    settings = res.scalar_one_or_none()

    if not settings:
        settings = GroupSettings(chat_id=chat_id, spawn_threshold=10, message_counter=0, spawns_enabled=True)
        db.add(settings)
        await db.commit()

    status_emoji = "✅ Enabled" if settings.spawns_enabled else "❌ Disabled"
    text = (
        f"⚙️ <b>Group Spawn Settings</b>\n\n"
        f"● <b>Spawns:</b> {status_emoji}\n"
        f"● <b>Threshold:</b> {settings.spawn_threshold} messages\n"
        f"● <b>Progress:</b> {settings.message_counter}/{settings.spawn_threshold} messages"
    )
    await message.reply(text, parse_mode="HTML")

@router.message(Command("setspawn"))
async def cmd_setspawn(message: Message, db: AsyncSession, bot):
    if message.chat.type == "private":
        await message.reply("⚠️ This command can only be used in group chats.")
        return

    if not await is_user_allowed(message, bot):
        await message.reply("⚠️ Only group administrators or the bot owner can change spawn settings.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            "⚠️ <b>Format:</b>\n"
            "• <code>/setspawn on</code> / <code>/setspawn off</code>\n"
            "• <code>/setspawn &lt;threshold_number&gt;</code> (e.g. <code>/setspawn 15</code>)",
            parse_mode="HTML"
        )
        return

    arg = parts[1].strip().lower()
    chat_id = message.chat.id

    stmt = select(GroupSettings).where(GroupSettings.chat_id == chat_id)
    res = await db.execute(stmt)
    settings = res.scalar_one_or_none()

    if not settings:
        settings = GroupSettings(chat_id=chat_id, spawn_threshold=10, message_counter=0, spawns_enabled=True)
        db.add(settings)

    if arg in ["on", "enable", "true"]:
        settings.spawns_enabled = True
        await db.commit()
        await message.reply("✅ Wild character spawns have been <b>enabled</b> for this group chat.", parse_mode="HTML")
    elif arg in ["off", "disable", "false"]:
        settings.spawns_enabled = False
        await db.commit()
        await message.reply("❌ Wild character spawns have been <b>disabled</b> for this group chat.", parse_mode="HTML")
    elif arg.isdigit():
        val = int(arg)
        if val < 5:
            await message.reply("⚠️ Minimum spawn threshold is 5 messages.")
            return
        settings.spawn_threshold = val
        await db.commit()
        await message.reply(f"⚙️ Spawn message threshold has been set to <b>{val}</b> messages.", parse_mode="HTML")
    else:
        await message.reply("⚠️ Invalid argument. Use <code>on</code>, <code>off</code>, or a number.", parse_mode="HTML")
