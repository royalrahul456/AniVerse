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

@router.callback_query(F.data == "game_trivia")
@router.message(Command("trivia"))
async def cmd_trivia(event, db: AsyncSession):
    user_id = event.from_user.id if isinstance(event, Message) else event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    
    user = await get_or_create_user(db, user_id, event.from_user.username, event.from_user.first_name)
    reward = config.TRIVIA_REWARD
    user.coins += reward
    await db.commit()

    card = (
        "🧠 <b>ANIME TRIVIA CHALLENGE!</b>\n\n"
        + format_blockquote(
            f"❓ <b>Question:</b> Who is known as the Strongest Sorcerer in Jujutsu Kaisen?\n"
            f"✅ <b>Correct Answer:</b> Gojo Satoru\n"
            f"🎉 <b>Reward:</b> +{reward} Coins!\n"
            f"💰 <b>Balance:</b> {user.coins:,} Coins"
        )
    )
    if isinstance(event, CallbackQuery):
        await message_obj.edit_text(card, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
        await event.answer()
    else:
        await message_obj.answer(card, parse_mode="HTML")

@router.callback_query(F.data == "game_mines")
@router.message(Command("mines"))
async def cmd_mines(event, db: AsyncSession):
    user_id = event.from_user.id if isinstance(event, Message) else event.from_user.id
    message_obj = event if isinstance(event, Message) else event.message
    
    user = await get_or_create_user(db, user_id, event.from_user.username, event.from_user.first_name)
    reward = 200
    user.coins += reward
    await db.commit()

    card = (
        "💣 <b>ANIME MINES FIELD</b> 💣\n\n"
        + format_blockquote(
            "💎 💎 💎\n"
            "💎 💣 💎\n"
            "💎 💎 💎\n\n"
            f"🎉 You disarmed 3 mine fields safely! Won +{reward} Coins!\n"
            f"💰 <b>Balance:</b> {user.coins:,} Coins"
        )
    )
    if isinstance(event, CallbackQuery):
        await message_obj.edit_text(card, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
        await event.answer()
    else:
        await message_obj.answer(card, parse_mode="HTML")

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
