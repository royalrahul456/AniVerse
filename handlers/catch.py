import random
import time
import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import User, Character, UserCharacter, GroupSettings, RarityType, BotAdmin
from utils.formatters import format_blockquote, get_rarity_emoji, escape_html
from handlers.start import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)

character_cache = {}
active_games = {} # chat_id -> dict with game details

# Helper to check commands manually so suffix matches like /togglenameguess@AniVerse1bot always work
def is_command_match(text: str, command_names: list) -> bool:
    if not text or not text.startswith("/"):
        return False
    first_word = text.split()[0].lower()
    cmd = first_word.split("@")[0][1:]
    return cmd in command_names

async def get_cached_characters(db: AsyncSession):
    global character_cache
    if not character_cache:
        stmt = select(Character)
        res = await db.execute(stmt)
        chars = res.scalars().all()
        character_cache = {c.id: c for c in chars}
    return list(character_cache.values())

async def is_admin_or_owner(event, db: AsyncSession) -> bool:
    user_id = event.from_user.id
    # Owner check
    if config.ADMIN_IDS and user_id in config.ADMIN_IDS:
        return True
    # DB Admin check
    stmt = select(BotAdmin).where(BotAdmin.user_id == user_id)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        return True
    # Telegram admin check
    try:
        member = await event.bot.get_chat_member(event.chat.id, user_id)
        if member.status in ("creator", "administrator"):
            return True
    except Exception:
        pass
    return False

def generate_vowel_hint(name: str) -> str:
    from utils.formatters import get_clean_name
    clean = get_clean_name(name)
    hint_chars = []
    for char in clean:
        if char.lower() in "aeiou":
            hint_chars.append("_")
        else:
            hint_chars.append(char)
    return " ".join(hint_chars)

async def cleanup_game_messages(chat_id: int, bot_obj, game_state: dict):
    # Delete main game card image message
    msg_id = game_state.get("msg_id")
    if msg_id:
        try:
            await bot_obj.delete_message(chat_id, msg_id)
        except Exception as e:
            logger.debug(f"Failed to delete game card message: {e}")

    # Delete all hint messages
    for hint_id in game_state.get("hint_msg_ids", []):
        try:
            await bot_obj.delete_message(chat_id, hint_id)
        except Exception as e:
            logger.debug(f"Failed to delete hint message: {e}")

async def start_nameguess_game(chat_id: int, db: AsyncSession, bot, is_auto: bool = False, reward: int = 150):
    if is_auto:
        reward = random.randint(100, 200)

    characters = await get_cached_characters(db)
    if not characters:
        return

    # Filter to active spawn rarities
    stmt = select(RarityType).where(RarityType.spawn_enabled == True)
    res = await db.execute(stmt)
    rarities = res.scalars().all()
    if not rarities:
        selected_rarity = "Common"
    else:
        choices = [r.name for r in rarities]
        weights = [r.weight for r in rarities]
        selected_rarity = random.choices(choices, weights=weights, k=1)[0]

    filtered = [c for c in characters if c.rarity.lower() == selected_rarity.lower()]
    if not filtered:
        filtered = characters

    character = random.choice(filtered)

    # Inline Keyboard
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Hint", callback_data=f"ng_hint:{chat_id}"),
        InlineKeyboardButton(text="🚫 Stop Game", callback_data=f"ng_stop:{chat_id}")
    )

    caption = (
        "🧠 <b>Guess The Character!</b>\n"
        "───────────────\n"
        "💭 Think you know this character?\n"
        "⌛ You have 60 seconds!\n"
        f"💰 Reward: <b>{reward}</b> coins"
    )

    msg = None
    try:
        if character.image_url:
            try:
                msg = await bot.send_photo(chat_id, character.image_url, caption=caption, parse_mode="HTML", reply_markup=builder.as_markup())
            except Exception:
                try:
                    msg = await bot.send_video(chat_id, character.image_url, caption=caption, parse_mode="HTML", reply_markup=builder.as_markup())
                except Exception:
                    try:
                        msg = await bot.send_animation(chat_id, character.image_url, caption=caption, parse_mode="HTML", reply_markup=builder.as_markup())
                    except Exception:
                        msg = await bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=builder.as_markup())
        else:
            msg = await bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Failed to spawn nameguess character: {e}")
        return

    # Timeout timer task
    async def game_timeout_timer(timeout_chat_id, char_name, bot_obj):
        await asyncio.sleep(60)
        if timeout_chat_id in active_games:
            game = active_games.pop(timeout_chat_id, None)
            
            # Clean up old game images/hints
            await cleanup_game_messages(timeout_chat_id, bot_obj, game)

            timeout_text = (
                "⏳ <b>Time is up!</b> No one guessed the character in time.\n"
                f"💡 Correct Answer: <b>{escape_html(char_name)}</b>"
            )
            try:
                await bot_obj.send_message(timeout_chat_id, timeout_text, parse_mode="HTML")
            except Exception:
                pass
            
            # Start next auto game if enabled
            if is_auto:
                await asyncio.sleep(2)
                from database.database import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    settings_stmt = select(GroupSettings).where(GroupSettings.chat_id == timeout_chat_id)
                    settings_res = await session.execute(settings_stmt)
                    settings = settings_res.scalar_one_or_none()
                    if settings and settings.auto_nameguess_enabled:
                        await start_nameguess_game(timeout_chat_id, session, bot_obj, is_auto=True)

    timer_task = asyncio.create_task(game_timeout_timer(chat_id, character.name, bot))

    active_games[chat_id] = {
        "character_id": character.id,
        "character_name": character.name,
        "reward": reward,
        "hint_requested": False,
        "is_auto": is_auto,
        "timer_task": timer_task,
        "msg_id": msg.message_id if msg else None,
        "hint_msg_ids": []
    }

# ----------------------------------------------------
# COMMAND HANDLERS
# ----------------------------------------------------

@router.message(lambda msg: is_command_match(msg.text, ["nameguess", "guess"]))
async def cmd_nameguess(message: Message, db: AsyncSession, bot):
    chat_id = message.chat.id
    
    # Restrict to official group
    is_official = False
    if chat_id == config.OFFICIAL_CHAT_ID:
        is_official = True
    elif message.chat.username and message.chat.username.lower() == "pokeempireunion":
        is_official = True

    if not is_official:
        await message.reply("❌ The Nameguess game is restricted to the <b>Official Group Chat</b> only!", parse_mode="HTML")
        return

    if chat_id in active_games:
        await message.reply("⚠️ There is already an active Nameguess game in this chat! Solve that one first.")
        return

    await start_nameguess_game(chat_id, db, bot, is_auto=False, reward=150)

@router.message(lambda msg: is_command_match(msg.text, ["togglenameguess"]))
async def cmd_togglenameguess(message: Message, db: AsyncSession, bot):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("⚠️ This command can only be used inside group chats.")
        return

    if not await is_admin_or_owner(message, db):
        await message.reply("❌ Only group administrators or bot owners can toggle this setting.")
        return

    chat_id = message.chat.id
    stmt = select(GroupSettings).where(GroupSettings.chat_id == chat_id)
    res = await db.execute(stmt)
    settings = res.scalar_one_or_none()

    if not settings:
        settings = GroupSettings(chat_id=chat_id, spawns_enabled=True, auto_nameguess_enabled=False)
        db.add(settings)

    settings.auto_nameguess_enabled = not settings.auto_nameguess_enabled
    await db.commit()

    status = "ENABLED 🟢" if settings.auto_nameguess_enabled else "DISABLED 🔴"
    await message.reply(f"ℹ️ <b>Auto Nameguess</b> is now <b>{status}</b> in this group chat.", parse_mode="HTML")

    if settings.auto_nameguess_enabled:
        if chat_id not in active_games:
            await start_nameguess_game(chat_id, db, bot, is_auto=True)
    else:
        if chat_id in active_games:
            game = active_games.pop(chat_id)
            if game.get("timer_task"):
                game["timer_task"].cancel()
            # Cleanup messages
            await cleanup_game_messages(chat_id, bot, game)
            await message.reply("🛑 Active auto game stopped because Auto Nameguess was toggled OFF.")

# ----------------------------------------------------
# CALLBACK HANDLERS
# ----------------------------------------------------

@router.callback_query(F.data.startswith("ng_hint:"))
async def cb_nameguess_hint(callback: CallbackQuery, db: AsyncSession):
    chat_id = int(callback.data.split(":")[1])

    if chat_id not in active_games:
        await callback.answer("❌ There is no active game running here.", show_alert=True)
        return

    game = active_games[chat_id]
    if game.get("hint_requested"):
        await callback.answer("⚠️ Hint has already been requested once for this game!", show_alert=True)
        return

    game["hint_requested"] = True
    hint_text = generate_vowel_hint(game["character_name"])

    card = (
        "💡 <b>Nameguess Hint</b>\n"
        "───────────────\n"
        f"👉 <code>{escape_html(hint_text)}</code>\n\n"
        "<i>Hint can only be requested once per game</i>"
    )
    hint_msg = await callback.message.reply(card, parse_mode="HTML")
    # Store hint message ID for cleanup
    game["hint_msg_ids"].append(hint_msg.message_id)
    await callback.answer("Hint revealed!")

@router.callback_query(F.data.startswith("ng_stop:"))
async def cb_nameguess_stop(callback: CallbackQuery, db: AsyncSession):
    chat_id = int(callback.data.split(":")[1])

    if chat_id not in active_games:
        await callback.answer("❌ There is no active game running here.", show_alert=True)
        return

    if not await is_admin_or_owner(callback, db):
        await callback.answer("❌ Only group admins or bot owners can stop the game.", show_alert=True)
        return

    game = active_games.pop(chat_id)
    if game.get("timer_task"):
        game["timer_task"].cancel()

    # Clean up old game images/hints
    await cleanup_game_messages(chat_id, callback.bot, game)

    admin_name = callback.from_user.first_name
    stop_text = f"🛑 Nameguess game stopped by <b>{escape_html(admin_name)}</b>."
    await callback.message.reply(stop_text, parse_mode="HTML")
    await callback.answer("Game stopped!")

# ----------------------------------------------------
# ANSWER GUESS MONITOR & LEGACY SPAWNS
# ----------------------------------------------------

def is_not_command(message: Message) -> bool:
    return message.text is not None and not message.text.startswith("/")

@router.message(F.chat.type.in_({"group", "supergroup"}), is_not_command)
async def group_message_monitor(message: Message, db: AsyncSession, bot):
    if not message.text:
        return

    chat_id = message.chat.id
    
    # 1. Handle Active Nameguess game evaluation
    if chat_id in active_games:
        game = active_games[chat_id]
        guess = message.text.strip()

        from utils.formatters import get_clean_name
        guess_clean = get_clean_name(guess).lower().replace('&', 'and')
        correct_clean = get_clean_name(game["character_name"]).lower().replace('&', 'and')

        is_correct = False
        if guess_clean == correct_clean:
            is_correct = True
        else:
            correct_parts = [p.strip() for p in correct_clean.split('and') if p.strip()]
            guess_parts = [p.strip() for p in guess_clean.split('and') if p.strip()]
            for gp in guess_parts:
                if gp in correct_parts or any(gp in cp for cp in correct_parts):
                    is_correct = True
                    break

        if is_correct:
            # Win! Clear active game timer & messages
            if game.get("timer_task"):
                game["timer_task"].cancel()
            active_games.pop(chat_id)

            # Cleanup card & hints
            await cleanup_game_messages(chat_id, bot, game)

            user_id = message.from_user.id
            username = message.from_user.username or ""
            first_name = message.from_user.first_name or "Trainer"

            user = await get_or_create_user(db, user_id, username, first_name)
            reward = game["reward"]
            user.coins += reward
            await db.commit()

            trainer_name = escape_html(first_name)
            ans_text = (
                f"🎉 <b>Correct! {trainer_name} guessed it!</b>\n"
                f"💡 Answer: <b>{escape_html(game['character_name'])}</b>\n"
                f"💰 <b>+{reward}</b> coins added!"
            )
            await message.reply(ans_text, parse_mode="HTML")

            # Check if auto loop needs to continue
            if game.get("is_auto"):
                await asyncio.sleep(2)
                stmt = select(GroupSettings).where(GroupSettings.chat_id == chat_id)
                res = await db.execute(stmt)
                settings = res.scalar_one_or_none()
                if settings and settings.auto_nameguess_enabled:
                    await start_nameguess_game(chat_id, db, bot, is_auto=True)
            return

    # 2. Legacy spawns are completely bypassed to let Nameguess run continuously
    return

# Legacy commands kept intact for command list consistency
@router.message(lambda msg: is_command_match(msg.text, ["catch", "snatch"]))
async def cmd_catch(message: Message, db: AsyncSession, bot):
    await message.reply("ℹ️ Catching wild characters is disabled. Please play `/nameguess` to guess characters and earn coins!", parse_mode="HTML")

@router.message(lambda msg: is_command_match(msg.text, ["spawnsettings"]))
async def cmd_spawnsettings(message: Message, db: AsyncSession, bot):
    await message.reply("ℹ️ Wild spawning is managed by the `/togglenameguess` command.", parse_mode="HTML")

@router.message(lambda msg: is_command_match(msg.text, ["setspawn"]))
async def cmd_setspawn(message: Message, db: AsyncSession, bot):
    await message.reply("ℹ️ Spawns are controlled via `/togglenameguess`.", parse_mode="HTML")
