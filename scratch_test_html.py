import asyncio
from aiogram.types import Message, MessageEntity

msg = Message(
    message_id=1,
    date=123,
    chat={"id": 1, "type": "private"},
    text="/editrarityemoji Divine 💌",
    entities=[
        MessageEntity(type="bot_command", offset=0, length=16),
        MessageEntity(type="custom_emoji", offset=24, length=1, custom_emoji_id="5368324170671202286")
    ]
)

print(msg.html_text)
