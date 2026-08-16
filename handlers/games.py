from utils.emojis import get_emoji
import random
import datetime
import math
import json
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import config
from database.models import User, ActiveGame
from utils.formatters import format_blockquote, escape_html
from handlers.start import get_or_create_user
from utils.game_limits import check_game_limit, record_game_play
from keyboards.inline import get_games_keyboard, get_back_to_hub_keyboard


import asyncio

router = Router()

def schedule_message_deletion(bot, chat_id: int, message_id: int, delay: int = 120):
    """Schedules background auto-deletion of a Telegram message after `delay` seconds."""
    async def _delete():
        await asyncio.sleep(delay)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
    asyncio.create_task(_delete())

@router.callback_query(F.data == "dm_games")
@router.message(Command("games"))
async def cmd_games(event, db: AsyncSession):
    text = (
        "🎮 <b>AniVerse Games Center</b>\n\n"
        + format_blockquote(
            "Welcome to the Arcade Arena! Choose from any of our thrilling minigames below to earn coins, increase your streak, and buy rare mystery boxes!"
        )
    )
    kb = get_games_keyboard()
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "game_spin")
@router.message(Command("spin"))
async def cmd_spin(event, db: AsyncSession):
    user_id = event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    can_play, current_count, remaining_seconds = await check_game_limit(db, user_id, "spin", 3)
    if not can_play:
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        text = (
            "⏳ <b>Spin Wheel Limit Reached!</b>\n\n"
            + format_blockquote(
                f"You have already used your <b>3</b> daily free spins!\n\n"
                f"Come back in <b>{hours}h {minutes}m</b> for more spins!\n<i>Resets daily at 5:30 AM IST</i>"
            )
        )
        if isinstance(event, CallbackQuery):
            await event.answer(f"{get_emoji('error')} Spin limit reached!", show_alert=True)
            await message_obj.edit_text(text, parse_mode="HTML")
        else:
            await message_obj.reply(text, parse_mode="HTML")
        return

    user = await get_or_create_user(db, user_id, event.from_user.username, event.from_user.first_name)
    won_coins = random.choice(config.SPIN_REWARDS)
    user.coins += won_coins
    await db.commit()

    await record_game_play(db, user_id, "spin")

    text = (
        "🎰 <b>LUCKY WHEEL SPIN!</b> 🎰\n\n"
        + format_blockquote(
            f"🌀 <i>*The wheel spins rapidly...*</i>\n\n"
            f"{get_emoji('party')} <b>Land:</b> +{won_coins} {config.CURRENCY_EMOJI} {config.CURRENCY_NAME}!\n"
            f"{get_emoji('coin')} <b>Total Balance:</b> {user.coins:,} {config.CURRENCY_NAME}\n"
            f"{get_emoji('target')} <b>Remaining spins today:</b> {2 - current_count}/3"
        )
    )
    if isinstance(event, CallbackQuery):
        await message_obj.edit_text(text, parse_mode="HTML")
        await event.answer()
    else:
        spin_msg = await message_obj.reply(text, parse_mode="HTML")
        schedule_message_deletion(message_obj.bot, message_obj.chat.id, spin_msg.message_id, 120)

@router.message(Command("daily"))
async def cmd_daily(message: Message, db: AsyncSession):
    user = await get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    now = datetime.datetime.utcnow()

    if user.last_daily and (now - user.last_daily).total_seconds() < 86400:
        remaining = 86400 - (now - user.last_daily).total_seconds()
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await message.answer(
            f"🔥 <b>Daily Streak Reward</b>\n\n"
            + format_blockquote(f"You've already claimed your daily reward today! Come back in <b>{hours}h {minutes}m</b>."),
            parse_mode="HTML"
        )
        return

    reward = random.randint(config.DAILY_REWARD_MIN, config.DAILY_REWARD_MAX)
    user.daily_streak += 1
    user.coins += reward
    user.last_daily = now
    await db.commit()

    text = (
        f"🔥 <b>{user.daily_streak}-Day Streak Claimed!</b>\n\n"
        + format_blockquote(
            f"{get_emoji('party')} <b>Reward:</b> +{reward} {config.CURRENCY_EMOJI} {config.CURRENCY_NAME}!\n"
            f"{get_emoji('target')} <b>Keep your streak going tomorrow!</b>\n"
            f"{get_emoji('coin')} <b>Total Balance:</b> {user.coins:,} {config.CURRENCY_NAME}"        )
    )
    daily_msg = await message.answer(text, parse_mode="HTML")
    schedule_message_deletion(message.bot, message.chat.id, daily_msg.message_id, 120)

@router.callback_query(F.data == "game_coinflip")
@router.message(Command("coinflip"))
async def cmd_coinflip(event, db: AsyncSession):
    user_id = event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    is_callback = isinstance(event, CallbackQuery)
    
    can_play, current_count, remaining_seconds = await check_game_limit(db, user_id, "coinflip", 2)
    if not can_play:
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        text = (
            "⏳ <b>Coin Flip Limit Reached!</b>\n\n"
            + format_blockquote(
                f"You have already played your <b>2</b> daily coin flips!\n\n"
                f"Come back in <b>{hours}h {minutes}m</b>!\n<i>Resets daily at 5:30 AM IST</i>"
            )
        )
        if is_callback:
            await event.answer(f"{get_emoji('error')} Coin Flip limit reached!", show_alert=True)
            await message_obj.edit_text(text, parse_mode="HTML")
        else:
            await message_obj.reply(text, parse_mode="HTML")
        return

    user = await get_or_create_user(db, user_id, event.from_user.username, event.from_user.first_name)
    bet = 100
    if user.coins < bet:
        text = f"{get_emoji('error')} You need at least 100 {config.CURRENCY_NAME} to flip a coin!"
        if is_callback:
            await event.answer(text, show_alert=True)
        else:
            await message_obj.reply(text)
        return

    win = random.choice([True, False])
    outcome = "Heads" if win else "Tails"
    if win:
        user.coins += bet
        res_text = f"{get_emoji('party')} <b>WIN!</b> It landed on {outcome}! You won +{bet} {config.CURRENCY_NAME}!"
    else:
        user.coins -= bet
        res_text = f"💀 <b>LOSS!</b> It landed on {outcome}! You lost {bet} {config.CURRENCY_NAME}."

    await db.commit()
    await record_game_play(db, user_id, "coinflip")

    card = (
        f"🪙 <b>COIN FLIP CHALLENGE</b>\n\n" 
        + format_blockquote(
            f"{res_text}\n"
            f"{get_emoji('coin')} <b>Balance:</b> {user.coins:,} {config.CURRENCY_NAME}\n"
            f"{get_emoji('target')} <b>Remaining flips today:</b> {1 - current_count}/2"
        )
    )
    if is_callback:
        await message_obj.edit_text(card, parse_mode="HTML")
        await event.answer()
    else:
        await message_obj.reply(card, parse_mode="HTML")
@router.callback_query(F.data == "game_dice")
@router.message(Command("dice"))
async def cmd_dice(event, db: AsyncSession):
    user_id = event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    is_callback = isinstance(event, CallbackQuery)
    
    can_play, current_count, remaining_seconds = await check_game_limit(db, user_id, "dice", 2)
    if not can_play:
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        text = (
            "⏳ <b>Dice Roll Limit Reached!</b>\n\n"
            + format_blockquote(
                f"You have already played your <b>2</b> daily dice rolls!\n\n"
                f"Come back in <b>{hours}h {minutes}m</b>!\n<i>Resets daily at 5:30 AM IST</i>"
            )
        )
        if is_callback:
            await event.answer(f"{get_emoji('error')} Dice limit reached!", show_alert=True)
            await message_obj.edit_text(text, parse_mode="HTML")
        else:
            await message_obj.reply(text, parse_mode="HTML")
        return

    user = await get_or_create_user(db, user_id, event.from_user.username, event.from_user.first_name)
    bet = 100
    if user.coins < bet:
        text = f"{get_emoji('error')} You need at least 100 coins to roll the dice!"
        if is_callback:
            await event.answer(text, show_alert=True)
        else:
            await message_obj.reply(text)
        return

    # Send dice emoji first
    if is_callback:
        await message_obj.edit_text("🎲 <i>*Rolling the dice...*</i>", parse_mode="HTML")
        dice_msg = await message_obj.reply_dice(emoji="🎲")
        await event.answer()
    else:
        dice_msg = await message_obj.reply_dice(emoji="🎲")

    # Wait for animation to finish
    import asyncio
    await asyncio.sleep(3.5)
    
    roll = dice_msg.dice.value
    if roll >= 4:
        reward = 150
        user.coins += reward
        res = f"🎲 You rolled a <b>{roll}</b>! {get_emoji('party')} <b>WIN!</b> +{reward} Coins!"
    else:
        loss = 50
        user.coins -= loss
        res = f"🎲 You rolled a <b>{roll}</b>! 💀 <b>LOSS!</b> -{loss} Coins."

    await db.commit()
    await record_game_play(db, user_id, "dice")

    card = (
        "🎲 <b>DICE ROLL BET</b>\n\n" 
        + format_blockquote(
            f"{res}\n"
            f"{get_emoji('coin')} <b>Balance:</b> {user.coins:,} Coins\n"
            f"{get_emoji('target')} <b>Remaining rolls today:</b> {1 - current_count}/2"
        )
    )

    if is_callback:
        await message_obj.edit_text(card, parse_mode="HTML")
    else:
        dice_res_msg = await dice_msg.reply(card, parse_mode="HTML")
        schedule_message_deletion(message_obj.bot, message_obj.chat.id, dice_res_msg.message_id, 120)

@router.callback_query(F.data == "game_dart")
@router.message(Command("dart"))
async def cmd_dart(event, db: AsyncSession):
    user_id = event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    is_callback = isinstance(event, CallbackQuery)
    can_play, current_count, remaining_seconds = await check_game_limit(db, user_id, "dart", 2)
    if not can_play:
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        text = (
            "⏳ <b>Dart Throw Limit Reached!</b>\n\n"
            + format_blockquote(
                f"You have already played your <b>2</b> daily dart throws!\n\n"
                f"Come back in <b>{hours}h {minutes}m</b>!\n<i>Resets daily at 5:30 AM IST</i>"
            )
        )
        if is_callback:
            await event.answer(f"{get_emoji('error')} Dart limit reached!", show_alert=True)
            await message_obj.edit_text(text, parse_mode="HTML")
        else:
            await message_obj.reply(text, parse_mode="HTML")
        return

    user = await get_or_create_user(db, user_id, event.from_user.username, event.from_user.first_name)
    bet = 100
    if user.coins < bet:
        text = f"{get_emoji('error')} You need at least 100 coins to throw a dart!"
        if is_callback:
            await event.answer(text, show_alert=True)
        else:
            await message_obj.reply(text)
        return

    # Send dart emoji first
    if is_callback:
        await message_obj.edit_text(f"{get_emoji('target')} <i>*Throwing the dart...*</i>", parse_mode="HTML")
        dart_msg = await message_obj.reply_dice(emoji=f"{get_emoji('target')}")
        await event.answer()
    else:
        dart_msg = await message_obj.reply_dice(emoji=f"{get_emoji('target')}")

    # Wait for animation to finish
    import asyncio
    await asyncio.sleep(3.5)
    
    score = dart_msg.dice.value
    # Multipliers applied: 150 * 1.05 = 157.5 -> 157; 50 * 1.05 = 52.5 -> 52
    if score >= 4:
        reward = 157
        user.coins += reward
        res = f"{get_emoji('target')} You hit a <b>{score}</b>! {get_emoji('party')} <b>WIN!</b> +{reward} Coins!"
    else:
        loss = 52
        user.coins -= loss
        res = f"{get_emoji('target')} You hit a <b>{score}</b>! 💀 <b>LOSS!</b> -{loss} Coins."

    await db.commit()
    await record_game_play(db, user_id, "dart")

    card = (
        f"{get_emoji('target')} <b>DART ARENA CHALLENGE</b>\n\n" 
        + format_blockquote(
            f"{res}\n"
            f"{get_emoji('coin')} <b>Balance:</b> {user.coins:,} Coins\n"
            f"{get_emoji('target')} <b>Remaining throws today:</b> {1 - current_count}/2"
        )
    )

    if is_callback:
        await message_obj.edit_text(card, parse_mode="HTML")
    else:
        dart_res_msg = await dart_msg.reply(card, parse_mode="HTML")
        schedule_message_deletion(message_obj.bot, message_obj.chat.id, dart_res_msg.message_id, 120)

# Trivia Questions List
TRIVIA_QUESTIONS = [
    {
        "q": "Who is known as the Strongest Sorcerer in Jujutsu Kaisen?",
        "opts": ["Gojo Satoru", "Ryomen Sukuna", "Megumi Fushiguro", "Yuji Itadori"],
        "ans": 0
    },
    {
        "q": "Who is the protagonist of One Piece?",
        "opts": ["Roronoa Zoro", "Monkey D. Luffy", "Vinsmoke Sanji", "Portgas D. Ace"],
        "ans": 1
    },
    {
        "q": "What is Goku's signature energy attack in Dragon Ball?",
        "opts": ["Rasengan", "Spirit Gun", "Chidori", "Kamehameha"],
        "ans": 3
    },
    {
        "q": "Who is known as the 'Copy Ninja' in Naruto?",
        "opts": ["Kakashi Hatake", "Sasuke Uchiha", "Itachi Uchiha", "Jiraiya"],
        "ans": 0
    },
    {
        "q": "What is Saitama's hero name in One Punch Man?",
        "opts": ["Caped Baldy", "Demon Cyborg", "Silver Fang", "Tornado of Terror"],
        "ans": 0
    },
    {
        "q": "Who is the main protagonist of Attack on Titan?",
        "opts": ["Armin Arlert", "Levi Ackerman", "Eren Yeager", "Mikasa Ackerman"],
        "ans": 2
    },
    {
        "q": "In Demon Slayer, who is Tanjiro's demon sister?",
        "opts": ["Nezuko Kamado", "Shinobu Kocho", "Kanao Tsuyuri", "Mitsuri Kanroji"],
        "ans": 0
    },
    {
        "q": "Which anime features characters called 'Ghouls' who feed on humans?",
        "opts": ["Bleach", "Tokyo Ghoul", "Naruto", "Death Note"],
        "ans": 1
    },
    {
        "q": "What is the name of the notebook that can kill anyone whose name is written in it?",
        "opts": ["Death Book", "Kill Note", "Death Note", "Shinshoku"],
        "ans": 2
    },
    {
        "q": "Which guild does Natsu Dragneel belong to in Fairy Tail?",
        "opts": ["Fairy Tail", "Blue Pegasus", "Sabertooth", "Lamia Scale"],
        "ans": 0
    }
]

@router.callback_query(F.data == "game_trivia")
@router.message(Command("trivia"))
async def cmd_trivia(event, db: AsyncSession):
    user_id = event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    
    # Pick a random question
    q_idx = random.randint(0, len(TRIVIA_QUESTIONS) - 1)
    question_data = TRIVIA_QUESTIONS[q_idx]
    
    # Build options buttons
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    
    # Render option buttons
    for opt_idx, opt in enumerate(question_data["opts"]):
        builder.row(InlineKeyboardButton(
            text=opt,
            callback_data=f"t_a:{user_id}:{q_idx}:{opt_idx}"
        ))
    builder.row(InlineKeyboardButton(text=f"{get_emoji('back')} Back to Games", callback_data="dm_games"))
    
    text = (
        "🧠 <b>ANIME TRIVIA CHALLENGE!</b>\n\n"
        + format_blockquote(
            f"❓ <b>Question:</b>\n{question_data['q']}\n\n"
            f"{get_emoji('coin')} <b>Reward:</b> +{config.TRIVIA_REWARD} Coins!"
        )
    )
    
    if isinstance(event, CallbackQuery):
        await message_obj.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        await event.answer()
    else:
        await message_obj.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("t_a:"))
async def handle_trivia_answer(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer(f"{get_emoji('error')} Invalid game session.", show_alert=True)
        return
        
    _, play_id_str, q_idx_str, opt_idx_str = parts
    play_id = int(play_id_str)
    q_idx = int(q_idx_str)
    opt_idx = int(opt_idx_str)
    
    if callback.from_user.id != play_id:
        await callback.answer(f"{get_emoji('error')} This trivia challenge is not yours! Start a new one with /trivia.", show_alert=True)
        return
        
    if q_idx >= len(TRIVIA_QUESTIONS):
        await callback.answer(f"{get_emoji('error')} Question no longer exists.", show_alert=True)
        return
        
    question_data = TRIVIA_QUESTIONS[q_idx]
    user = await get_or_create_user(db, play_id, callback.from_user.username, callback.from_user.first_name)
    
    is_correct = (opt_idx == question_data["ans"])
    chosen_opt = question_data["opts"][opt_idx]
    correct_opt = question_data["opts"][question_data["ans"]]
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"TRIVIA: User {play_id} clicked index {opt_idx} ({chosen_opt}) for Q_{q_idx}. Correct is index {question_data['ans']} ({correct_opt}). result={is_correct}")
    if is_correct:
        reward = config.TRIVIA_REWARD
        user.coins += reward
        await db.commit()        
        card = (
            "🧠 <b>ANIME TRIVIA CHALLENGE!</b>\n\n"
            + format_blockquote(
                f"❓ <b>Question:</b> {question_data['q']}\n\n"
                f"{get_emoji('success')} <b>Your Answer:</b> {chosen_opt} (Correct!)\n"
                f"{get_emoji('party')} <b>Reward:</b> +{reward} Coins!\n"
                f"{get_emoji('coin')} <b>Balance:</b> {user.coins:,} Coins"
            )
        )
    else:
        card = (
            "🧠 <b>ANIME TRIVIA CHALLENGE!</b>\n\n"
            + format_blockquote(
                f"❓ <b>Question:</b> {question_data['q']}\n\n"
                f"{get_emoji('error')} <b>Your Answer:</b> {chosen_opt} (Incorrect!)\n"
                f"💡 <b>Correct Answer:</b> {correct_opt}\n"
                f"💀 <b>Reward:</b> 0 Coins\n"
                f"{get_emoji('coin')} <b>Balance:</b> {user.coins:,} Coins"
            )
        )
        
    await callback.message.edit_text(card, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
    await callback.answer()

import math

def get_combination(n, k):
    if k < 0 or k > n:
        return 0
    return math.comb(n, k)

def get_mines_multiplier(mines_count: int, revealed_count: int) -> float:
    if revealed_count == 0:
        return 1.0
    total = 25
    safe = total - mines_count
    if revealed_count > safe:
        return 0.0
    
    num = get_combination(total, revealed_count)
    den = get_combination(safe, revealed_count)
    if den == 0:
        return 0.0
    
    val = 0.96 * (num / den)
    return round(val, 2)

@router.message(Command("endmines"))
async def cmd_endmines(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    
    stmt = select(ActiveGame).where(ActiveGame.user_id == user_id, ActiveGame.game_type == "mines")
    res = await db.execute(stmt)
    game = res.scalar_one_or_none()
    
    if not game:
        await message.reply(f"{get_emoji('error')} You do not have any active Mines game!")
        return

    state = json.loads(game.data)
    bet = state.get("bet", 0)
    
    await db.delete(game)
    await db.commit()
    
    await message.reply(f"💸 Your active Mines game has been force-quit. Your bet of <b>{bet:,} coins</b> has been lost.", parse_mode="HTML")

@router.callback_query(F.data == "game_mines")
@router.message(Command("mines"))
async def cmd_mines(event, db: AsyncSession):
    user_id = event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    is_callback = isinstance(event, CallbackQuery)
    first_name = event.from_user.first_name
    
    # Enforce official group rule in group chats
    if not is_callback and message_obj.chat.type in ["group", "supergroup"]:
        if message_obj.chat.username != "AniVerseUnion":
            await message_obj.reply(f"{get_emoji('warning')} Mines can only be played in private DM or in our official group chat @AniVerseUnion.")
            return

    bet = 100
    mines_count = 3
    
    if not is_callback:
        parts = message_obj.text.strip().split()
        if len(parts) < 2:
            await message_obj.reply(
                f"{get_emoji('warning')} <b>Mines Game Usage:</b>\n"
                f"{get_emoji('pointer')} <code>/mines &lt;bet&gt; [mines_count]</code>\n\n"
                "• <b>Bet range:</b> 10 to 100,000 coins\n"
                "• <b>Mines count:</b> 1 to 24 (default is 3)",
                parse_mode="HTML"
            )
            return
            
        bet_str = parts[1]
        if not bet_str.isdigit():
            await message_obj.reply(f"{get_emoji('error')} Bet must be a valid positive number.")
            return
        bet = int(bet_str)
        
        if bet < 10 or bet > 100000:
            await message_obj.reply(f"{get_emoji('error')} Bet must be between 10 and 100,000 coins.")
            return
            
        if len(parts) >= 3:
            mines_str = parts[2]
            if not mines_str.isdigit():
                await message_obj.reply(f"{get_emoji('error')} Mines count must be a number between 1 and 24.")
                return
            mines_count = int(mines_str)
            if mines_count < 1 or mines_count > 24:
                await message_obj.reply(f"{get_emoji('error')} Mines count must be between 1 and 24.")
                return
    else:
        # Default options if clicked from button callback
        bet = 100
        mines_count = 3

    stmt = select(ActiveGame).where(ActiveGame.user_id == user_id, ActiveGame.game_type == "mines")
    res = await db.execute(stmt)
    game = res.scalar_one_or_none()
    
    if game:
        await message_obj.reply(f"{get_emoji('error')} You already have an active Mines game! End it first using /endmines.")
        return

    user = await get_or_create_user(db, user_id, event.from_user.username, event.from_user.first_name)
    if user.coins < bet:
        await message_obj.reply(f"{get_emoji('error')} You do not have enough coins to start this game! (Balance: {user.coins:,} coins)")
        return

    # Deduct bet
    user.coins -= bet

    # Generate 5x5 mines (indexes 0 to 24)
    mine_indices = random.sample(range(25), mines_count)
    game_state = {
        "bet": bet,
        "mines_count": mines_count,
        "mines": mine_indices,
        "revealed": [],
        "reward": 0,
        "status": "playing",
        "hit_tile": -1
    }

    new_game = ActiveGame(user_id=user_id, game_type="mines", data=json.dumps(game_state))
    db.add(new_game)
    await db.commit()

    kb = render_mines_keyboard(user_id, game_state)
    card = (
        f"{get_emoji('bomb')} <b>MINES GAME STARTED</b> {get_emoji('bomb')}\n\n"
        + format_blockquote(
            f"{get_emoji('user')} Trainer: <b>{escape_html(first_name)}</b>\n"
            f"{get_emoji('coin')} Bet: <b>{bet:,} coins</b>\n"
            f"{get_emoji('bomb')} Mines: <b>{mines_count} {get_emoji('bomb')}</b>\n"
            f"📈 Multiplier: <b>1.0x</b>"
        )
        + f"\n{get_emoji('pointer')} Click on the tiles below to find diamonds! Avoid the mines!"
    )

    if is_callback:
        await message_obj.edit_text(card, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await message_obj.reply(card, parse_mode="HTML", reply_markup=kb)

def render_mines_keyboard(user_id: int, state: dict) -> InlineKeyboardMarkup:
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    builder = InlineKeyboardBuilder()

    mines = state["mines"]
    revealed = state["revealed"]
    status = state["status"]
    hit_tile = state.get("hit_tile", -1)

    buttons = []
    for idx in range(25):
        if status == "playing":
            if idx in revealed:
                buttons.append(InlineKeyboardButton(text=f"{get_emoji('gem')}", callback_data="noop"))
            else:
                buttons.append(InlineKeyboardButton(text="❓", callback_data=f"mines_click:{user_id}:{idx}"))
        else:
            if idx == hit_tile:
                buttons.append(InlineKeyboardButton(text=f"{get_emoji('bomb')}", callback_data="noop"))
            elif idx in mines:
                buttons.append(InlineKeyboardButton(text=f"{get_emoji('bomb')}", callback_data="noop"))
            elif idx in revealed:
                buttons.append(InlineKeyboardButton(text=f"{get_emoji('gem')}", callback_data="noop"))
            else:
                buttons.append(InlineKeyboardButton(text="🟢", callback_data="noop"))

    for i in range(0, 25, 5):
        builder.row(buttons[i], buttons[i+1], buttons[i+2], buttons[i+3], buttons[i+4])

    if status == "playing":
        current_multiplier = get_mines_multiplier(state["mines_count"], len(revealed))
        current_reward = int(state["bet"] * current_multiplier)
        if len(revealed) >= 1:
            builder.row(InlineKeyboardButton(
                text=f"{get_emoji('coin')} Cashout (+{current_reward:,} Coins)",
                callback_data=f"mines_cashout:{user_id}"
            ))
    return builder.as_markup()

@router.callback_query(F.data.startswith("mines_click:"))
async def handle_mines_click(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer(f"{get_emoji('error')} Invalid session.", show_alert=True)
        return

    _, play_id_str, idx_str = parts
    play_id = int(play_id_str)
    idx = int(idx_str)

    if callback.from_user.id != play_id:
        await callback.answer(f"{get_emoji('error')} This game is not yours! Start a new one with /mines.", show_alert=True)
        return

    stmt = select(ActiveGame).where(ActiveGame.user_id == play_id, ActiveGame.game_type == "mines")
    res = await db.execute(stmt)
    game = res.scalar_one_or_none()
    if not game:
        await callback.answer(f"{get_emoji('error')} Game not found. Start a new one with /mines.", show_alert=True)
        return

    state = json.loads(game.data)
    if state["status"] != "playing":
        await callback.answer(f"{get_emoji('error')} Game already finished.", show_alert=True)
        return

    mines = state["mines"]
    revealed = state["revealed"]
    bet = state["bet"]
    mines_count = state["mines_count"]

    if idx in revealed:
        await callback.answer()
        return

    user = await get_or_create_user(db, play_id, callback.from_user.username, callback.from_user.first_name)
    first_name = callback.from_user.first_name

    if idx in mines:
        state["status"] = "lost"
        state["hit_tile"] = idx
        await db.delete(game)
        await db.commit()

        kb = render_mines_keyboard(play_id, state)
        card = (
            "💥 <b>BOOM! GAME OVER</b> 💥\n\n"
            + format_blockquote(
                f"{get_emoji('user')} Trainer: <b>{escape_html(first_name)}</b>\n"
                f"{get_emoji('bomb')} Hit Tile: <b>#{idx}</b>\n"
                f"💸 Lost Bet: <b>-{bet:,} coins</b>\n"
                f"{get_emoji('coin')} New Balance: <b>{get_emoji('coin')} {user.coins:,} coins</b>"
            )
        )
        await callback.message.edit_text(card, parse_mode="HTML", reply_markup=kb)
        await callback.answer("💥 BOOM! You hit a mine!", show_alert=True)
    else:
        revealed.append(idx)
        diamonds_found = len(revealed)
        
        multiplier = get_mines_multiplier(mines_count, diamonds_found)
        potential_win = int(bet * multiplier)
        
        safe_tiles_count = 25 - mines_count
        if diamonds_found == safe_tiles_count:
            state["status"] = "won"
            user.coins += potential_win
            await db.delete(game)
            await db.commit()

            kb = render_mines_keyboard(play_id, state)
            card = (
                f"{get_emoji('trophy')} <b>MAXIMUM WIN!</b> {get_emoji('trophy')}\n\n"
                + format_blockquote(
                    f"{get_emoji('user')} Trainer: <b>{escape_html(first_name)}</b>\n"
                    f"🌟 Result: <b>Cleared all safe tiles!</b>\n"
                    f"📈 Multiplier: <b>{multiplier}x</b>\n"
                    f"{get_emoji('coin')} Earnings: <b>+{potential_win:,} coins</b>\n"
                    f"{get_emoji('coin')} New Balance: <b>{get_emoji('coin')} {user.coins:,} coins</b>"
                )
            )
            await callback.message.edit_text(card, parse_mode="HTML", reply_markup=kb)
            await callback.answer(f"{get_emoji('trophy')} Maximum win! All safe tiles cleared!", show_alert=True)
        else:
            game.data = json.dumps(state)
            await db.commit()

            kb = render_mines_keyboard(play_id, state)
            card = (
                f"{get_emoji('bomb')} <b>MINES GAME</b> {get_emoji('bomb')}\n\n"
                + format_blockquote(
                    f"{get_emoji('user')} Trainer: <b>{escape_html(first_name)}</b>\n"
                    f"{get_emoji('coin')} Bet: <b>{bet:,} coins</b>\n"
                    f"{get_emoji('bomb')} Mines: <b>{mines_count} {get_emoji('bomb')}</b>\n"
                    f"{get_emoji('gem')} Diamonds: <b>{diamonds_found} {get_emoji('gem')}</b>\n"
                    f"📈 Multiplier: <b>{multiplier}x</b>\n"
                    f"{get_emoji('coin')} Potential Win: <b>{potential_win:,} coins</b>"
                )
                + f"\n{get_emoji('pointer')} Keep clicking or cash out!"
            )
            await callback.message.edit_text(card, parse_mode="HTML", reply_markup=kb)
            await callback.answer(f"{get_emoji('gem')} Diamond found!")

@router.callback_query(F.data.startswith("mines_cashout:"))
async def handle_mines_cashout(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split(":")
    if len(parts) != 2:
        return

    play_id = int(parts[1])
    if callback.from_user.id != play_id:
        await callback.answer(f"{get_emoji('error')} This game is not yours!", show_alert=True)
        return

    stmt = select(ActiveGame).where(ActiveGame.user_id == play_id, ActiveGame.game_type == "mines")
    res = await db.execute(stmt)
    game = res.scalar_one_or_none()
    if not game:
        await callback.answer(f"{get_emoji('error')} Game already finished.", show_alert=True)
        return

    state = json.loads(game.data)
    bet = state["bet"]
    mines_count = state["mines_count"]
    revealed = state["revealed"]

    user = await get_or_create_user(db, play_id, callback.from_user.username, callback.from_user.first_name)
    first_name = callback.from_user.first_name

    multiplier = get_mines_multiplier(mines_count, len(revealed))
    earnings = int(bet * multiplier)
    profit = earnings - bet
    
    user.coins += earnings
    state["status"] = "cashed_out"

    await db.delete(game)
    await db.commit()

    kb = render_mines_keyboard(play_id, state)
    card = (
        f"{get_emoji('coin')} <b>CASHOUT SUCCESSFUL!</b> {get_emoji('coin')}\n\n"
        + format_blockquote(
            f"{get_emoji('user')} Trainer: <b>{escape_html(first_name)}</b>\n"
            f"📈 Multiplier: <b>{multiplier}x</b>\n"
            f"{get_emoji('coin')} Earnings: <b>+{earnings:,} coins</b> (Profit: <b>+{profit:+,} coins</b>)\n"
            f"{get_emoji('coin')} New Balance: <b>{get_emoji('coin')} {user.coins:,} coins</b>"
        )
    )
    await callback.message.edit_text(card, parse_mode="HTML", reply_markup=kb)
    await callback.answer("💵 Cashed out successfully!")

@router.callback_query(F.data == "game_scramble")
@router.message(Command("scramble"))
async def cmd_scramble(event, db: AsyncSession):
    user_id = event.from_user.id if isinstance(event, Message) else event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    
    user = await get_or_create_user(db, user_id, event.from_user.username, event.from_user.first_name)
    reward = 150
    user.coins += reward
    await db.commit()

    card = (
        "🧩 <b>WORD SCRAMBLE ARENA</b>\n\n"
        + format_blockquote(
            "🔤 <b>Unscrambled:</b> N-A-R-U-T-O -> Naruto Uzumaki!\n"
            f"{get_emoji('party')} <b>Reward:</b> +{reward} Coins!\n"
            f"{get_emoji('coin')} <b>Balance:</b> {user.coins:,} Coins"
        )
    )
    if isinstance(event, CallbackQuery):
        await message_obj.edit_text(card, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
        await event.answer()
    else:
        scram_msg = await message_obj.answer(card, parse_mode="HTML")
        schedule_message_deletion(message_obj.bot, message_obj.chat.id, scram_msg.message_id, 120)

@router.message(Command("rob"))
async def cmd_rob(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    target_id = None
    target_name = None

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name
    else:
        parts = message.text.split()
        if len(parts) > 1:
            if message.entities:
                for entity in message.entities:
                    if entity.type == "text_mention":
                        target_id = entity.user.id
                        target_name = entity.user.first_name
                        break
        if not target_id:
            await message.reply(f"{get_emoji('warning')} You must reply to a user or @mention them to rob them!")
            return

    if user_id == target_id:
        await message.reply(f"{get_emoji('warning')} You can't rob yourself!")
        return

    # Check cooldown
    from database.models import UserDailyLimit
    import time
    limit_stmt = select(UserDailyLimit).where(UserDailyLimit.user_id == user_id)
    limit_res = await db.execute(limit_stmt)
    limit = limit_res.scalar_one_or_none()

    now_ts = int(time.time())
    if limit and limit.last_rob_at:
        elapsed = now_ts - limit.last_rob_at
        if elapsed < 3600:
            remaining = 3600 - elapsed
            m, s = divmod(remaining, 60)
            await message.reply(f"⏳ The cops are still looking for you! Wait <b>{m}m {s}s</b> before robbing again.", parse_mode="HTML")
            return

    # Get users
    robber = await get_or_create_user(db, user_id, message.from_user.username, message.from_user.first_name)
    target = await db.get(User, target_id)

    if not target:
        await message.reply(f"{get_emoji('warning')} That user isn't registered in the database.")
        return

    if robber.coins < 100:
        await message.reply(f"{get_emoji('error')} You need at least 100 coins to pay the fine if you get caught!")
        return

    if target.coins < 100:
        await message.reply(f"{get_emoji('error')} That user is too poor to rob. They need at least 100 coins!")
        return

    # Update cooldown
    if not limit:
        limit = UserDailyLimit(user_id=user_id, last_rob_at=now_ts, rob_count=1)
        db.add(limit)
    else:
        limit.last_rob_at = now_ts
        limit.rob_count += 1

    # Execute rob logic
    success = random.random() < 0.50 # 50% chance
    if success:
        # Steal 15% to 35%, max 5000
        percent = random.uniform(0.15, 0.35)
        steal_amount = int(target.coins * percent)
        if steal_amount > 5000:
            steal_amount = 5000

        target.coins -= steal_amount
        robber.coins += steal_amount
        await db.commit()
        await message.reply(f"🥷 <b>HEIST SUCCESSFUL!</b>\n\nYou sneaked in and stole <b>{steal_amount}</b> coins from {escape_html(target_name)}!", parse_mode="HTML")
    else:
        # Fine 10%, max 5000
        fine_amount = int(robber.coins * 0.10)
        if fine_amount > 5000:
            fine_amount = 5000
        
        robber.coins -= fine_amount
        await db.commit()
        await message.reply(f"🚨 <b>BUSTED!</b>\n\nYou got caught trying to rob {escape_html(target_name)}!\nYou paid a fine of <b>{fine_amount}</b> coins to the cops.", parse_mode="HTML")
