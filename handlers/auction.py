from utils.emojis import get_emoji
import datetime
import logging
import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, or_, desc
from database.models import User, Character, UserCharacter, Auction, Bid
from utils.formatters import format_blockquote, get_rarity_emoji, escape_html
from handlers.start import get_or_create_user
from utils.settings import get_cover_media
from handlers.admin import is_owner

router = Router()
logger = logging.getLogger(__name__)

async def build_active_auction_card(auction: Auction, db: AsyncSession) -> str:
    character = await db.get(Character, auction.character_id)
    seller = await db.get(User, auction.seller_id)
    
    leader_name = "No bids yet"
    if auction.highest_bidder_id:
        leader = await db.get(User, auction.highest_bidder_id)
        if leader:
            leader_name = escape_html(leader.first_name)

    time_left_str = "0m 0s"
    if auction.expires_at:
        now = datetime.datetime.utcnow()
        delta = auction.expires_at - now
        if delta.total_seconds() > 0:
            m = int(delta.total_seconds() // 60)
            s = int(delta.total_seconds() % 60)
            time_left_str = f"{m}m {s}s"

    r_emoji = get_rarity_emoji(character.rarity)
    
    # Fetch recent bids (last 3)
    bids_stmt = select(Bid).where(Bid.auction_id == auction.id).order_by(desc(Bid.amount)).limit(3)
    bids_res = await db.execute(bids_stmt)
    bids = bids_res.scalars().all()
    
    bids_text = "<i>No bids placed yet. Be the first!</i>"
    if bids:
        bids_lines = []
        for b in bids:
            bidder = await db.get(User, b.bidder_id)
            bname = escape_html(bidder.first_name) if bidder else "User"
            bids_lines.append(f"• {bname}: {b.amount:,} coins")
        bids_text = "\n".join(bids_lines)

    card = (
        "🔮 <b>ACTIVE AUCTION!</b>\n"
        "───────────────\n"
        + format_blockquote(
            f"{get_emoji('id')} <b>Auction ID:</b> #{auction.id}\n"
            f"📛 <b>Name:</b> {escape_html(character.name)}\n"
            f"{get_emoji('gem')} <b>Rarity:</b> {r_emoji} {character.rarity}\n"
            f"{get_emoji('coin')} <b>Starting:</b> {auction.starting_price:,}\n"
            f"{get_emoji('bomb')} <b>Current Bid:</b> {auction.current_bid:,}\n"
            f"{get_emoji('crown')} <b>Leader:</b> {leader_name}\n"
            f"👥 <b>Seller:</b> {escape_html(seller.first_name)}\n"
            f"⏳ <b>Time Left:</b> {time_left_str}"
        )
        + f"\n\n📝 <b>Recent Bids:</b>\n{bids_text}"
    )
    return card

def build_auction_keyboard(auction: Auction) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"+1,000 {get_emoji('coin')}", callback_data=f"bid_quick_{auction.id}_1000"),
        InlineKeyboardButton(text=f"+5,000 {get_emoji('coin')}", callback_data=f"bid_quick_{auction.id}_5000"),
        InlineKeyboardButton(text=f"+10,000 {get_emoji('coin')}", callback_data=f"bid_quick_{auction.id}_10000")
    )
    return builder.as_markup()

@router.message(Command("auction"))
async def cmd_auction(message: Message, db: AsyncSession):
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.reply(
            "🔮 <b>AniVerse Character Auction House</b>\n\n"
            + format_blockquote(
                "List your characters for global bidding!\n\n"
                f"{get_emoji('energy')} <b>Usage:</b> <code>/auction &lt;character_id_or_name&gt; &lt;starting_price&gt;</code>\n"
                "<b>Example:</b> <code>/auction 1 10000</code>"
            ),
            parse_mode="HTML"
        )
        return

    char_search = " ".join(parts[1:-1])
    price_str = parts[-1]

    if not price_str.isdigit():
        await message.reply(f"{get_emoji('error')} Starting price must be a positive number!", parse_mode="HTML")
        return
    starting_price = int(price_str)
    if starting_price < 100:
        await message.reply(f"{get_emoji('error')} Minimum starting price is 100 coins!", parse_mode="HTML")
        return

    user_id = message.from_user.id
    user = await get_or_create_user(db, user_id, message.from_user.username, message.from_user.first_name)

    # Check listing limit (only 1 active or queued auction per player)
    limit_stmt = select(Auction).where(Auction.seller_id == user_id, Auction.status.in_(["pending", "active"]))
    limit_res = await db.execute(limit_stmt)
    if limit_res.scalars().all():
        await message.reply(f"{get_emoji('error')} You can only have one active or queued auction at a time!", parse_mode="HTML")
        return

    # Find character in user harem
    char_id_val = int(char_search) if char_search.isdigit() else None
    
    # OWNER BYPASS: If the owner searches for a character, they can auction ANY character globally, even if they don't own it!
    owner_bypass = False
    if is_owner(message):
        if char_id_val is not None:
            stmt = select(Character).where(Character.id == char_id_val)
        else:
            stmt = select(Character).where(Character.name.ilike(f"%{char_search}%"))
        
        res = await db.execute(stmt)
        character = res.scalars().first()
        if character:
            owner_bypass = True
            # Create a synthetic UserCharacter for the auction referencing the bot
            bot_user = await get_or_create_user(db, message.bot.id, "AniVerse_Bot", "Auction House")
            user_char = UserCharacter(user_id=bot_user.user_id, character_id=character.id, nickname=character.name)
            db.add(user_char)
            await db.flush()

    if not owner_bypass:
        if char_id_val is not None:
            stmt = select(UserCharacter).join(Character).where(
                UserCharacter.user_id == user_id,
                Character.id == char_id_val
            )
        else:
            stmt = select(UserCharacter).join(Character).where(
                UserCharacter.user_id == user_id,
                Character.name.ilike(f"%{char_search}%")
            )
    
        res = await db.execute(stmt)
        user_char = res.scalars().first()
        if not user_char:
            await message.reply(f"{get_emoji('error')} You do not own any character matching '<b>{escape_html(char_search)}</b>' in your harem!", parse_mode="HTML")
            return
        character = await db.get(Character, user_char.character_id)

    # Check if there is already an active global auction
    active_stmt = select(Auction).where(Auction.status == "active")
    active_res = await db.execute(active_stmt)
    active_auction = active_res.scalar_one_or_none()

    # Determine status and times
    status = "pending"
    started_at = None
    expires_at = None

    if not active_auction:
        status = "active"
        started_at = datetime.datetime.utcnow()
        expires_at = started_at + datetime.timedelta(minutes=5)

    # Transfer UserCharacter to the bot account (Auction House) to hold it, preventing duplicates while avoiding Postgres ForeignKey integrity errors from deletion
    bot_user = await get_or_create_user(db, message.bot.id, "AniVerse_Bot", "Auction House")
    user_char.user_id = bot_user.user_id
    await db.flush()

    # Create Auction record
    auction = Auction(
        seller_id=user_id,
        character_id=character.id,
        user_character_id=user_char.id,
        starting_price=starting_price,
        current_bid=starting_price,
        status=status,
        started_at=started_at,
        expires_at=expires_at,
        chat_id=message.chat.id
    )
    db.add(auction)
    await db.commit()

    if status == "active":
        card = await build_active_auction_card(auction, db)
        kb = build_auction_keyboard(auction)
        photo = character.image_url if character.image_url else get_cover_media("start")
        sent_msg = None
        try:
            sent_msg = await message.reply_photo(photo, caption=card, reply_markup=kb, parse_mode="HTML")
        except Exception:
            try:
                sent_msg = await message.reply_video(photo, caption=card, reply_markup=kb, parse_mode="HTML")
            except Exception:
                try:
                    sent_msg = await message.reply_animation(photo, caption=card, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    try:
                        sent_msg = await message.reply(card, reply_markup=kb, parse_mode="HTML")
                    except Exception:
                        pass
        if sent_msg:
            auction.message_id = sent_msg.message_id
            await db.commit()
            try:
                await message.bot.pin_chat_message(chat_id=message.chat.id, message_id=sent_msg.message_id, disable_notification=True)
            except Exception:
                pass
    else:
        # Get queue position
        q_stmt = select(func.count(Auction.id)).where(Auction.status == "pending")
        q_pos = (await db.execute(q_stmt)).scalar() or 1
        
        card = (
            "🕒 <b>Added to Auction Queue!</b>\n"
            "───────────────\n"
            + format_blockquote(
                f"📛 Character: <b>{escape_html(character.name)}</b>\n"
                f"{get_emoji('coin')} Starting Price: <b>{starting_price:,} coins</b>\n"
                f"🔢 Queue Position: <b>#{q_pos}</b>"
            )
            + "\nIt will start automatically once active auctions ahead of it finish."
        )
        await message.reply(card, parse_mode="HTML")

@router.message(Command("bid"))
async def cmd_bid(message: Message, db: AsyncSession):
    parts = message.text.strip().split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.reply(f"{get_emoji('error')} Usage: <code>/bid &lt;auction_id&gt; &lt;amount&gt;</code>", parse_mode="HTML")
        return

    auction_id = int(parts[1])
    amount = int(parts[2])

    user_id = message.from_user.id
    user = await get_or_create_user(db, user_id, message.from_user.username, message.from_user.first_name)

    auction = await db.get(Auction, auction_id)
    if not auction or auction.status != "active":
        await message.reply(f"{get_emoji('error')} This auction is not active or does not exist!", parse_mode="HTML")
        return

    if auction.seller_id == user_id:
        await message.reply(f"{get_emoji('error')} You cannot bid on your own auction!", parse_mode="HTML")
        return

    # Check minimum bid rules
    min_bid = auction.starting_price
    if auction.highest_bidder_id:
        min_bid = auction.current_bid + 100

    if amount < min_bid:
        await message.reply(f"{get_emoji('error')} Minimum required bid is <b>{min_bid:,} coins</b>!", parse_mode="HTML")
        return

    if user.coins < amount:
        await message.reply(f"{get_emoji('error')} You do not have enough coins! Balance: {user.coins:,} coins.", parse_mode="HTML")
        return

    # Process bid
    # Refund previous highest bidder
    if auction.highest_bidder_id:
        prev_bidder = await db.get(User, auction.highest_bidder_id)
        if prev_bidder:
            prev_bidder.coins += auction.current_bid

    # Debit new highest bidder
    user.coins -= amount
    
    # Update auction
    auction.current_bid = amount
    auction.highest_bidder_id = user_id

    # Log bid
    bid_log = Bid(auction_id=auction.id, bidder_id=user_id, amount=amount)
    db.add(bid_log)
    await db.commit()

    await message.reply(f"{get_emoji('success')} Bid of <b>{amount:,} coins</b> placed successfully on Auction #{auction.id}!")

@router.message(Command("cancelauction"))
async def cmd_cancelauction(message: Message, db: AsyncSession):
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply(f"{get_emoji('error')} Usage: <code>/cancelauction &lt;auction_id&gt;</code>", parse_mode="HTML")
        return

    auction_id = int(parts[1])
    user_id = message.from_user.id

    auction = await db.get(Auction, auction_id)
    if not auction:
        await message.reply(f"{get_emoji('error')} Auction not found!", parse_mode="HTML")
        return

    if auction.seller_id != user_id:
        await message.reply(f"{get_emoji('error')} You can only cancel your own auctions!", parse_mode="HTML")
        return

    if auction.status not in ["pending", "active"]:
        await message.reply(f"{get_emoji('error')} This auction is already finished or cancelled!", parse_mode="HTML")
        return

    # Check if there are any bids (only if active)
    if auction.status == "active" and auction.highest_bidder_id is not None:
        await message.reply(f"{get_emoji('error')} You cannot cancel an active auction that already has bids!", parse_mode="HTML")
        return

    # Cancel auction
    auction.status = "cancelled"
    
    # Return character to seller
    # Return character to seller
    user_char = await db.get(UserCharacter, auction.user_character_id)
    if user_char:
        user_char.user_id = user_id
    else:
        character = await db.get(Character, auction.character_id)
        user_char = UserCharacter(
            user_id=user_id,
            character_id=character.id,
            nickname=character.name
        )
        db.add(user_char)
    await db.commit()

    await message.reply(f"{get_emoji('success')} Auction cancelled successfully! Your character has been returned to your harem.")

@router.message(Command("auctions", "auc"))
async def cmd_auctions(message: Message, db: AsyncSession):
    active_stmt = select(Auction).where(Auction.status == "active")
    active_res = await db.execute(active_stmt)
    auction = active_res.scalar_one_or_none()

    q_stmt = select(func.count(Auction.id)).where(Auction.status == "pending")
    queue_size = (await db.execute(q_stmt)).scalar() or 0

    if not auction:
        await message.reply(
            "🔮 <b>Active Auctions</b>\n━━━━━━━━━━━━━━━━━━━\n"
            + format_blockquote(
                f"{get_emoji('error')} There is no active auction globally right now.\n\n"
                f"🕒 <b>Queue Size:</b> {queue_size} pending listings."
            ),
            parse_mode="HTML"
        )
        return

    card = await build_active_auction_card(auction, db)
    kb = build_auction_keyboard(auction)
    
    character = await db.get(Character, auction.character_id)
    photo = character.image_url if character.image_url else get_cover_media("start")
    try:
        await message.reply_photo(photo, caption=card, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            await message.reply_video(photo, caption=card, reply_markup=kb, parse_mode="HTML")
        except Exception:
            try:
                await message.reply_animation(photo, caption=card, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.reply(card, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("bid_quick_"))
async def cb_bid_quick(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    auction_id = int(parts[2])
    increment = int(parts[3])
    user_id = callback.from_user.id

    auction = await db.get(Auction, auction_id)
    if not auction or auction.status != "active":
        await callback.answer(f"{get_emoji('error')} This auction is no longer active!", show_alert=True)
        return

    if auction.seller_id == user_id:
        await callback.answer(f"{get_emoji('error')} You cannot bid on your own auction!", show_alert=True)
        return

    # Calculate bid amount
    amount = auction.current_bid + increment
    if not auction.highest_bidder_id:
        amount = auction.starting_price + increment

    user = await get_or_create_user(db, user_id, callback.from_user.username, callback.from_user.first_name)
    if user.coins < amount:
        await callback.answer(f"{get_emoji('error')} Not enough coins! Balance: {user.coins:,}", show_alert=True)
        return

    # Refund previous highest bidder
    if auction.highest_bidder_id:
        prev_bidder = await db.get(User, auction.highest_bidder_id)
        if prev_bidder:
            prev_bidder.coins += auction.current_bid

    # Debit new highest bidder
    user.coins -= amount

    # Update auction
    auction.current_bid = amount
    auction.highest_bidder_id = user_id

    # Log bid
    bid_log = Bid(auction_id=auction.id, bidder_id=user_id, amount=amount)
    db.add(bid_log)
    await db.commit()

    await callback.answer(f"{get_emoji('party')} Bid of {amount:,} placed!", show_alert=False)
    
    # Update active auction card caption
    card = await build_active_auction_card(auction, db)
    kb = build_auction_keyboard(auction)
    try:
        await callback.message.edit_caption(caption=card, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

async def process_auctions_tick(bot):
    from database.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        # 1. Fetch active auction
        stmt = select(Auction).where(Auction.status == "active")
        res = await db.execute(stmt)
        active = res.scalar_one_or_none()
        
        now = datetime.datetime.utcnow()
        
        if active:
            # Check if expired
            if active.expires_at and active.expires_at <= now:
                character = await db.get(Character, active.character_id)
                seller = await db.get(User, active.seller_id)
                nickname = character.name
                
                # Check if someone bid
                if active.highest_bidder_id:
                    # Completed
                    active.status = "completed"
                    bidder = await db.get(User, active.highest_bidder_id)
                    
                    # Distribute character to bidder
                    user_char = await db.get(UserCharacter, active.user_character_id)
                    if user_char:
                        user_char.user_id = active.highest_bidder_id
                    else:
                        user_char = UserCharacter(user_id=active.highest_bidder_id, character_id=active.character_id, nickname=nickname)
                        db.add(user_char)
                    
                    # Pay seller (5% tax)
                    payout = int(active.current_bid * 0.95)
                    seller.coins += payout
                    await db.commit()
                    
                    # Notify
                    win_card = (
                        f"{get_emoji('party')} <b>Auction Won!</b> {get_emoji('party')}\n"
                        "───────────────\n"
                        + format_blockquote(
                            f"{get_emoji('crown')} <b>{escape_html(bidder.first_name)}</b> won!\n"
                            f"🙇 <b>{escape_html(character.name)}</b> added to collection\n"
                            f"{get_emoji('coin')} Paid: <b>{active.current_bid:,} coins</b>\n"
                            f"{get_emoji('coin')} Seller <b>{escape_html(seller.first_name)}</b> received <b>{payout:,} coins</b> (5% tax deducted)\n"
                            f"{get_emoji('party')} Congratulations!"
                        )
                    )
                    try:
                        await bot.send_message(active.chat_id, win_card, parse_mode="HTML")
                    except Exception:
                        pass
                else:
                    # Cancelled (0 bids)
                    active.status = "cancelled"
                    
                    # Return character to seller
                    # Return character to seller
                    user_char = await db.get(UserCharacter, active.user_character_id)
                    if user_char:
                        user_char.user_id = active.seller_id
                    else:
                        user_char = UserCharacter(user_id=active.seller_id, character_id=active.character_id, nickname=nickname)
                        db.add(user_char)
                    await db.commit()
                    
                    cancel_card = (
                        "⚖️ <b>Auction Expired!</b>\n"
                        "───────────────\n"
                        + format_blockquote(
                            f"📛 Character: <b>{escape_html(character.name)}</b>\n"
                            f"{get_emoji('warning')} Status: <b>No bids received.</b>\n"
                            f"🏡 Character returned to seller <a href=\"tg://user?id={seller.user_id}\">{escape_html(seller.first_name)}</a>."
                        )
                    )
                    try:
                        await bot.send_message(active.chat_id, cancel_card, parse_mode="HTML")
                    except Exception:
                        pass
                
        # 2. Start next pending auction if no active exists
        stmt = select(Auction).where(Auction.status == "active")
        res = await db.execute(stmt)
        active = res.scalar_one_or_none()
        
        if not active:
            next_stmt = select(Auction).where(Auction.status == "pending").order_by(Auction.id).limit(1)
            next_res = await db.execute(next_stmt)
            next_auc = next_res.scalar_one_or_none()
            
            if next_auc:
                next_auc.status = "active"
                next_auc.started_at = datetime.datetime.utcnow()
                next_auc.expires_at = next_auc.started_at + datetime.timedelta(minutes=5)
                await db.commit()
                
                character = await db.get(Character, next_auc.character_id)
                card = await build_active_auction_card(next_auc, db)
                kb = build_auction_keyboard(next_auc)
                photo = character.image_url if character.image_url else get_cover_media("start")
                
                sent_msg = None
                try:
                    sent_msg = await bot.send_photo(next_auc.chat_id, photo, caption=card, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    try:
                        sent_msg = await bot.send_video(next_auc.chat_id, photo, caption=card, reply_markup=kb, parse_mode="HTML")
                    except Exception:
                        try:
                            sent_msg = await bot.send_animation(next_auc.chat_id, photo, caption=card, reply_markup=kb, parse_mode="HTML")
                        except Exception:
                            try:
                                sent_msg = await bot.send_message(next_auc.chat_id, card, reply_markup=kb, parse_mode="HTML")
                            except Exception:
                                pass
                if sent_msg:
                    next_auc.message_id = sent_msg.message_id
                    await db.commit()
                    try:
                        await bot.pin_chat_message(chat_id=next_auc.chat_id, message_id=sent_msg.message_id, disable_notification=True)
                    except Exception:
                        pass
