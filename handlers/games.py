import random
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import User, ActiveGame
from utils.formatters import format_blockquote, escape_html
from keyboards.inline import get_games_keyboard, get_back_to_hub_keyboard
from handlers.start import get_or_create_user

router = Router()

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
    user_id = event.from_user.id if isinstance(event, Message) else event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    
    user = await get_or_create_user(db, user_id, event.from_user.username, event.from_user.first_name)
    won_coins = random.choice(config.SPIN_REWARDS)
    user.coins += won_coins
    await db.commit()

    text = (
        "🎰 <b>LUCKY WHEEL SPIN!</b> 🎰\n\n"
        + format_blockquote(
            f"🌀 <i>*The wheel spins rapidly...*</i>\n\n"
            f"🎉 <b>Land:</b> +{won_coins} Coins!\n"
            f"💰 <b>Total Balance:</b> {user.coins:,} Coins"
        )
    )
    if isinstance(event, CallbackQuery):
        await message_obj.edit_text(text, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
        await event.answer()
    else:
        await message_obj.answer(text, parse_mode="HTML")

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
            f"🎉 <b>Reward:</b> +{reward} Coins!\n"
            f"🎯 <b>Keep your streak going tomorrow!</b>\n"
            f"💰 <b>Total Balance:</b> {user.coins:,} Coins"
        )
    )
    await message.answer(text, parse_mode="HTML")

@router.callback_query(F.data == "game_coinflip")
@router.message(Command("coinflip"))
async def cmd_coinflip(event, db: AsyncSession):
    user_id = event.from_user.id if isinstance(event, Message) else event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    
    user = await get_or_create_user(db, user_id, event.from_user.username, event.from_user.first_name)
    bet = 100
    if user.coins < bet:
        text = "❌ You need at least 100 coins to flip a coin!"
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await message_obj.answer(text)
        return

    win = random.choice([True, False])
    outcome = "Heads" if win else "Tails"
    if win:
        user.coins += bet
        res_text = f"🎉 <b>WIN!</b> It landed on {outcome}! You won +{bet} coins!"
    else:
        user.coins -= bet
        res_text = f"💀 <b>LOSS!</b> It landed on {outcome}! You lost {bet} coins."

    await db.commit()
    card = f"🪙 <b>COIN FLIP CHALLENGE</b>\n\n" + format_blockquote(f"{res_text}\n💰 <b>Balance:</b> {user.coins:,} Coins")
    if isinstance(event, CallbackQuery):
        await message_obj.edit_text(card, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
        await event.answer()
    else:
        await message_obj.answer(card, parse_mode="HTML")

@router.callback_query(F.data == "game_dice")
@router.message(Command("dice"))
async def cmd_dice(event, db: AsyncSession):
    user_id = event.from_user.id if isinstance(event, Message) else event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    
    user = await get_or_create_user(db, user_id, event.from_user.username, event.from_user.first_name)
    roll = random.randint(1, 6)
    if roll >= 4:
        reward = 150
        user.coins += reward
        res = f"🎲 You rolled a <b>{roll}</b>! 🎉 <b>WIN!</b> +{reward} Coins!"
    else:
        loss = 50
        user.coins -= loss
        res = f"🎲 You rolled a <b>{roll}</b>! 💀 <b>LOSS!</b> -{loss} Coins."

    await db.commit()
    card = "🎲 <b>DICE ROLL BET</b>\n\n" + format_blockquote(f"{res}\n💰 <b>Balance:</b> {user.coins:,} Coins")
    if isinstance(event, CallbackQuery):
        await message_obj.edit_text(card, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
        await event.answer()
    else:
        await message_obj.answer(card, parse_mode="HTML")

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
    builder.row(InlineKeyboardButton(text="🔙 Back to Games", callback_data="dm_games"))
    
    text = (
        "🧠 <b>ANIME TRIVIA CHALLENGE!</b>\n\n"
        + format_blockquote(
            f"❓ <b>Question:</b>\n{question_data['q']}\n\n"
            f"💰 <b>Reward:</b> +{config.TRIVIA_REWARD} Coins!"
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
        await callback.answer("❌ Invalid game session.", show_alert=True)
        return
        
    _, play_id_str, q_idx_str, opt_idx_str = parts
    play_id = int(play_id_str)
    q_idx = int(q_idx_str)
    opt_idx = int(opt_idx_str)
    
    if callback.from_user.id != play_id:
        await callback.answer("❌ This trivia challenge is not yours! Start a new one with /trivia.", show_alert=True)
        return
        
    if q_idx >= len(TRIVIA_QUESTIONS):
        await callback.answer("❌ Question no longer exists.", show_alert=True)
        return
        
    question_data = TRIVIA_QUESTIONS[q_idx]
    user = await get_or_create_user(db, play_id, callback.from_user.username, callback.from_user.first_name)
    
    is_correct = opt_idx == question_data["ans"]
    chosen_opt = question_data["opts"][opt_idx]
    correct_opt = question_data["opts"][question_data["ans"]]
    
    if is_correct:
        reward = config.TRIVIA_REWARD
        user.coins += reward
        await db.commit()
        
        card = (
            "🧠 <b>ANIME TRIVIA CHALLENGE!</b>\n\n"
            + format_blockquote(
                f"❓ <b>Question:</b> {question_data['q']}\n\n"
                f"✅ <b>Your Answer:</b> {chosen_opt} (Correct!)\n"
                f"🎉 <b>Reward:</b> +{reward} Coins!\n"
                f"💰 <b>Balance:</b> {user.coins:,} Coins"
            )
        )
    else:
        card = (
            "🧠 <b>ANIME TRIVIA CHALLENGE!</b>\n\n"
            + format_blockquote(
                f"❓ <b>Question:</b> {question_data['q']}\n\n"
                f"❌ <b>Your Answer:</b> {chosen_opt} (Incorrect!)\n"
                f"💡 <b>Correct Answer:</b> {correct_opt}\n"
                f"💀 <b>Reward:</b> 0 Coins\n"
                f"💰 <b>Balance:</b> {user.coins:,} Coins"
            )
        )
        
    await callback.message.edit_text(card, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
    await callback.answer()
@router.callback_query(F.data == "game_mines")
@router.message(Command("mines"))
async def cmd_mines(event, db: AsyncSession):
    user_id = event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message

    # Delete any existing active mines game
    await db.execute(
        delete(ActiveGame).where(ActiveGame.user_id == user_id, ActiveGame.game_type == "mines")
    )

    # 3x3 grid, index 0 to 8
    # 2 hidden mines
    mine_indices = random.sample(range(9), 2)
    game_state = {
        "mines": mine_indices,
        "revealed": [],
        "reward": 0,
        "status": "playing"
    }

    new_game = ActiveGame(user_id=user_id, game_type="mines", data=json.dumps(game_state))
    db.add(new_game)
    await db.commit()

    kb = render_mines_keyboard(user_id, game_state)
    card = (
        "💣 <b>ANIME MINES ARENA</b> 💣\n\n"
        + format_blockquote(
            "Find the hidden diamonds 💎 and avoid the mines 💣!\n\n"
            "💰 <b>Current Cashout:</b> 0 Coins\n"
            "💎 <b>Diamonds Found:</b> 0 / 7"
        )
    )

    if isinstance(event, CallbackQuery):
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

    # 3x3 grid buttons
    buttons = []
    for idx in range(9):
        if status == "playing":
            if idx in revealed:
                buttons.append(InlineKeyboardButton(text="💎", callback_data="noop"))
            else:
                buttons.append(InlineKeyboardButton(text="⬜", callback_data=f"mines_click:{user_id}:{idx}"))
        else: # Game over (lost/won/cashed out)
            if idx in mines:
                buttons.append(InlineKeyboardButton(text="💣", callback_data="noop"))
            elif idx in revealed:
                buttons.append(InlineKeyboardButton(text="💎", callback_data="noop"))
            else:
                # show remaining diamonds
                buttons.append(InlineKeyboardButton(text="💎", callback_data="noop"))

    for i in range(0, 9, 3):
        builder.row(buttons[i], buttons[i+1], buttons[i+2])

    if status == "playing":
        current_reward = state["reward"]
        if current_reward > 0:
            builder.row(InlineKeyboardButton(
                text=f"💵 Cash Out (+{current_reward} Coins)",
                callback_data=f"mines_cashout:{user_id}"
            ))
    builder.row(InlineKeyboardButton(text="🔙 Back to Games", callback_data="dm_games"))
    return builder.as_markup()

@router.callback_query(F.data.startswith("mines_click:"))
async def handle_mines_click(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("❌ Invalid session.", show_alert=True)
        return

    _, play_id_str, idx_str = parts[0], parts[1], parts[2]
    play_id = int(play_id_str)
    idx = int(idx_str)

    if callback.from_user.id != play_id:
        await callback.answer("❌ This game is not yours! Start a new one with /mines.", show_alert=True)
        return

    stmt = select(ActiveGame).where(ActiveGame.user_id == play_id, ActiveGame.game_type == "mines")
    res = await db.execute(stmt)
    game = res.scalar_one_or_none()
    if not game:
        await callback.answer("❌ Game not found. Start a new one with /mines.", show_alert=True)
        return

    state = json.loads(game.data)
    if state["status"] != "playing":
        await callback.answer("❌ Game already finished.", show_alert=True)
        return

    # Process click
    mines = state["mines"]
    revealed = state["revealed"]

    if idx in revealed:
        await callback.answer()
        return

    user = await get_or_create_user(db, play_id, callback.from_user.username, callback.from_user.first_name)

    if idx in mines:
        # HIT MINE -> Lose game
        state["status"] = "lost"
        await db.delete(game)
        await db.commit()

        kb = render_mines_keyboard(play_id, state)
        card = (
            "💣 <b>ANIME MINES ARENA</b> 💣\n\n"
            + format_blockquote(
                "💥 <b>BOOM! You hit a mine!</b>\n"
                "You lost your accumulated coins!\n\n"
                f"💎 <b>Diamonds Found:</b> {len(revealed)} / 7\n"
                f"💀 <b>Reward:</b> 0 Coins\n"
                f"💰 <b>Balance:</b> {user.coins:,} Coins"
            )
        )
        await callback.message.edit_text(card, parse_mode="HTML", reply_markup=kb)
        await callback.answer("💥 BOOM! You lost!", show_alert=True)
    else:
        # HIT DIAMOND -> Keep playing or cashout
        revealed.append(idx)
        diamonds_found = len(revealed)
        
        # Reward increases per diamond found: e.g. 75 coins per diamond
        reward = diamonds_found * 75
        state["reward"] = reward

        if diamonds_found == 7:
            # Found all diamonds -> Perfect Win
            state["status"] = "won"
            user.coins += reward
            await db.delete(game)
            await db.commit()

            kb = render_mines_keyboard(play_id, state)
            card = (
                "💣 <b>ANIME MINES ARENA</b> 💣\n\n"
                + format_blockquote(
                    "🎉 <b>PERFECT WIN!</b>\n"
                    "You found all the diamonds safely!\n\n"
                    f"💎 <b>Diamonds Found:</b> 7 / 7\n"
                    f"🎉 <b>Reward:</b> +{reward} Coins!\n"
                    f"💰 <b>Balance:</b> {user.coins:,} Coins"
                )
            )
            await callback.message.edit_text(card, parse_mode="HTML", reply_markup=kb)
            await callback.answer("🎉 Perfect win!", show_alert=True)
        else:
            # Update state in DB
            game.data = json.dumps(state)
            await db.commit()

            kb = render_mines_keyboard(play_id, state)
            card = (
                "💣 <b>ANIME MINES ARENA</b> 💣\n\n"
                + format_blockquote(
                    "Find the hidden diamonds 💎 and avoid the mines 💣!\n\n"
                    f"💰 <b>Current Cashout:</b> {reward} Coins\n"
                    f"💎 <b>Diamonds Found:</b> {diamonds_found} / 7"
                )
            )
            await callback.message.edit_text(card, parse_mode="HTML", reply_markup=kb)
            await callback.answer("💎 Diamond found!")

@router.callback_query(F.data.startswith("mines_cashout:"))
async def handle_mines_cashout(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split(":")
    if len(parts) != 2:
        return

    play_id = int(parts[1])
    if callback.from_user.id != play_id:
        await callback.answer("❌ This game is not yours!", show_alert=True)
        return

    stmt = select(ActiveGame).where(ActiveGame.user_id == play_id, ActiveGame.game_type == "mines")
    res = await db.execute(stmt)
    game = res.scalar_one_or_none()
    if not game:
        await callback.answer("❌ Game already finished.", show_alert=True)
        return

    state = json.loads(game.data)
    reward = state["reward"]
    revealed = state["revealed"]

    user = await get_or_create_user(db, play_id, callback.from_user.username, callback.from_user.first_name)
    user.coins += reward
    state["status"] = "cashed_out"

    await db.delete(game)
    await db.commit()

    kb = render_mines_keyboard(play_id, state)
    card = (
        "💣 <b>ANIME MINES ARENA</b> 💣\n\n"
        + format_blockquote(
            "💵 <b>CASHOUT SUCCESSFUL!</b>\n"
            "You disarmed the field and kept your earnings!\n\n"
            f"💎 <b>Diamonds Found:</b> {len(revealed)} / 7\n"
            f"🎉 <b>Reward:</b> +{reward} Coins!\n"
            f"💰 <b>Balance:</b> {user.coins:,} Coins"
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
            f"🎉 <b>Reward:</b> +{reward} Coins!\n"
            f"💰 <b>Balance:</b> {user.coins:,} Coins"
        )
    )
    if isinstance(event, CallbackQuery):
        await message_obj.edit_text(card, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
        await event.answer()
    else:
        await message_obj.answer(card, parse_mode="HTML")
