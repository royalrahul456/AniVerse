from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
import config
from utils.formatters import format_blockquote
from keyboards.inline import get_back_to_hub_keyboard

router = Router()

@router.callback_query(F.data == "dm_trade_info")
@router.message(Command("trade"))
async def cmd_trade(event):
    text = (
        "🔄 <b>AniVerse Trading Hub</b>\n\n"
        + format_blockquote(
            "Swap and trade rare characters with trainers across any group chat!\n\n"
            "🤝 <b>Usage:</b> Reply to any user's message in a group chat with:\n"
            "<code>/trade &lt;your_char_id&gt; &lt;their_char_id&gt;</code>\n\n"
            "Both users will be prompted with confirmation buttons to securely exchange characters!"
        )
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML")

@router.callback_query(F.data == "dm_redeem_info")
async def cmd_redeem(event):
    text = (
        "🎁 <b>Promo Code Redemption</b>\n\n"
        + format_blockquote(
            "Have a secret promo code from our updates channel?\n\n"
            "🎟️ <b>Usage:</b> <code>/redeem &lt;promo_code&gt;</code>\n\n"
            "Redeem codes for free bonus coins, special mystery boxes, and exclusive event characters!"
        )
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_to_hub_keyboard())
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML")
