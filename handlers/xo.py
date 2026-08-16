from utils.emojis import get_emoji
import random
import asyncio
import time
from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import User
from utils.formatters import format_blockquote, escape_html, get_rarity_emoji
from utils.settings import get_cover_media
from handlers.start import get_or_create_user

router = Router()

# In-memory storage for active Tic-Tac-Toe games
active_xo_games = {}

# Uptime tracker
from handlers.start import START_TIME

# 1. Game State Helpers

def check_winner(board: list) -> Optional[str]:
    # 3x3 win states (indices)
    win_states = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8], # rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8], # cols
        [0, 4, 8], [2, 4, 6]             # diagonals
    ]
    for win in win_states:
        if board[win[0]] == board[win[1]] == board[win[2]] and board[win[0]] != "":
            return board[win[0]]
    if "" not in board:
        return "draw"
    return None

def get_smart_move(board: list) -> int:
    empty_cells = [i for i, cell in enumerate(board) if cell == ""]
    if not empty_cells:
        return 0

    win_states = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6]
    ]

    # 1. Can AI ("O") win in one move?
    for win in win_states:
        vals = [board[idx] for idx in win]
        if vals.count("O") == 2 and vals.count("") == 1:
            for idx in win:
                if board[idx] == "":
                    return idx

    # 2. Can Player ("X") win? Block them!
    for win in win_states:
        vals = [board[idx] for idx in win]
        if vals.count("X") == 2 and vals.count("") == 1:
            for idx in win:
                if board[idx] == "":
                    return idx

    # 3. Take center if free, else random
    if 4 in empty_cells:
        return 4
    return random.choice(empty_cells)

def minimax(board: list, depth: int, is_maximizing: bool) -> int:
    winner = check_winner(board)
    if winner == "O":
        return 10 - depth
    if winner == "X":
        return depth - 10
    if winner == "draw":
        return 0

    if is_maximizing:
        best_score = -float("inf")
        for i in range(9):
            if board[i] == "":
                board[i] = "O"
                score = minimax(board, depth + 1, False)
                board[i] = ""
                best_score = max(score, best_score)
        return best_score
    else:
        best_score = float("inf")
        for i in range(9):
            if board[i] == "":
                board[i] = "X"
                score = minimax(board, depth + 1, True)
                board[i] = ""
                best_score = min(score, best_score)
        return best_score

def get_minimax_move(board: list) -> int:
    best_score = -float("inf")
    best_move = -1
    for i in range(9):
        if board[i] == "":
            board[i] = "O"
            score = minimax(board, 0, False)
            board[i] = ""
            if score > best_score:
                best_score = score
                best_move = i
    if best_move != -1:
        return best_move
    return random.choice([i for i, cell in enumerate(board) if cell == ""])

def get_ai_move(board: list, difficulty: str, is_owner: bool) -> int:
    empty_cells = [i for i, cell in enumerate(board) if cell == f""]
    if not empty_cells:
        return 0

    if difficulty == "easy":
        # 50% random, 50% smart
        if random.random() < 0.5:
            return random.choice(empty_cells)
        return get_smart_move(board)

    elif difficulty == "medium":
        # 80% Minimax, 20% random
        if random.random() < 0.2:
            return random.choice(empty_cells)
        return get_minimax_move(board)

    else:  # hard
        # Bot Owner Secret Advantage: play suboptimally
        if is_owner:
            return random.choice(empty_cells)
        return get_minimax_move(board)

def build_xo_board(game_id: str, board: list, is_game_over: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(9):
        cell_val = board[i]
        text = "{get_emoji('error')}" if cell_val == "X" else ("🔵" if cell_val == "O" else "⬜")
        cb_data = "xo_noop" if (is_game_over or cell_val != "") else f"xo_move_{game_id}_{i}"
        builder.add(InlineKeyboardButton(text=text, callback_data=cb_data))
    builder.adjust(3, 3, 3)
    return builder.as_markup()

# 2. Command /xo /tictactoe

@router.message(Command("xo", "tictactoe"))
async def cmd_xo(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    user_name = escape_html(message.from_user.first_name)
    cover_media = get_cover_media("xo")
    
    parts = message.text.strip().split()
    wager = 0
    target_username = None
    force_ai = False

    # Parse arguments: /xo <amount> [@username or solo]
    for p in parts[1:]:
        if p.isdigit():
            wager = int(p)
        elif p.startswith("@"):
            target_username = p.replace("@", f"").strip()
        elif p.lower() in ["solo", "ai", "bot"]:
            force_ai = True

    is_group = message.chat.type in ["group", "supergroup"]
    target_user = None

    has_target = (message.reply_to_message is not None) or (target_username is not None)

    if is_group and has_target and not force_ai:
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
        elif target_username:
            stmt = select(User).where(User.username.ilike(target_username))
            res = await db.execute(stmt)
            target_db_user = res.scalar_one_or_none()
            if target_db_user:
                target_user = target_db_user
            else:
                await message.reply(f"{get_emoji('warning')} Could not find user @{target_username} in database!")
                return

        challenger = await get_or_create_user(db, user_id, message.from_user.username, message.from_user.first_name)
        if wager > 0 and challenger.coins < wager:
            await message.reply(f"{get_emoji('error')} You do not have enough coins! Balance: {challenger.coins:,} coins.")
            return

        if target_user:
            target_id = target_user.user_id if hasattr(target_user, "user_id") else target_user.id
            target_fname = target_user.first_name

            if target_id == user_id:
                await message.reply("{get_emoji('warning')} You cannot challenge yourself!")
                return
            if getattr(target_user, "is_bot", False) or target_id == message.bot.id:
                await message.reply("{get_emoji('warning')} You cannot challenge a bot!")
                return

            game_id = f"xo_pvp_{message.chat.id}_{message.message_id}"
            active_xo_games[game_id] = {
                "p1_id": user_id,
                "p1_name": user_name,
                "p2_id": target_id,
                "p2_name": escape_html(target_fname),
                "turn": "X",
                "board": [""] * 9,
                "mode": "pvp",
                "wager": wager,
                "status": "pending",
                "chat_id": message.chat.id
            }
            
            caption = (
                "⚔️ <b>TIC-TAC-TOE WAGER CHALLENGE!</b> ⚔️\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                + format_blockquote(
                    f"{get_emoji('user')} Challenger: <b>{user_name}</b>\n"
                    f"{get_emoji('target')} Opponent: <b>{escape_html(target_fname)}</b>\n"
                    f"{get_emoji('coin')} Wager: <b>{wager:,} Coins</b> (Pot: {2*wager:,} Coins)\n\n"
                    f"{get_emoji('pointer')} Challenge expires in 60 seconds!"
                )
            )

            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text=f"{get_emoji('success')} Accept", callback_data=f"xo_accept_{game_id}"),
                InlineKeyboardButton(text=f"{get_emoji('error')} Decline", callback_data=f"xo_decline_{game_id}")
            )
        
            sent_msg = None
            try:
                sent_msg = await message.reply_photo(cover_media, caption=caption, parse_mode="HTML", reply_markup=builder.as_markup())
            except Exception:
                try:
                    sent_msg = await message.reply_video(cover_media, caption=caption, parse_mode="HTML", reply_markup=builder.as_markup())
                except Exception:
                    sent_msg = await message.reply(caption, parse_mode="HTML", reply_markup=builder.as_markup())
            
            if sent_msg:
                active_xo_games[game_id]["invite_message_id"] = sent_msg.message_id
                asyncio.create_task(cleanup_invite_task(message.bot, message.chat.id, game_id, 60))
            return

    # Solo AI Mode
    game_id = f"xo_ai_{message.chat.id}_{user_id}"
    if game_id in active_xo_games:
        await message.reply(f"{get_emoji('warning')} You already have an active game in this chat!")
        return

    caption = (
        f"{get_emoji('error')}{get_emoji('circle')} <b>TIC-TAC-TOE VS BOT AI</b> {get_emoji('error')}{get_emoji('circle')}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        + format_blockquote(
            "Select your game difficulty below:\n\n"
            "🟢 Easy: +150 Coins on Win (50% Smart AI)\n"
            "🟡 Medium: +1,500 Coins on Win (80% Minimax AI)\n"
            "🔴 Hard: +20,000,000 Coins on Win (100% Minimax AI)"
        )
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🟢 Easy (+150)", callback_data="xo_ai_difficulty_easy"),
        InlineKeyboardButton(text="🟡 Medium (+1.5k)", callback_data="xo_ai_difficulty_medium")
    )
    builder.row(
        InlineKeyboardButton(text="🔴 Hard (+20M 💀)", callback_data="xo_ai_difficulty_hard")
    )
    if is_group:
        builder.row(InlineKeyboardButton(text="🗑️ Close", callback_data="close_menu"))
    else:
        builder.row(InlineKeyboardButton(text=f"{get_emoji('back')} Back", callback_data="dm_home"))

    try:
        await message.reply_photo(cover_media, caption=caption, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        try:
            await message.reply_video(cover_media, caption=caption, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            await message.reply(caption, parse_mode="HTML", reply_markup=builder.as_markup())

# 3. Callbacks

async def cleanup_invite_task(bot, chat_id: int, game_id: str, delay: int):
    await asyncio.sleep(delay)
    if game_id in active_xo_games:
        game = active_xo_games[game_id]
        if game.get("status") == "pending":
            del active_xo_games[game_id]
            try:
                await bot.delete_message(chat_id=chat_id, message_id=game["invite_message_id"])
            except Exception:
                pass

@router.callback_query(F.data.startswith("xo_ai_difficulty_"))
async def cb_xo_ai_difficulty(callback: CallbackQuery, db: AsyncSession):
    difficulty = callback.data.replace("xo_ai_difficulty_", "")
    user_id = callback.from_user.id
    user_name = escape_html(callback.from_user.first_name)

    game_id = f"xo_ai_{callback.message.chat.id}_{user_id}"
    active_xo_games[game_id] = {
        "p1_id": user_id,
        "p1_name": user_name,
        "mode": "ai",
        "difficulty": difficulty,
        "board": [""] * 9,
        "status": "active"
    }

    rewards = {"easy": 150, "medium": 1500, "hard": 20000000}
    reward = rewards.get(difficulty, 150)

    caption = (
        f"{get_emoji('error')}{get_emoji('circle')} <b>TIC-TAC-TOE VS BOT AI</b> {get_emoji('error')}{get_emoji('circle')}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        + format_blockquote(
            f"{get_emoji('user')} Player: <b>{user_name}</b> ({get_emoji('error')})\n"
            f"🤖 Bot AI: ({get_emoji('circle')})\n"
            f"🟢 Difficulty: <b>{difficulty.upper()}</b>\n"
            f"{get_emoji('coin')} Win Reward: <b>+{reward:,} coins</b>\n\n"
            f"{get_emoji('pointer')} Turn: <b>{user_name}</b> ({get_emoji('error')})"
        )
    )
    markup = build_xo_board(game_id, active_xo_games[game_id]["board"])
    
    if callback.message.photo or callback.message.video:
        try:
            await callback.message.edit_caption(caption=caption, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
    else:
        try:
            await callback.message.edit_text(text=caption, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
    await callback.answer()

@router.callback_query(F.data.startswith("xo_accept_"))
async def cb_xo_accept(callback: CallbackQuery, db: AsyncSession):
    game_id = callback.data.replace("xo_accept_", f"")
    if game_id not in active_xo_games:
        await callback.answer("{get_emoji('error')} Challenge expired or finished!", show_alert=True)
        return

    game = active_xo_games[game_id]
    user_id = callback.from_user.id

    if game["p2_id"] is not None and user_id != game["p2_id"]:
        await callback.answer("{get_emoji('error')} You are not the challenged player!", show_alert=True)
        return

    if game["p2_id"] is None:
        if user_id == game["p1_id"]:
            await callback.answer("{get_emoji('error')} You cannot accept your own challenge!", show_alert=True)
            return
        game["p2_id"] = user_id
        game["p2_name"] = escape_html(callback.from_user.first_name)

    if game["status"] != "pending":
        await callback.answer("{get_emoji('error')} This game already started!", show_alert=True)
        return

    wager = game["wager"]
    p1 = await get_or_create_user(db, game["p1_id"], "", game["p1_name"])
    p2 = await get_or_create_user(db, game["p2_id"], callback.from_user.username, callback.from_user.first_name)

    if p1.coins < wager:
        await callback.answer(f"{get_emoji('error')} Challenger no longer has enough coins!", show_alert=True)
        del active_xo_games[game_id]
        await callback.message.delete()
        return

    if p2.coins < wager:
        await callback.answer(f"{get_emoji('error')} You do not have enough coins! Need: {wager:,} coins.", show_alert=True)
        return

    p1.coins -= wager
    p2.coins -= wager
    game["status"] = "active"
    await db.commit()

    caption = (
        f"{get_emoji('error')}{get_emoji('circle')} <b>TIC-TAC-TOE WAGER DUEL!</b> {get_emoji('error')}{get_emoji('circle')}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        + format_blockquote(
            f"⚔️ <b>{game['p1_name']}</b> ({get_emoji('error')}) vs <b>{game['p2_name']}</b> ({get_emoji('circle')})\n"
            f"{get_emoji('coin')} Wager: <b>{wager:,} Coins</b> (Pot: {2*wager:,} Coins)\n\n"
            f"{get_emoji('pointer')} Turn: <b>{game['p1_name']}</b> ({get_emoji('error')})"
        )
    )
    markup = build_xo_board(game_id, game["board"])

    if callback.message.photo or callback.message.video:
        try:
            await callback.message.edit_caption(caption=caption, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
    else:
        try:
            await callback.message.edit_text(text=caption, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
    await callback.answer("Duel accepted! Make your move.")

@router.callback_query(F.data.startswith("xo_decline_"))
async def cb_xo_decline(callback: CallbackQuery):
    game_id = callback.data.replace("xo_decline_", f"")
    if game_id not in active_xo_games:
        await callback.answer("{get_emoji('error')} Challenge expired!", show_alert=True)
        return

    game = active_xo_games[game_id]
    user_id = callback.from_user.id

    if game["p2_id"] is None:
        if user_id != game["p1_id"]:
            await callback.answer("{get_emoji('error')} Only the challenger can cancel this challenge!", show_alert=True)
            return
    else:
        if user_id != game["p1_id"] and user_id != game["p2_id"]:
            await callback.answer("{get_emoji('error')} You are not part of this duel!", show_alert=True)
            return

    del active_xo_games[game_id]
    await callback.message.delete()
    await callback.answer("Challenge cancelled.")

@router.callback_query(F.data.startswith("xo_move_"))
async def cb_xo_move(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    cell_idx = int(parts[-1])
    game_id = "_".join(parts[2:-1])

    if game_id not in active_xo_games:
        await callback.answer("{get_emoji('error')} Game has expired or finished!", show_alert=True)
        return

    game = active_xo_games[game_id]
    user_id = callback.from_user.id
    board = game["board"]

    if game["mode"] == "ai":
        if user_id != game["p1_id"]:
            await callback.answer("{get_emoji('error')} This is not your AI game!", show_alert=True)
            return

        board[cell_idx] = "X"
        winner = check_winner(board)
        difficulty = game["difficulty"]
        rewards = {"easy": 150, "medium": 1500, "hard": 20000000}
        reward = rewards.get(difficulty, 150)

        if winner:
            del active_xo_games[game_id]
            markup = build_xo_board(game_id, board, is_game_over=True)
            if winner == "X":
                user = await get_or_create_user(db, user_id, callback.from_user.username, callback.from_user.first_name)
                user.coins += reward
                await db.commit()
                text = f"{get_emoji('party')} <b>YOU WON VS BOT AI ({difficulty.upper()})!</b>\n+{reward:,} Coins added!"
            else:
                text = "🤝 <b>IT'S A DRAW!</b> Good game!"
            
            card = "{get_emoji('error')}{get_emoji('circle')} <b>TIC-TAC-TOE GAME OVER</b>\n" + format_blockquote(text)
            if callback.message.photo or callback.message.video:
                await callback.message.edit_caption(caption=card, reply_markup=markup, parse_mode="HTML")
            else:
                await callback.message.edit_text(text=card, reply_markup=markup, parse_mode="HTML")
            return

        # AI Move
        is_owner = (config.ADMIN_IDS and user_id == config.ADMIN_IDS[0])
        ai_move = get_ai_move(board, difficulty, is_owner)
        board[ai_move] = "O"
        winner = check_winner(board)

        if winner:
            del active_xo_games[game_id]
            markup = build_xo_board(game_id, board, is_game_over=True)
            if winner == "O":
                text = f"💀 <b>BOT AI WON ({difficulty.upper()})!</b> Better luck next time!"
            else:
                text = "🤝 <b>IT'S A DRAW!</b> Good game!"
            
            card = "{get_emoji('error')}{get_emoji('circle')} <b>TIC-TAC-TOE GAME OVER</b>\n" + format_blockquote(text)
            if callback.message.photo or callback.message.video:
                await callback.message.edit_caption(caption=card, reply_markup=markup, parse_mode="HTML")
            else:
                await callback.message.edit_text(text=card, reply_markup=markup, parse_mode="HTML")
            return

        markup = build_xo_board(game_id, board)
        card = (
            "{get_emoji('error')}{get_emoji('circle')} <b>TIC-TAC-TOE VS BOT AI</b> {get_emoji('error')}{get_emoji('circle')}\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            + format_blockquote(
                f"{get_emoji('user')} Player: <b>{game['p1_name']}</b> ({get_emoji('error')})\n"
                f"🤖 Bot AI: ({get_emoji('circle')})\n"
                f"🟢 Difficulty: <b>{difficulty.upper()}</b>\n"
                f"{get_emoji('coin')} Win Reward: <b>+{reward:,} coins</b>\n\n"
                f"{get_emoji('pointer')} Turn: <b>{game['p1_name']}</b> ({get_emoji('error')})"
            )
        )
        if callback.message.photo or callback.message.video:
            await callback.message.edit_caption(caption=card, reply_markup=markup, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=card, reply_markup=markup, parse_mode="HTML")

    elif game["mode"] == "pvp":
        current_turn_id = game["p1_id"] if game["turn"] == "X" else game["p2_id"]
        if user_id != current_turn_id:
            await callback.answer("{get_emoji('error')} It is not your turn!", show_alert=True)
            return

        board[cell_idx] = game["turn"]
        winner = check_winner(board)
        wager = game["wager"]

        if winner:
            del active_xo_games[game_id]
            markup = build_xo_board(game_id, board, is_game_over=True)
            if winner == "draw":
                if wager > 0:
                    p1 = await get_or_create_user(db, game["p1_id"], "", game["p1_name"])
                    p2 = await get_or_create_user(db, game["p2_id"], "", game["p2_name"])
                    p1.coins += wager
                    p2.coins += wager
                    await db.commit()
                    text = f"🤝 <b>GAME DRAW!</b> Both players refunded {wager:,} coins."
                else:
                    text = "🤝 <b>GAME DRAW!</b> Casual match draw."
            else:
                winner_name = game["p1_name"] if winner == "X" else game["p2_name"]
                winner_user_id = game["p1_id"] if winner == "X" else game["p2_id"]
                winner_user = await get_or_create_user(db, winner_user_id, "", winner_name)

                # Victory Settlement with 5% tax
                if wager > 0:
                    total_pot = 2 * wager
                    tax = int(total_pot * 0.05)
                    reward = total_pot - tax
                    winner_user.coins += reward
                    await db.commit()
                    text = f"{get_emoji('crown')} <b>{winner_name} WON THE XO DUEL!</b>\nClaims <b>{reward:,} coins</b> (Pot: {total_pot:,} - 5% tax)!"
                else:
                    winner_user.coins += 231
                    await db.commit()
                    text = f"{get_emoji('crown')} <b>{winner_name} WON THE XO DUEL!</b>\nClaims +231 casual win coins!"

            card = f"{get_emoji('error')}{get_emoji('circle')} <b>TIC-TAC-TOE DUEL RESULT</b>\n" + format_blockquote(text)
            if callback.message.photo or callback.message.video:
                await callback.message.edit_caption(caption=card, reply_markup=markup, parse_mode="HTML")
            else:
                await callback.message.edit_text(text=card, reply_markup=markup, parse_mode="HTML")
            return

        game["turn"] = "O" if game["turn"] == "X" else "X"
        next_turn_name = game["p1_name"] if game["turn"] == "X" else game["p2_name"]
        markup = build_xo_board(game_id, board)
        wager_text = f"{get_emoji('coin')} Wager: <b>{wager:,} Coins</b> (Pot: {2*wager:,} Coins)" if wager > 0 else "Casual Mode"
        card = (
            f"{get_emoji('error')}{get_emoji('circle')} <b>TIC-TAC-TOE DUEL!</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            + format_blockquote(
                f"⚔️ <b>{game['p1_name']}</b> ({get_emoji('error')}) vs <b>{game['p2_name']}</b> ({get_emoji('circle')})\n"
                f"🎮 Mode: {wager_text}\n\n"
                f"{get_emoji('pointer')} Next Turn: <b>{next_turn_name}</b> ({game['turn']})"
            )
        )
        if callback.message.photo or callback.message.video:
            await callback.message.edit_caption(caption=card, reply_markup=markup, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=card, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data == "xo_noop")
async def cb_xo_noop(callback: CallbackQuery):
    await callback.answer()
