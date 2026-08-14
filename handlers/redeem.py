from utils.emojis import get_emoji
import random
import string
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import User, Character, UserCharacter, RedeemCode, RedeemUsage
from utils.formatters import format_blockquote, get_rarity_emoji, escape_html
from handlers.start import get_or_create_user
from utils.settings import get_cover_media

router = Router()
logger = logging.getLogger(__name__)

def generate_random_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))

@router.message(Command("gen"))
async def cmd_gen(message: Message, db: AsyncSession):
    if not message.from_user or message.from_user.id not in config.ADMIN_IDS:
        await message.reply(f"{get_emoji('no_entry')} Only bot owners can generate redeem codes!")
        return

    parts = message.text.strip().split()
    if len(parts) < 3:
        card = (
            "⏳ <b>Generate Redeem Code Console</b>\n\n"
            + format_blockquote(
                f"{get_emoji('energy')} <b>Usage Formats:</b>\n"
                "• <b>Character:</b> <code>/gen &lt;character_id&gt; &lt;limit&gt;</code>\n"
                "• <b>Coins:</b> <code>/gen coins &lt;amount&gt; &lt;limit&gt;</code>\n\n"
                "<b>Examples:</b>\n"
                "• <code>/gen 1 5</code> (Character #1 redeemable 5 times)\n"
                "• <code>/gen coins 50000 10</code> (50k coins redeemable 10 times)"
            )
        )
        await message.reply(card, parse_mode="HTML")
        return

    # Check if coin reward
    if parts[1].lower() == "coins":
        if len(parts) < 4:
            await message.reply(f"{get_emoji('error')} Usage: <code>/gen coins &lt;amount&gt; &lt;limit&gt;</code>", parse_mode="HTML")
            return
        amount_str, limit_str = parts[2], parts[3]
        if not amount_str.isdigit() or not limit_str.isdigit():
            await message.reply(f"{get_emoji('error')} Amount and Limit must be positive numbers!", parse_mode="HTML")
            return
        amount = int(amount_str)
        limit = int(limit_str)
        
        code_str = generate_random_code()
        new_code = RedeemCode(
            code=code_str,
            reward_type="coins",
            reward_amount=amount,
            max_uses=limit,
            uses_count=0
        )
        db.add(new_code)
        await db.commit()

        card = (
            f"{get_emoji('party')} <b>Redeem Code Created!</b>\n"
            + format_blockquote(
                f"{get_emoji('gift')} <b>Reward:</b> {get_emoji('coin')} {amount:,} Coins\n"
                f"🔢 <b>Limit:</b> {limit}\n"
                f"🔐 <b>Code:</b> <code>{code_str}</code>"
            )
        )
        cover = get_cover_media("start")
        try:
            await message.reply_photo(cover, caption=card, parse_mode="HTML")
        except Exception:
            await message.reply(card, parse_mode="HTML")
        return

    # Else fit's character reward
    char_id_str, limit_str = parts[1], parts[2]
    if not char_id_str.isdigit() or not limit_str.isdigit():
        await message.reply("{get_emoji('ferror')} Character ID and Limit must be positive numbers!", parse_mode="HTML")
        return
    char_id = int(char_id_str)
    limit = int(limit_str)

    stmt = select(Character).where(Character.id == char_id)
    res = await db.execute(stmt)
    character = res.scalar_one_or_none()
    if not character:
        await message.reply(f"{get_emoji('ferror')} Character ID <b>#{char_id}</b> not found in database!", parse_mode="HTML")
        return

    code_str = generate_random_code()
    new_code = RedeemCode(
        code=code_str,
        reward_type="character",
        reward_id=character.id,
        max_uses=limit,
        uses_count=0
    )
    db.add(new_code)
    await db.commit()

    r_emoji = get_rarity_emoji(character.rarity)
    card = (
        "{get_emoji('fparty')} <b>Redeem Code Created!</b>\n"
        + format_blockquote(
            f"{get_emoji('gift')} <b>Character:</b> {escape_html(character.name)}\n"
            f"{get_emoji('fsparkle')} <b>Anime:</b> {escape_html(character.anime)}\n"
            f"{r_emoji} <b>Rarity:</b> {r_emoji} {character.rarity}\n"
            f"🔢 <b>Limit:</b> {limit}\n"
            f"🔐 <b>Code:</b> <code>{code_str}</code>"
        )
    )
    photo = character.image_url if character.image_url else get_cover_media("start")
    try:
        await message.reply_photo(photo, caption=card, parse_mode="HTML")
    except Exception:
        try:
            await message.reply_video(photo, caption=card, parse_mode="HTML")
        except Exception:
            try:
                await message.reply_animation(photo, caption=card, parse_mode="HTML")
            except Exception:
                await message.reply(card, parse_mode="HTML")

@router.message(Command("redeem"))
async def cmd_redeem(message: Message, db: AsyncSession):
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.reply("{get_emoji('ferror')} Usage: <code>/redeem &lt;code&gt;</code>", parse_mode="HTML")
        return

    code_str = parts[1].strip().upper()
    user_id = message.from_user.id

    # Fetch redeem code
    stmt = select(RedeemCode).where(RedeemCode.code == code_str)
    res = await db.execute(stmt)
    redeem_code = res.scalar_one_or_none()

    if not redeem_code:
        await message.reply("{get_emoji('ferror')} Invalid or expired redeem code!", parse_mode="HTML")
        return

    if redeem_code.uses_count >= redeem_code.max_uses:
        await message.reply("{get_emoji('ferror')} This redeem code has already expired!", parse_mode="HTML")
        return

    # Check if user already claimed
    usage_stmt = select(RedeemUsage).where(RedeemUsage.user_id == user_id, RedeemUsage.code == code_str)
    usage_res = await db.execute(usage_stmt)
    already_used = usage_res.scalar_one_or_none()

    if already_used:
        await message.reply("{get_emoji('ferror')} You have already claimed this redeem code!", parse_mode="HTML")
        return

    # Claim logic
    user = await get_or_create_user(db, user_id, message.from_user.username, message.from_user.first_name)

    if redeem_code.reward_type == "coins":
        amount = redeem_code.reward_amount
        user.coins += amount
        redeem_code.uses_count += 1
        
        usage = RedeemUsage(user_id=user_id, code=code_str)
        db.add(usage)
        await db.commit()

        success_card = (
            "{get_emoji('fparty')} <b>REDEEM SUCCESSFUL!</b> {get_emoji('fparty')}\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            + format_blockquote(
                f"{get_emoji('fuser')} Trainer: <b>{escape_html(user.first_name)}</b>\n"
                f"🎫 Code: <code>{code_str}</code>\n"
                f"{get_emoji('gift')} Reward: {get_emoji('fcoin')} <b>{amount:,} Coins</b>\n"
                f"{get_emoji('fcoin')} New Balance: <code>{user.coins:,} Coins</code>"
            )
        )
        cover = get_cover_media("start")
        try:
            await message.reply_photo(cover, caption=success_card, parse_mode="HTML")
        except Exception:
            try:
                await message.reply_video(cover, caption=success_card, parse_mode="HTML")
            except Exception:
                try:
                    await message.reply_animation(cover, caption=success_card, parse_mode="HTML")
                except Exception:
                    await message.reply(success_card, parse_mode="HTML")
        return

    elif redeem_code.reward_type == "character":
        char_stmt = select(Character).where(Character.id == redeem_code.reward_id)
        char_res = await db.execute(char_stmt)
        character = char_res.scalar_one_or_none()
        
        if not character:
            await message.reply("{get_emoji('ferror')} Failed to claim character: character no longer exists in database.", parse_mode="HTML")
            return

        user.total_catches += 1
        user_char = UserCharacter(user_id=user_id, character_id=character.id, nickname=character.name)
        db.add(user_char)
        
        redeem_code.uses_count += 1
        usage = RedeemUsage(user_id=user_id, code=code_str)
        db.add(usage)
        await db.commit()

        r_emoji = get_rarity_emoji(character.rarity)
        success_card = (
            "{get_emoji('fparty')} <b>REDEEM SUCCESSFUL!</b> {get_emoji('fparty')}\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            + format_blockquote(
                f"{get_emoji('fuser')} Trainer: <b>{escape_html(user.first_name)}</b>\n"
                f"🎫 Code: <code>{code_str}</code>\n"
                f"{get_emoji('gift')} Reward: {r_emoji} <b>{escape_html(character.name)}</b> [{escape_html(character.anime)}]\n"
                f"🎫 <b>Character ID:</b> <code>#{character.id}</code>"
            )
        )
        photo = character.image_url if character.image_url else get_cover_media("start")
        try:
            await message.reply_photo(photo, caption=success_card, parse_mode="HTML")
        except Exception:
            try:
                await message.reply_video(photo, caption=success_card, parse_mode="HTML")
            except Exception:
                try:
                    await message.reply_animation(photo, caption=success_card, parse_mode="HTML")
                except Exception:
                    await message.reply(success_card, parse_mode="HTML")
        return
