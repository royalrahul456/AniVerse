import random
import time
import asyncio
import logging
import traceback
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
import config
from database.models import User, Character, UserCharacter, GroupSettings, RarityType, BotAdmin, ActiveSpawn
from utils.formatters import format_blockquote, get_rarity_emoji, escape_html
from handlers.start import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)

character_cache = {}
active_games = {} # chat_id -> dict with game details

def schedule_message_deletion(bot, chat_id: int, message_id: int, delay: int = 120):
    """Schedules background auto-deletion of a Telegram message after `delay` seconds."""
    async def _delete():
        await asyncio.sleep(delay)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
    asyncio.create_task(_delete())

async def get_random_character(db: AsyncSession, custom_rarity: str = None) -> Character:
    """Dynamically selects a character from the database weighted by rarity across ALL available characters."""
    stmt = select(Character)
    res = await db.execute(stmt)
    characters = res.scalars().all()
    if not characters:
        return None

    if custom_rarity:
        selected_rarity = custom_rarity.title()
    else:
        # Base weights from config.RARITY_CONFIG
        weights_map = {r_name.title(): info["weight"] for r_name, info in config.RARITY_CONFIG.items()}

        # Merge DB enabled rarities if set
        db_rar_stmt = select(RarityType).where(RarityType.spawn_enabled == True)
        db_rarities = (await db.execute(db_rar_stmt)).scalars().all()
        for dr in db_rarities:
            weights_map[dr.name.title()] = dr.weight

        # Available rarities present in database characters
        available_rarities = list(set(c.rarity.title() for c in characters if c.rarity))

        choices = []
        weights = []
        for r in available_rarities:
            choices.append(r)
            weights.append(weights_map.get(r, 10))

        selected_rarity = random.choices(choices, weights=weights, k=1)[0]

    filtered = [c for c in characters if c.rarity and c.rarity.title() == selected_rarity]
    if not filtered:
        filtered = characters

    return random.choice(filtered)

async def spawn_character(chat_id: int, db: AsyncSession, bot, custom_rarity: str = None) -> bool:
    character = await get_random_character(db, custom_rarity)
    if not character:
        return False

    await db.execute(delete(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id))
    
    active_spawn = ActiveSpawn(chat_id=chat_id, character_id=character.id)
    db.add(active_spawn)
    await db.commit()

    r_emoji = get_rarity_emoji(character.rarity)
    caption = (
        "✨ <b>A WILD CHARACTER HAS APPEARED!</b>\n\n"
        + format_blockquote(
            f"📺 <b>Anime:</b> {escape_html(character.anime)}\n"
            f"💎 <b>Rarity:</b> {r_emoji} {character.rarity}\n\n"
            f"🎯 <b>Catch Command:</b>\n"
            f"👉 <code>/guess &lt;name&gt;</code>"
        )
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

async def is_admin_or_owner(event, db: AsyncSession) -> bool:
    try:
        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return False
        # Owner check
        if config.ADMIN_IDS and user_id in config.ADMIN_IDS:
            return True
        # DB Admin check
        stmt = select(BotAdmin).where(BotAdmin.user_id == user_id)
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            return True
            
        # Get chat ID safely based on event type
        chat_id = None
        if isinstance(event, Message):
            chat_id = event.chat.id
        elif isinstance(event, CallbackQuery) and event.message:
            chat_id = event.message.chat.id
            
        if not chat_id:
            return False
            
        # Telegram admin check
        try:
            member = await event.bot.get_chat_member(chat_id, user_id)
            if member.status in ("creator", "administrator"):
                return True
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
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

    character = await get_random_character(db)
    if not character:
        return

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
        "⌛ You have 120 seconds!\n"
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
        raise e

    # Timeout timer task (120 seconds)
    async def game_timeout_timer(timeout_chat_id, char_name, bot_obj):
        await asyncio.sleep(120)
        if timeout_chat_id in active_games:
            game = active_games.pop(timeout_chat_id, None)
            
            # Clean up old game images/hints
            await cleanup_game_messages(timeout_chat_id, bot_obj, game)

            timeout_text = (
                "⏳ <b>Time is up!</b> No one guessed the character in time.\n"
                f"💡 Correct Answer: <b>{escape_html(char_name)}</b>"
            )
            try:
                t_msg = await bot_obj.send_message(timeout_chat_id, timeout_text, parse_mode="HTML")
                schedule_message_deletion(bot_obj, timeout_chat_id, t_msg.message_id, 120)
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

@router.message(Command("nameguess"))
async def cmd_nameguess(message: Message, db: AsyncSession, bot):
    try:
        chat_id = message.chat.id
        if message.chat.type not in ("group", "supergroup"):
            await message.reply("⚠️ This command can only be used inside group chats.")
            return

        if chat_id in active_games:
            await message.reply("⚠️ There is already an active Nameguess game in this chat! Solve that one first.")
            return

        await start_nameguess_game(chat_id, db, bot, is_auto=False, reward=150)
    except Exception as e:
        tb = traceback.format_exc()
        if len(tb) > 3000:
            tb = tb[:3000] + "\n...(truncated)..."
        error_msg = f"❌ <b>Error in nameguess command:</b>\n<code>{escape_html(str(e))}</code>\n\n<b>Traceback:</b>\n<code>{escape_html(tb)}</code>"
        await message.reply(error_msg, parse_mode="HTML")

@router.message(Command("togglenameguess"))
async def cmd_togglenameguess(message: Message, db: AsyncSession, bot):
    try:
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
    except Exception as e:
        tb = traceback.format_exc()
        if len(tb) > 3000:
            tb = tb[:3000] + "\n...(truncated)..."
        error_msg = f"❌ <b>Error in togglenameguess command:</b>\n<code>{escape_html(str(e))}</code>\n\n<b>Traceback:</b>\n<code>{escape_html(tb)}</code>"
        await message.reply(error_msg, parse_mode="HTML")
# ----------------------------------------------------
# CALLBACK HANDLERS
# ----------------------------------------------------

@router.callback_query(F.data.startswith("ng_hint:"))
async def cb_nameguess_hint(callback: CallbackQuery, db: AsyncSession):
    try:
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
    except Exception as e:
        logger.error(f"Error in hint callback: {e}")

@router.callback_query(F.data.startswith("ng_stop:"))
async def cb_nameguess_stop(callback: CallbackQuery, db: AsyncSession):
    try:
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
    except Exception as e:
        logger.error(f"Error in stop callback: {e}")

# ----------------------------------------------------
# ANSWER GUESS MONITOR & LEGACY SPAWNS
# ----------------------------------------------------

@router.message(F.chat.type.in_({"group", "supergroup"}))
async def group_message_monitor(message: Message, db: AsyncSession, bot):
    try:
        # Ignore bot commands
        if message.text and message.text.startswith("/"):
            return

        chat_id = message.chat.id
        
        # 1. Handle Active Nameguess game evaluation
        if chat_id in active_games and message.text:
            game = active_games[chat_id]
            guess = message.text.strip()

            from utils.formatters import get_clean_name
            # Normalize and split character name into words
            correct_clean = get_clean_name(game["character_name"]).lower()
            correct_words = [w.strip(".,()[]&") for w in correct_clean.split()]
            stop_words = {"and", "the", "of", "a", "d", "d.", "v2", "&"}
            correct_words_filtered = [w for w in correct_words if w and w not in stop_words]

            # Normalize and split guess into words
            guess_clean = get_clean_name(guess).lower()
            guess_words = [w.strip(".,()[]&") for w in guess_clean.split()]

            is_correct = False
            # Check if any word in the player's guess matches any of the character's major name words
            for gw in guess_words:
                if gw in correct_words_filtered:
                    is_correct = True
                    break
            
            # Fallback to exact comparison if filter removed all words
            if not is_correct and guess_clean == correct_clean:
                is_correct = True

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
                ans_msg = await message.reply(ans_text, parse_mode="HTML")
                schedule_message_deletion(bot, chat_id, ans_msg.message_id, 120)

                # Check if auto loop needs to continue
                if game.get("is_auto"):
                    await asyncio.sleep(2)
                    stmt = select(GroupSettings).where(GroupSettings.chat_id == chat_id)
                    res = await db.execute(stmt)
                    settings = res.scalar_one_or_none()
                    if settings and settings.auto_nameguess_enabled:
                        await start_nameguess_game(chat_id, db, bot, is_auto=True)
                return

        # 2. Increment message counter for wild character spawns
        stmt = select(GroupSettings).where(GroupSettings.chat_id == chat_id)
        res = await db.execute(stmt)
        settings = res.scalar_one_or_none()

        if not settings:
            settings = GroupSettings(chat_id=chat_id, spawn_threshold=10, message_counter=0, spawns_enabled=True)
            db.add(settings)
            await db.commit()

        if settings.spawns_enabled:
            settings.message_counter += 1
            if settings.message_counter >= settings.spawn_threshold:
                settings.message_counter = 0
                await db.commit()
                await spawn_character(chat_id, db, bot)
            else:
                await db.commit()
    except Exception as e:
        logger.error(f"Error in guess monitor: {e}")

    return

# /guess, /catch, /snatch = WILD SPAWN CATCHING ONLY → adds character to harem
# Nameguess game (coins only) is answered via plain text in group_message_monitor
@router.message(Command("guess", "catch", "snatch"))
async def cmd_catch(message: Message, db: AsyncSession, bot):
    try:
        parts = message.text.split(maxsplit=1)
        chat_id = message.chat.id
        user_id = message.from_user.id

        # No args → just show help on how to catch
        if len(parts) < 2:
            await message.reply(
                "🎯 <b>How to catch wild characters:</b>\n\n"
                "When a wild character spawns in the chat, use:\n"
                "<code>/guess &lt;character name&gt;</code>\n\n"
                "<i>💡 Tip: Any single word from the name works!\n"
                "e.g. for 'Monkey D. Luffy' → /guess luffy</i>",
                parse_mode="HTML"
            )
            return

        guess = parts[1].strip()

        # Only catch wild spawns — nameguess is a separate plain-text game
        nickname = escape_html(message.from_user.first_name if message.from_user else "Trainer")
        guess_lower = guess.strip().lower()

        spawn_stmt = select(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id)
        spawn_res = await db.execute(spawn_stmt)
        spawn = spawn_res.scalar_one_or_none()

        if not spawn:
            if message.chat.type == "private":
                await message.reply("⚠️ Wild characters only spawn in group chats. Keep chatting to trigger a spawn!", parse_mode="HTML")
            else:
                await message.reply("⚠️ No active wild character to catch right now! Keep chatting in group to spawn one.", parse_mode="HTML")
            return

        character = spawn.character
        if not character:
            await message.reply("⚠️ Error reading spawned character data.")
            return

        # Flexible matching logic (single word match or full match)
        from utils.formatters import get_clean_name
        actual_name_clean = get_clean_name(character.name).lower()
        actual_words = [w.strip(".,()[]&") for w in actual_name_clean.split()]
        stop_words = {"and", "the", "of", "a", "d", "d.", "v2", "&"}
        actual_words_filtered = [w for w in actual_words if w and w not in stop_words]

        guess_clean = get_clean_name(guess).lower()
        guess_words = [w.strip(".,()[]&") for w in guess_clean.split()]

        is_correct = any(gw in actual_words_filtered for gw in guess_words)
        if not is_correct and guess_clean == actual_name_clean:
            is_correct = True
        if not is_correct and guess_clean and guess_clean in actual_name_clean:
            is_correct = True

        if not is_correct:
            await message.reply("❌ Wrong name! Try again. 💡 <i>Any word from the name works.</i>", parse_mode="HTML")
            return

        # ✅ Correct! Add character to harem
        user = await get_or_create_user(db, user_id,
            message.from_user.username if message.from_user else "",
            message.from_user.first_name if message.from_user else "")
        coins_won = random.randint(config.CATCH_REWARD_MIN, config.CATCH_REWARD_MAX)
        user.coins += coins_won
        user.total_catches += 1

        user_char = UserCharacter(user_id=user_id, character_id=character.id, nickname=character.name)
        db.add(user_char)

        spawn_time = spawn.spawned_at
        seconds_taken = int((time.time() - spawn_time.timestamp())) if spawn_time else 5

        await db.delete(spawn)
        await db.commit()

        from utils.formatters import format_currency
        r_emoji = get_rarity_emoji(character.rarity)
        card_text = (
            f"💥 🌟 <b>{nickname}</b> caught <b>{escape_html(character.name)}</b>!\n\n"
            + format_blockquote(
                f"⛔ <b>NAME:</b> {escape_html(character.name)}\n"
                f"🎦 <b>ANIME:</b> {escape_html(character.anime)}\n"
                f"{r_emoji} <b>RARITY:</b> {character.rarity}\n"
                f"⏱️ <b>TIME:</b> {seconds_taken}s\n"
                f"💰 <b>+{coins_won} {config.CURRENCY_EMOJI}</b> earned!"
            )
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🎒 View Harem", callback_data=f"dm_bag_{user_id}_All_1_anime"))
        catch_msg = await message.reply(card_text, parse_mode="HTML", reply_markup=builder.as_markup())
        schedule_message_deletion(bot, chat_id, catch_msg.message_id, 120)
    except Exception as e:
        logger.error(f"Error in cmd_catch command: {e}")
        await message.reply("⚠️ An error occurred while trying to catch the character.")

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

@router.message(Command("setspawn", "spawnchance", "changetime", "spawnrate", "spawnthreshold"))
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

@router.message(Command("togglespawn"))
async def cmd_togglespawn(message: Message, db: AsyncSession, bot):
    """Quick toggle for enabling/disabling wild character spawns in a group."""
    if message.chat.type == "private":
        await message.reply("⚠️ This command can only be used in group chats.")
        return

    if not await is_user_allowed(message, bot):
        await message.reply("⚠️ Only group administrators or the bot owner can toggle spawn settings.")
        return

    chat_id = message.chat.id
    stmt = select(GroupSettings).where(GroupSettings.chat_id == chat_id)
    res = await db.execute(stmt)
    settings = res.scalar_one_or_none()

    if not settings:
        settings = GroupSettings(chat_id=chat_id, spawn_threshold=10, message_counter=0, spawns_enabled=True)
        db.add(settings)

    settings.spawns_enabled = not settings.spawns_enabled
    await db.commit()

    if settings.spawns_enabled:
        status = "✅ <b>ENABLED</b>"
        detail = f"Characters will spawn every <b>{settings.spawn_threshold}</b> messages."
    else:
        status = "❌ <b>DISABLED</b>"
        detail = "No wild characters will spawn until re-enabled."

    text = (
        f"⚙️ Wild Spawn is now {status}\n"
        f"💬 {detail}\n\n"
        f"<i>Use /spawnsettings to view full settings.</i>"
    )
    await message.reply(text, parse_mode="HTML")
