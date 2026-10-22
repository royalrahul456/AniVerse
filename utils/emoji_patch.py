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
    EditMessageCaption,
    EditMessageMedia
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
_EMOJI_PATTERN = "|".join(re.escape(k) for k in SORTED_EMOJI_KEYS)
_EMOJI_REGEX = re.compile(_EMOJI_PATTERN)

# Tokenizer pattern: cleanly matches tags/code blocks to skip, while isolating target emojis
_TOKEN_REGEX = re.compile(
    r'(<code[^>]*>.*?</code>|<pre[^>]*>.*?</pre>|<tg-emoji[^>]*>.*?</tg-emoji>|<[^>]+>|&[a-zA-Z0-9#]+;)|(' + _EMOJI_PATTERN + r')',
    re.IGNORECASE | re.DOTALL
)

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

    return True

_PREMIUM_EMOJIS_ENABLED = _load_settings_val()

def is_premium_emojis_enabled() -> bool:
    return _PREMIUM_EMOJIS_ENABLED

def set_premium_emojis_status(enabled: bool):
    global _PREMIUM_EMOJIS_ENABLED
    _PREMIUM_EMOJIS_ENABLED = enabled
    try:
        import utils.emojis
        utils.emojis.ENABLE_PREMIUM_EMOJIS = enabled
    except Exception:
        pass
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

def rebuild_emoji_regex():
    """Rebuilds regex whenever new custom emojis are mapped from Telegram or loaded from DB."""
    global _TOKEN_REGEX, _EMOJI_REGEX, _EMOJI_PATTERN, SORTED_EMOJI_KEYS, ALL_EMOJIS_SET
    ALL_EMOJIS_SET = set(EMOJI_MAPPING.keys())
    SORTED_EMOJI_KEYS = sorted(EMOJI_MAPPING.keys(), key=lambda x: len(x), reverse=True)
    _EMOJI_PATTERN = "|".join(re.escape(k) for k in SORTED_EMOJI_KEYS)
    _EMOJI_REGEX = re.compile(_EMOJI_PATTERN)
    _TOKEN_REGEX = re.compile(
        r'(<code[^>]*>.*?</code>|<pre[^>]*>.*?</pre>|<tg-emoji[^>]*>.*?</tg-emoji>|<[^>]+>|&[a-zA-Z0-9#]+;)|(' + _EMOJI_PATTERN + r')',
        re.IGNORECASE | re.DOTALL
    )

def replace_emojis(text: str) -> str:
    """Replaces standard Unicode emojis with <tg-emoji emoji-id="..."> tags in a single pass,
    safely preserving code blocks, pre blocks, HTML tags, and existing tg-emoji tags."""
    if not isinstance(text, str) or not text:
        return text

    def _replace_match(match):
        tag_or_code = match.group(1)
        if tag_or_code is not None:
            return tag_or_code
        em = match.group(2)
        eid = EMOJI_MAPPING.get(em) or EMOJI_MAPPING.get(em.replace('️', ''))
        if eid:
            return f'<tg-emoji emoji-id="{eid}">{em}</tg-emoji>'
        return em

    return _TOKEN_REGEX.sub(_replace_match, text)

def strip_tg_emojis(text: str) -> str:
    """Strips <tg-emoji ...> tags and retains internal emoji/content."""
    if not isinstance(text, str) or not text:
        return text
    cleaned = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', text, flags=re.DOTALL)
    cleaned = re.sub(r'</?tg-emoji[^>]*>', '', cleaned)
    return cleaned

def enhance_reply_markup(markup):
    """Enhances buttons in InlineKeyboardMarkup with style colors (primary/success/danger)
    and attaches native icon_custom_emoji_id while ensuring fallback text with clean Unicode
    emojis is always preserved."""
    if not markup:
        return markup
    try:
        inline_kb = getattr(markup, "inline_keyboard", None)
        if inline_kb is None and isinstance(markup, dict):
            inline_kb = markup.get("inline_keyboard")

        if inline_kb is not None:
            for row in inline_kb:
                for btn in row:
                    orig_text = btn.get("text", "") if isinstance(btn, dict) else getattr(btn, "text", "")
                    if not orig_text or not isinstance(orig_text, str):
                        continue

                    # 1. Detect any <tg-emoji> tag or unicode emoji in button text
                    tg_match = re.search(r'<tg-emoji[^>]*emoji-id=["\']?(\d+)["\']?[^>]*>(.*?)</tg-emoji>', orig_text)
                    custom_id = None
                    emoji_char = None

                    if tg_match:
                        custom_id = tg_match.group(1)
                        emoji_char = tg_match.group(2)
                        clean_text = re.sub(r'<tg-emoji[^>]*>.*?</tg-emoji>', '', orig_text).strip()
                        fallback_text = f"{emoji_char} {clean_text}".strip()
                    else:
                        clean_text = orig_text.strip()
                        fallback_text = orig_text
                        for em in SORTED_EMOJI_KEYS:
                            if em in orig_text:
                                custom_id = EMOJI_MAPPING.get(em)
                                emoji_char = em
                                if clean_text.startswith(em):
                                    candidate = clean_text[len(em):].strip()
                                    if candidate:
                                        clean_text = candidate
                                break

                    # 2. Determine button color style if not already explicitly set
                    cur_style = btn.get("style", None) if isinstance(btn, dict) else getattr(btn, "style", None)
                    if not cur_style:
                        combined = f"{orig_text} {btn.get('callback_data', '') if isinstance(btn, dict) else getattr(btn, 'callback_data', '')}".lower()
                        if any(k in combined for k in ["claim", "accept", "pokedex", "animedex", "buy", "join", "confirm", "start", "collect", "redeem", "win", "agree", "done", "yes"]):
                            cur_style = "success"
                        elif any(k in combined for k in ["cancel", "decline", "delete", "close", "reject", "reset", "remove", "vip", "battle", "no", "stop"]):
                            cur_style = "danger"
                        elif any(k in combined for k in ["profile", "refresh", "help", "guide", "update", "updates", "leaderboard", "home", "back", "settings", "shop", "play", "games", "bag", "harem", "streak", "dex"]):
                            cur_style = "primary"

                    # 3. Apply properties
                    if isinstance(btn, dict):
                        btn["_fallback_text"] = fallback_text
                        if cur_style:
                            btn["style"] = cur_style
                        if custom_id and is_premium_emojis_enabled():
                            btn["icon_custom_emoji_id"] = str(custom_id)
                            btn["text"] = clean_text
                        else:
                            btn["text"] = fallback_text
                    else:
                        try:
                            setattr(btn, "_fallback_text", fallback_text)
                        except Exception:
                            pass
                        if cur_style:
                            try:
                                btn.style = cur_style
                            except Exception:
                                pass
                        if custom_id and is_premium_emojis_enabled():
                            try:
                                btn.icon_custom_emoji_id = str(custom_id)
                                btn.text = clean_text
                            except Exception:
                                btn.text = fallback_text
                        else:
                            btn.text = fallback_text

        # Also sanitize ReplyKeyboardMarkup
        kb = getattr(markup, "keyboard", None)
        if kb is None and isinstance(markup, dict):
            kb = markup.get("keyboard")
        if kb is not None:
            for row in kb:
                for btn in row:
                    if isinstance(btn, dict):
                        if "text" in btn and isinstance(btn["text"], str) and "<tg-emoji" in btn["text"]:
                            btn["text"] = strip_tg_emojis(btn["text"])
                    elif hasattr(btn, "text") and isinstance(btn.text, str) and "<tg-emoji" in btn.text:
                        btn.text = strip_tg_emojis(btn.text)
    except Exception as e:
        logger.error(f"Error enhancing reply_markup buttons: {e}", exc_info=True)
    return markup


def fallback_strip_button_icons(markup):
    """Strips icon_custom_emoji_id and restores Unicode emojis on all buttons."""
    if not markup:
        return markup
    try:
        inline_kb = getattr(markup, "inline_keyboard", None)
        if inline_kb is None and isinstance(markup, dict):
            inline_kb = markup.get("inline_keyboard")

        if inline_kb is not None:
            for row in inline_kb:
                for btn in row:
                    if isinstance(btn, dict):
                        if "_fallback_text" in btn and btn["_fallback_text"]:
                            btn["text"] = btn["_fallback_text"]
                        btn.pop("icon_custom_emoji_id", None)
                    else:
                        if hasattr(btn, "_fallback_text") and getattr(btn, "_fallback_text"):
                            btn.text = getattr(btn, "_fallback_text")
                        try:
                            btn.icon_custom_emoji_id = None
                        except Exception:
                            pass
    except Exception as e:
        logger.error(f"Error stripping button icons in fallback: {e}")
    return markup


def fallback_strip_button_styles(markup):
    """Strips button styles in case an old API server rejects the style field."""
    if not markup:
        return markup
    try:
        inline_kb = getattr(markup, "inline_keyboard", None)
        if inline_kb is None and isinstance(markup, dict):
            inline_kb = markup.get("inline_keyboard")

        if inline_kb is not None:
            for row in inline_kb:
                for btn in row:
                    if isinstance(btn, dict):
                        btn.pop("style", None)
                        btn.pop("icon_custom_emoji_id", None)
                    else:
                        try:
                            btn.style = None
                        except Exception:
                            pass
                        try:
                            btn.icon_custom_emoji_id = None
                        except Exception:
                            pass
    except Exception as e:
        logger.error(f"Error stripping button styles in fallback: {e}")
    return markup


def sanitize_reply_markup(markup):
    """Alias for backwards compatibility."""
    return enhance_reply_markup(markup)

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
        return processed, "HTML"
    return text, current_mode

def patch_bot_emojis(bot: Bot):
    """Intercepts outgoing messages to inject custom emojis and provides automatic error recovery fallback."""
    original_make_request = bot.session.make_request

    async def new_make_request(bot_instance, method, timeout=None):
        # 1. Enhance button colors (styles) & try native custom emoji icon (with fallback preservation)
        if hasattr(method, "reply_markup") and method.reply_markup:
            enhance_reply_markup(method.reply_markup)

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
            elif isinstance(method, EditMessageMedia):
                if method.media and getattr(method.media, "caption", None) and isinstance(method.media.caption, str):
                    m_mode = getattr(method.media, "parse_mode", None) or parse_mode
                    method.media.caption, new_mode = process_text_or_caption(method.media.caption, m_mode, bot_instance, max_len=1024)
                    method.media.parse_mode = new_mode

        try:
            return await original_make_request(bot_instance, method, timeout=timeout)
        except TelegramBadRequest as e:
            err_str = str(e).lower()
            if (
                "button_icon_custom_emoji" in err_str
                or "button_type_invalid" in err_str
                or "button_style" in err_str
                or "custom_emoji" in err_str
                or "entity_bounds_invalid" in err_str
                or "cannot_use_custom_emoji" in err_str
                or "can't use custom emoji" in err_str
                or "can't parse entities" in err_str
                or "failed to parse entities" in err_str
                or "unsupported start tag" in err_str
                or "tag" in err_str
                or "too long" in err_str
                or "caption" in err_str
            ):
                logger.warning(f"Telegram API request issue: {e}. Retrying with safe Unicode fallback...")
                # Automatic recovery: strip custom emoji tags from text/caption
                if isinstance(method, (SendMessage, EditMessageText)):
                    if method.text:
                        method.text = strip_tg_emojis(method.text)
                elif isinstance(method, (SendPhoto, SendVideo, SendAnimation, SendAudio, SendDocument, EditMessageCaption)):
                    if method.caption:
                        method.caption = strip_tg_emojis(method.caption)
                elif isinstance(method, EditMessageMedia):
                    if method.media and getattr(method.media, "caption", None):
                        method.media.caption = strip_tg_emojis(method.media.caption)

                # Automatic recovery for buttons: strip icon_custom_emoji_id and restore Unicode emoji in button title
                if hasattr(method, "reply_markup") and method.reply_markup:
                    fallback_strip_button_icons(method.reply_markup)

                try:
                    return await original_make_request(bot_instance, method, timeout=timeout)
                except TelegramBadRequest as e2:
                    logger.warning(f"Retrying message with parse_mode=None & plain button fallback: {e2}")
                    if hasattr(method, "reply_markup") and method.reply_markup:
                        fallback_strip_button_styles(method.reply_markup)
                    if isinstance(method, EditMessageMedia) and method.media:
                        method.media.parse_mode = None
                    else:
                        method.parse_mode = None
                    return await original_make_request(bot_instance, method, timeout=timeout)
            raise e

    bot.session.make_request = new_make_request
    logger.info("Premium custom emoji session interceptor active.")
