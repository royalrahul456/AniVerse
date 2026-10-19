# -*- coding: utf-8 -*-
import re
import os
import json
import logging
from typing import Optional
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.methods import (
    SendMessage,
    EditMessageText,
    SendPhoto,
    SendVideo,
    SendAnimation,
    SendAudio,
    SendDocument,
    EditMessageCaption
)
from aiogram.exceptions import TelegramBadRequest
import config

logger = logging.getLogger(__name__)

# Complete 100 emoji mapping provided by the user
EMOJI_MAPPING = {
    # 1. Cooldown & Time
    "⏳": "5307865960449843456",
    "⌛️": "5454415424319931791",
    "⌛": "5454415424319931791",
    "⏱️": "5373236586760651455",
    "⏱": "5373236586760651455",

    # 2. Settings & Admin
    "⚙️": "4965290516993278759",
    "⚙": "4965290516993278759",
    "⛩": "6093510268816460924",
    "⛩️": "6093510268816460924",
    "🛠️": "5462921117423384478",
    "🛠": "5462921117423384478",
    "🔧": "5258023599419171861",
    "🛡️": "5465154440287757794",
    "🛡": "5465154440287757794",
    "🔒": "5393302369024882368",
    "🔐": "5393302369024882368",

    # 3. Currency & Economy
    "🪙": "4918300654197277832",
    "💎": "5298799799884067733",
    "💸": "5233326571099534068",
    "💵": "5409048419211682843",
    "💳": "6185718195844812269",
    "🛒": "5258024802010026053",
    "💰": "4918300654197277832",

    # 4. Games & Battles
    "🎲": "5235588635885054955",
    "🎮": "5012808218385058363",
    "🧠": "5226639745106330551",
    "💀": "5357592447557848986",
    "💥": "5219901967916084166",
    "⚔️": "5453991094435997597",
    "⚔": "5453991094435997597",
    "🎰": "5098276216444552309",
    "🧩": "5098271397491246244",
    "🤖": "5287337687517242743",
    "🌀": "5467699418864040455",
    "🥷": "5391034312759980875",
    "💣": "5226813248900187912",
    "🏓": "5431428286905340656",
    "🔲": "5467617737176007012",
    "🎯": "5350460637182993292",

    # 5. Success, Errors & Alerts
    "✅": "5224634983221569440",
    "❌": "5210952531676504517",
    "⚠️": "5447644880824181073",
    "⚠": "5447644880824181073",
    "🚫": "5240241223632954241",
    "🛑": "5289485175460210350",
    "🚨": "6152366159883671628",

    # 6. Rarity Spheres
    "🟢": "5416081784641168838",
    "🔴": "5467584206366326723",
    "🟡": "5469722262561111478",
    "🔵": "5208773600277970208",
    "🟣": "5307720425483016568",
    "💮": "5190408384544794456",
    "🌸": "5375525443552162306",
    "👾": "5258196742435787040",
    "🌑": "5240147537511328128",
    "🔸": "5287713089133751614",

    # 7. Media & Characters
    "🖼️": "5033108527338488459",
    "🖼": "5033108527338488459",
    "📸": "6231107453178611892",
    "📺": "5350641446716193389",
    "🎥": "5350327536146463341",
    "🎬": "5350641446716193389",
    "🍿": "6278039359685926188",
    "🎨": "5195236692289659924",
    "🏷️": "5298623379807414367",
    "🏷": "5298623379807414367",
    "📝": "5033080906403808074",
    "📖": "6334834495379736183",
    "📋": "5308039077696643700",
    "✏️": "5469824826380140690",
    "✏": "5469824826380140690",

    # 8. Profile & Social
    "👑": "5217822164362739968",
    "🏆": "5226431245918942763",
    "🥇": "5440539497383087970",
    "🥈": "5447203607294265305",
    "🥉": "5453902265922376865",
    "👤": "5280781432824802048",
    "👥": "5280619787435650822",
    "🤝": "5463256910851546817",
    "💌": "5257980374868311346",
    "📢": "4967957395331351254",
    "📣": "5424818078833715060",
    "💬": "5443038326535759644",
    "💭": "5467538555158943525",
    "🖤": "5366579872783158101",
    "🎁": "5449800250032143374",

    # 9. UI Navigation & Arrows
    "🔄": "5346321684574003384",
    "➡️": "5433866913501434170",
    "⬅️": "5298509030598128013",
    "⬅": "5298509030598128013",
    "◀️": "4970176665062736422",
    "◀": "4970176665062736422",
    "➕": "5467922830177875987",
    "➖": "4970086827231806362",
    "🔻": "5469699739752612659",
    "🗑️": "5445267414562389170",
    "🗑": "5445267414562389170",
    "🔍": "5258274739041883702",
    "🔎": "5258396243666681152",
    "📌": "5397782960512444700",

    # 10. General Items & Elements
    "⚡️": "5341463333532882949",
    "⚡": "5341463333532882949",
    "🔥": "5256047523620995497",
    "⭐️": "5226928895189598791",
    "⭐": "5226928895189598791",
    "✨": "5325547803936572038",
    "💡": "5422439311196834318",
    "❓": "5436113877181941026",
    "📊": "5231200819986047254",
    "📈": "5244837092042750681",
    "📉": "5246762912428603768",
    "🏠": "5416041192905265756",
    "🏡": "5447411500891255968",
    "🎫": "5314784791986453963",
    "🎟️": "6190651597144461028",
    "🎟": "6190651597144461028",
    "🌐": "5447410659077661506",
    "🌍": "5244465315378651153",
    "📦": "5463172695132745432",
    "⚖️": "5379976829262118888",
    "⚖": "5379976829262118888",
    "🛂": "5307841307337564967",
}

ALL_EMOJIS_SET = set(EMOJI_MAPPING.keys())
SORTED_EMOJI_KEYS = sorted(EMOJI_MAPPING.keys(), key=lambda x: len(x), reverse=True)
_EMOJI_REGEX = re.compile("|".join(re.escape(k) for k in SORTED_EMOJI_KEYS))

HTML_TAG_PATTERN = re.compile(r'</?(?:b|strong|i|em|u|ins|s|strike|del|span|tg-spoiler|a|tg-emoji|code|pre|blockquote)\b', re.IGNORECASE)

SETTINGS_FILE = "data/settings.json"

def _load_settings_val() -> bool:
    # 1. Environment variable override
    env_val = os.getenv("ENABLE_PREMIUM_EMOJIS")
    if env_val is not None:
        return env_val.lower() in ("true", "1", "yes")

    # 2. Stored JSON setting
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "premium_emojis_enabled" in data:
                    return bool(data["premium_emojis_enabled"])
        except Exception:
            pass

    return False

_PREMIUM_EMOJIS_ENABLED = _load_settings_val()

def is_premium_emojis_enabled() -> bool:
    return _PREMIUM_EMOJIS_ENABLED

def set_premium_emojis_status(enabled: bool):
    global _PREMIUM_EMOJIS_ENABLED
    _PREMIUM_EMOJIS_ENABLED = enabled
    try:
        data = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["premium_emojis_enabled"] = enabled
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to persist premium emoji status: {e}")

def replace_emojis(text: str) -> str:
    """Replaces standard Unicode emojis with <tg-emoji emoji-id="..."> tags in a single pass."""
    if not isinstance(text, str) or not text:
        return text

    # Avoid duplicate replacements if tg-emoji tags already exist
    if "<tg-emoji" in text:
        return text

    def _replace_match(match):
        em = match.group(0)
        eid = EMOJI_MAPPING.get(em)
        if eid:
            # NOTICE: emoji-id with HYPHEN (required by Telegram API)
            return f'<tg-emoji emoji-id="{eid}">{em}</tg-emoji>'
        return em

    return _EMOJI_REGEX.sub(_replace_match, text)

def strip_tg_emojis(text: str) -> str:
    """Strips <tg-emoji ...> tags and retains internal emoji/content."""
    if not isinstance(text, str) or not text:
        return text
    cleaned = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', text)
    cleaned = re.sub(r'</?tg-emoji[^>]*>', '', cleaned)
    return cleaned

def markdown_to_html(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\*\*(.*?)\*\*|__(.*?)__', lambda m: f"<b>{m.group(1) or m.group(2)}</b>", text)
    text = re.sub(r'\*(.*?)\*|_(.*?)_', lambda m: f"<i>{m.group(1) or m.group(2)}</i>", text)
    text = re.sub(r'`(.*?)`', lambda m: f"<code>{m.group(1)}</code>", text)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    return text

def process_text_or_caption(text: str, parse_mode, bot_instance, max_len: int = 4096) -> tuple[str, str]:
    if not text or not is_premium_emojis_enabled():
        return text, parse_mode

    has_target = any(em in text for em in ALL_EMOJIS_SET)
    if not has_target:
        return text, parse_mode

    current_mode = parse_mode
    is_markdown = False

    if HTML_TAG_PATTERN.search(text):
        processed = replace_emojis(text)
        if len(processed) <= max_len:
            return processed, "HTML"
        return text, "HTML"

    if current_mode is None:
        bot_default_mode = getattr(bot_instance, "default", None) and bot_instance.default.parse_mode
        if bot_default_mode in (ParseMode.MARKDOWN, ParseMode.MARKDOWN_V2, "Markdown", "MarkdownV2"):
            is_markdown = True
    elif isinstance(current_mode, str) and current_mode.lower() in ("markdown", "markdownv2"):
        is_markdown = True
    elif current_mode in (ParseMode.MARKDOWN, ParseMode.MARKDOWN_V2):
        is_markdown = True

    if is_markdown:
        text = markdown_to_html(text)
        current_mode = "HTML"

    processed = replace_emojis(text)
    if len(processed) <= max_len:
        return processed, current_mode
    return text, current_mode

def patch_bot_emojis(bot: Bot):
    """Intercepts outgoing messages to inject custom emojis and provides automatic error recovery fallback."""
    original_make_request = bot.session.make_request

    async def new_make_request(bot_instance, method, timeout=None):
        parse_mode = getattr(method, "parse_mode", None)

        if is_premium_emojis_enabled():
            if isinstance(method, (SendMessage, EditMessageText)):
                if method.text and isinstance(method.text, str):
                    method.text, new_mode = process_text_or_caption(method.text, parse_mode, bot_instance, max_len=4096)
                    method.parse_mode = new_mode
            elif isinstance(method, (SendPhoto, SendVideo, SendAnimation, SendAudio, SendDocument, EditMessageCaption)):
                if method.caption and isinstance(method.caption, str):
                    method.caption, new_mode = process_text_or_caption(method.caption, parse_mode, bot_instance, max_len=1024)
                    method.parse_mode = new_mode

        try:
            return await original_make_request(bot_instance, method, timeout=timeout)
        except TelegramBadRequest as e:
            err_str = str(e).lower()
            if (
                "custom_emoji" in err_str
                or "entity_bounds_invalid" in err_str
                or "cannot_use_custom_emoji" in err_str
                or "can't use custom emoji" in err_str
                or "can't parse entities" in err_str
                or "failed to parse entities" in err_str
                or "tag" in err_str
                or "too long" in err_str
                or "caption" in err_str
            ):
                logger.warning(f"Telegram API parsing/emoji error: {e}. Retrying with clean Unicode fallback...")
                # Automatic recovery: strip custom emoji tags and retry
                if isinstance(method, (SendMessage, EditMessageText)):
                    if method.text:
                        method.text = strip_tg_emojis(method.text)
                elif isinstance(method, (SendPhoto, SendVideo, SendAnimation, SendAudio, SendDocument, EditMessageCaption)):
                    if method.caption:
                        method.caption = strip_tg_emojis(method.caption)

                try:
                    return await original_make_request(bot_instance, method, timeout=timeout)
                except TelegramBadRequest as e2:
                    logger.warning(f"Retrying message with parse_mode=None fallback: {e2}")
                    method.parse_mode = None
                    return await original_make_request(bot_instance, method, timeout=timeout)
            raise e

    bot.session.make_request = new_make_request
    logger.info("Premium custom emoji session interceptor active.")
