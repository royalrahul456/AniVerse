import os
from typing import Optional

# In-memory cache for fast lookups
EMOJI_CACHE = {}

# Set to True only if your bot username is a Fragment collectible that has custom emoji permissions
ENABLE_PREMIUM_EMOJIS = os.getenv("ENABLE_PREMIUM_EMOJIS", "false").lower() in ("true", "1", "yes")

# Default unicode fallbacks for standard keys
DEFAULT_EMOJIS = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "coin": "🪙",
    "crown": "👑",
    "party": "🎉",
    "id": "🆔",
    "gem": "💎",
    "back": "⬅️",
    "sparkle": "✨",
    "pointer": "➡️",
    "circle": "⭕",
    "energy": "⚡️",
    "tv": "📺",
    "bomb": "💣",
    "gift": "🎁",
    "trophy": "🏆",
    "target": "🎯",
    "no_entry": "🚫",
    "user": "👤",
    "settings": "⚙️",
    "hint": "💡",
    "admin": "⛩",
    "dice": "🎲",
    "monster": "👾",
    "image": "🖼",
    "refresh": "🔄",
    "games": "🎮",
    "spring": "🌸",
    "question": "❓",
    "delete": "🗑",
    "stats": "📊",
    "chart_up": "📈",
    "trivia": "🧠",
    "rarity_uncommon": "🟢",
    "skull": "💀",
    "palette": "🎨",
    "trade": "🤝",
    "rarity_mythical": "🔴",
    "camera": "📸",
    "memo": "📝",
    "search": "🔍",
    "collision": "💥",
    "fire": "🔥",
    "star": "⭐️",
    "plus": "➕",
    "rarity_legendary": "🟡",
    "tag": "🏷",
    "hourglass": "⌛️",
    "cooldown": "⏳",
    "shield": "🛡",
    "spend": "💸",
    "battle": "⚔️",
    "rarity_rare": "🔵",
    "tools": "🛠",
    "group": "👥",
    "mail": "💌",
    "broadcast": "📢",
    "stop": "🛑",
    "slot": "🎰",
    "puzzle": "🧩",
    "bot": "🤖",
    "popcorn": "🍿",
    "lock": "🔒",
    "home": "🏠",
    "card": "💳",
    "ticket": "🎫",
    "prev": "◀️",
    "rarity_epic": "🟣",
    "chat": "💬",
    "chart_down": "📉",
    "spin": "🌀",
    "ninja": "🥷",
    "alert": "🚨",
    "flower": "💮",
    "diamond": "🔸",
    "moon": "🌑",
    "movie": "🎥",
    "wrench": "🔧",
    "megaphone": "📣",
    "balance": "⚖",
    "house_garden": "🏡",
    "thought": "💭",
    "stopwatch": "⏱",
    "cash": "💵",
    "globe": "🌐",
    "heart": "🖤",
    "square": "🔲",
    "pingpong": "🏓",
    "world": "🌍",
    "package": "📦",
    "gold_medal": "🥇",
    "silver_medal": "🥈",
    "bronze_medal": "🥉",
    "pin": "📌",
    "tickets": "🎟️",
    "passport": "🛂",
    "book": "📖",
    "inspect": "🔎",
    "shop": "🛒",
    "edit": "✏️",
    "minus": "➖",
    "down": "🔻",
    "clipboard": "📋",
}

# 100 Premium Custom Emoji IDs
PREMIUM_EMOJI_IDS = {
    # 1. ⏳ Cooldown / Hourglass
    "⏳": "5307865960449843456",
    "cooldown": "5307865960449843456",

    # 2. ⚙️ Settings / Gear
    "⚙️": "4965290516993278759",
    "⚙": "4965290516993278759",
    "settings": "4965290516993278759",
    "gear": "4965290516993278759",

    # 3. 🪙 Coin / Currency
    "🪙": "4918300654197277832",
    "coin": "4918300654197277832",
    "currency": "4918300654197277832",

    # 4. 💡 Hint / Light bulb
    "💡": "5422439311196834318",
    "hint": "5422439311196834318",
    "light_bulb": "5422439311196834318",

    # 5. ⛩ Admin / Shinto Shrine
    "⛩": "6093510268816460924",
    "⛩️": "6093510268816460924",
    "admin": "6093510268816460924",
    "shinto_shrine": "6093510268816460924",

    # 6. 🎲 Dice / Roll
    "🎲": "5235588635885054955",
    "dice": "5235588635885054955",
    "game_die": "5235588635885054955",

    # 7. 👾 Alien Monster
    "👾": "5258196742435787040",
    "monster": "5258196742435787040",
    "alien_monster": "5258196742435787040",

    # 8. ⚡️ Energy / High Voltage
    "⚡️": "5341463333532882949",
    "⚡": "5341463333532882949",
    "energy": "5341463333532882949",

    # 9. 🖼 Frame / Image
    "🖼": "5033108527338488459",
    "🖼️": "5033108527338488459",
    "image": "5033108527338488459",
    "framed_picture": "5033108527338488459",

    # 10. 🔄 Refresh / Counterclockwise Arrows
    "🔄": "5346321684574003384",
    "refresh": "5346321684574003384",

    # 11. 🎮 Games / Video Game
    "🎮": "5012808218385058363",
    "games": "5012808218385058363",
    "video_game": "5012808218385058363",

    # 12. 🌸 Cherry Blossom
    "🌸": "5375525443552162306",
    "spring": "5375525443552162306",
    "cherry_blossom": "5375525443552162306",

    # 13. ❓ Question Mark
    "❓": "5436113877181941026",
    "question": "5436113877181941026",

    # 14. 👑 Crown
    "👑": "5217822164362739968",
    "crown": "5217822164362739968",

    # 15. 🗑 Wastebasket / Delete
    "🗑": "5445267414562389170",
    "🗑️": "5445267414562389170",
    "delete": "5445267414562389170",
    "wastebasket": "5445267414562389170",

    # 16. 📊 Bar Chart / Stats
    "📊": "5231200819986047254",
    "stats": "5231200819986047254",
    "bar_chart": "5231200819986047254",

    # 17. 📈 Chart Increasing
    "📈": "5244837092042750681",
    "chart_up": "5244837092042750681",
    "chart_increasing": "5244837092042750681",

    # 18. 🚫 Prohibited / No Entry
    "🚫": "5240241223632954241",
    "no_entry": "5240241223632954241",
    "prohibited": "5240241223632954241",

    # 19. 🧠 Brain / Trivia
    "🧠": "5226639745106330551",
    "brain": "5226639745106330551",
    "trivia": "5226639745106330551",

    # 20. 🟢 Green Circle (Uncommon)
    "🟢": "5416081784641168838",
    "green_circle": "5416081784641168838",
    "rarity_uncommon": "5416081784641168838",

    # 21. 🎁 Gift / Wrapped Gift
    "🎁": "5449800250032143374",
    "gift": "5449800250032143374",
    "wrapped_gift": "5449800250032143374",

    # 22. 💀 Skull
    "💀": "5357592447557848986",
    "skull": "5357592447557848986",

    # 23. 🎨 Artist Palette
    "🎨": "5195236692289659924",
    "palette": "5195236692289659924",
    "artist_palette": "5195236692289659924",

    # 24. 🤝 Handshake / Trade
    "🤝": "5463256910851546817",
    "trade": "5463256910851546817",
    "handshake": "5463256910851546817",

    # 25. 🔴 Red Circle (Mythical)
    "🔴": "5467584206366326723",
    "red_circle": "5467584206366326723",
    "rarity_mythical": "5467584206366326723",

    # 26. 📸 Camera
    "📸": "6231107453178611892",
    "camera": "6231107453178611892",
    "camera_with_flash": "6231107453178611892",

    # 27. 📝 Memo
    "📝": "5033080906403808074",
    "memo": "5033080906403808074",

    # 28. 🔍 Search
    "🔍": "5258274739041883702",
    "search": "5258274739041883702",
    "magnifying_glass_tilted_left": "5258274739041883702",

    # 29. 💥 Collision / Blast
    "💥": "5219901967916084166",
    "collision": "5219901967916084166",

    # 30. 🔥 Fire
    "🔥": "5256047523620995497",
    "fire": "5256047523620995497",

    # 31. ⭐️ Star
    "⭐️": "5226928895189598791",
    "⭐": "5226928895189598791",
    "star": "5226928895189598791",

    # 32. ➡️ Right Arrow / Pointer
    "➡️": "5433866913501434170",
    "pointer": "5433866913501434170",
    "right_arrow": "5433866913501434170",

    # 33. ➕ Plus
    "➕": "5467922830177875987",
    "plus": "5467922830177875987",

    # 34. 🟡 Yellow Circle (Legendary)
    "🟡": "5469722262561111478",
    "yellow_circle": "5469722262561111478",
    "rarity_legendary": "5469722262561111478",

    # 35. 🏷 Label / Tag
    "🏷": "5298623379807414367",
    "🏷️": "5298623379807414367",
    "tag": "5298623379807414367",
    "label": "5298623379807414367",

    # 36. ⌛️ Hourglass Done
    "⌛️": "5454415424319931791",
    "⌛": "5454415424319931791",
    "hourglass": "5454415424319931791",
    "hourglass_done": "5454415424319931791",

    # 37. 🛡 Shield
    "🛡": "5465154440287757794",
    "🛡️": "5465154440287757794",
    "shield": "5465154440287757794",

    # 38. 💎 Gem
    "💎": "5298799799884067733",
    "gem": "5298799799884067733",
    "gem_stone": "5298799799884067733",

    # 39. 💸 Money with Wings
    "💸": "5233326571099534068",
    "spend": "5233326571099534068",
    "money_with_wings": "5233326571099534068",

    # 40. ⚔️ Crossed Swords / Battle
    "⚔️": "5453991094435997597",
    "⚔": "5453991094435997597",
    "battle": "5453991094435997597",
    "crossed_swords": "5453991094435997597",

    # 41. ✨ Sparkles
    "✨": "5325547803936572038",
    "sparkle": "5325547803936572038",
    "sparkles": "5325547803936572038",

    # 42. 🔵 Blue Circle (Rare)
    "🔵": "5208773600277970208",
    "blue_circle": "5208773600277970208",
    "rarity_rare": "5208773600277970208",

    # 43. 🛠 Hammer & Wrench / Tools
    "🛠": "5462921117423384478",
    "🛠️": "5462921117423384478",
    "tools": "5462921117423384478",
    "hammer_and_wrench": "5462921117423384478",

    # 44. 👥 Busts in Silhouette / Group
    "👥": "5280619787435650822",
    "group": "5280619787435650822",
    "busts_in_silhouette": "5280619787435650822",

    # 45. 💌 Love Letter / Mail
    "💌": "5257980374868311346",
    "mail": "5257980374868311346",
    "love_letter": "5257980374868311346",

    # 46. 📢 Loudspeaker / Broadcast
    "📢": "4967957395331351254",
    "broadcast": "4967957395331351254",
    "loudspeaker": "4967957395331351254",

    # 47. 🛑 Stop Sign
    "🛑": "5289485175460210350",
    "stop": "5289485175460210350",
    "stop_sign": "5289485175460210350",

    # 48. 🎰 Slot Machine
    "🎰": "5098276216444552309",
    "slot": "5098276216444552309",
    "slot_machine": "5098276216444552309",

    # 49. 🧩 Puzzle Piece
    "🧩": "5098271397491246244",
    "puzzle": "5098271397491246244",
    "puzzle_piece": "5098271397491246244",

    # 50. 🤖 Robot / Bot
    "🤖": "5287337687517242743",
    "bot": "5287337687517242743",
    "robot": "5287337687517242743",

    # 51. 🍿 Popcorn
    "🍿": "6278039359685926188",
    "popcorn": "6278039359685926188",

    # 52. 🔒 Locked
    "🔒": "5393302369024882368",
    "lock": "5393302369024882368",
    "locked": "5393302369024882368",

    # 53. 🏠 House / Home
    "🏠": "5416041192905265756",
    "home": "5416041192905265756",
    "house": "5416041192905265756",

    # 54. 💳 Credit Card
    "💳": "6185718195844812269",
    "card": "6185718195844812269",
    "credit_card": "6185718195844812269",

    # 55. 🎫 Ticket
    "🎫": "5314784791986453963",
    "ticket": "5314784791986453963",

    # 56. ◀️ Reverse Button / Previous
    "◀️": "4970176665062736422",
    "◀": "4970176665062736422",
    "prev": "4970176665062736422",
    "reverse_button": "4970176665062736422",

    # 57. 🟣 Purple Circle (Epic)
    "🟣": "5307720425483016568",
    "purple_circle": "5307720425483016568",
    "rarity_epic": "5307720425483016568",

    # 58. 💬 Speech Balloon / Chat
    "💬": "5443038326535759644",
    "chat": "5443038326535759644",
    "speech_balloon": "5443038326535759644",

    # 59. 📉 Chart Decreasing
    "📉": "5246762912428603768",
    "chart_down": "5246762912428603768",
    "chart_decreasing": "5246762912428603768",

    # 60. ✅ Success / Check Mark
    "✅": "5224634983221569440",
    "success": "5224634983221569440",
    "check_mark_button": "5224634983221569440",

    # 61. ❌ Error / Cross Mark
    "❌": "5210952531676504517",
    "error": "5210952531676504517",
    "cross_mark": "5210952531676504517",

    # 62. 🌀 Cyclone / Spin
    "🌀": "5467699418864040455",
    "spin": "5467699418864040455",
    "cyclone": "5467699418864040455",

    # 63. 🥷 Ninja
    "🥷": "5391034312759980875",
    "ninja": "5391034312759980875",

    # 64. 🚨 Police Car Light / Alert
    "🚨": "6152366159883671628",
    "alert": "6152366159883671628",
    "police_car_light": "6152366159883671628",

    # 65. 💮 White Flower
    "💮": "5190408384544794456",
    "flower": "5190408384544794456",
    "white_flower": "5190408384544794456",

    # 66. 🔸 Small Orange Diamond
    "🔸": "5287713089133751614",
    "diamond": "5287713089133751614",
    "small_orange_diamond": "5287713089133751614",

    # 67. 🌑 New Moon
    "🌑": "5240147537511328128",
    "moon": "5240147537511328128",
    "new_moon": "5240147537511328128",

    # 68. 👤 User / Profile
    "👤": "5280781432824802048",
    "user": "5280781432824802048",
    "bust_in_silhouette": "5280781432824802048",

    # 69. 🏆 Trophy
    "🏆": "5226431245918942763",
    "trophy": "5226431245918942763",

    # 70. 📺 Television / Anime
    "📺": "5350641446716193389",
    "tv": "5350641446716193389",
    "television": "5350641446716193389",

    # 71. 💣 Bomb
    "💣": "5226813248900187912",
    "bomb": "5226813248900187912",

    # 72. 🎥 Movie Camera
    "🎥": "5350327536146463341",
    "movie": "5350327536146463341",
    "movie_camera": "5350327536146463341",

    # 73. 🔧 Wrench
    "🔧": "5258023599419171861",
    "wrench": "5258023599419171861",

    # 74. 📣 Megaphone
    "📣": "5424818078833715060",
    "megaphone": "5424818078833715060",

    # 75. ⚖ Balance Scale
    "⚖": "5379976829262118888",
    "⚖️": "5379976829262118888",
    "balance": "5379976829262118888",
    "balance_scale": "5379976829262118888",

    # 76. 🏡 House with Garden
    "🏡": "5447411500891255968",
    "house_garden": "5447411500891255968",
    "house_with_garden": "5447411500891255968",

    # 77. 💭 Thought Balloon
    "💭": "5467538555158943525",
    "thought": "5467538555158943525",
    "thought_balloon": "5467538555158943525",

    # 78. ⏱ Stopwatch
    "⏱": "5373236586760651455",
    "⏱️": "5373236586760651455",
    "stopwatch": "5373236586760651455",

    # 79. 💵 Dollar Banknote
    "💵": "5409048419211682843",
    "cash": "5409048419211682843",
    "dollar_banknote": "5409048419211682843",

    # 80. 🌐 Globe with Meridians
    "🌐": "5447410659077661506",
    "globe": "5447410659077661506",
    "globe_with_meridians": "5447410659077661506",

    # 81. 🖤 Black Heart
    "🖤": "5366579872783158101",
    "heart": "5366579872783158101",
    "black_heart": "5366579872783158101",

    # 82. 🔲 Black Square Button
    "🔲": "5467617737176007012",
    "square": "5467617737176007012",
    "black_square_button": "5467617737176007012",

    # 83. 🏓 Ping Pong
    "🏓": "5431428286905340656",
    "pingpong": "5431428286905340656",
    "ping_pong": "5431428286905340656",

    # 84. 🌍 Globe Showing Europe-Africa
    "🌍": "5244465315378651153",
    "world": "5244465315378651153",
    "globe_showing_Europe-Africa": "5244465315378651153",

    # 85. 📦 Package
    "📦": "5463172695132745432",
    "package": "5463172695132745432",

    # 86. ⬅️ Left Arrow / Back
    "⬅️": "5298509030598128013",
    "⬅": "5298509030598128013",
    "back": "5298509030598128013",
    "left_arrow": "5298509030598128013",

    # 87. 🥇 1st Place Medal
    "🥇": "5440539497383087970",
    "gold_medal": "5440539497383087970",
    "1st_place_medal": "5440539497383087970",

    # 88. 🥈 2nd Place Medal
    "🥈": "5447203607294265305",
    "silver_medal": "5447203607294265305",
    "2nd_place_medal": "5447203607294265305",

    # 89. 🥉 3rd Place Medal
    "🥉": "5453902265922376865",
    "bronze_medal": "5453902265922376865",
    "3rd_place_medal": "5453902265922376865",

    # 90. 📌 Pushpin
    "📌": "5397782960512444700",
    "pin": "5397782960512444700",
    "pushpin": "5397782960512444700",

    # 91. 🎟️ Admission Tickets
    "🎟️": "6190651597144461028",
    "🎟": "6190651597144461028",
    "tickets": "6190651597144461028",
    "admission_tickets": "6190651597144461028",

    # 92. 🛂 Passport Control
    "🛂": "5307841307337564967",
    "passport": "5307841307337564967",
    "passport_control": "5307841307337564967",

    # 93. 📖 Open Book
    "📖": "6334834495379736183",
    "book": "6334834495379736183",
    "open_book": "6334834495379736183",

    # 94. 🔎 Magnifying Glass Right
    "🔎": "5258396243666681152",
    "inspect": "5258396243666681152",
    "magnifying_glass_tilted_right": "5258396243666681152",

    # 95. 🛒 Shopping Cart
    "🛒": "5258024802010026053",
    "shop": "5258024802010026053",
    "shopping_cart": "5258024802010026053",

    # 96. ✏️ Pencil
    "✏️": "5469824826380140690",
    "✏": "5469824826380140690",
    "edit": "5469824826380140690",
    "pencil": "5469824826380140690",

    # 97. ➖ Minus
    "➖": "4970086827231806362",
    "minus": "4970086827231806362",

    # 98. 🔻 Red Triangle Down
    "🔻": "5469699739752612659",
    "down": "5469699739752612659",
    "red_triangle_pointed_down": "5469699739752612659",

    # 99. 📋 Clipboard
    "📋": "5308039077696643700",
    "clipboard": "5308039077696643700",

    # 100. ⚠️ Warning
    "⚠️": "5447644880824181073",
    "⚠": "5447644880824181073",
    "warning": "5447644880824181073",
}

async def load_emojis(db):
    """Load custom emojis from database into cache."""
    try:
        from database.models import BotEmoji
        from sqlalchemy.future import select
        stmt = select(BotEmoji)
        result = await db.execute(stmt)
        emojis = result.scalars().all()
        for em in emojis:
            EMOJI_CACHE[em.key] = em.emoji
    except Exception as e:
        pass

def get_emoji(key: str) -> str:
    """Get the emoji for a given key or unicode character.
    If premium custom emojis are enabled and an ID is available,
    returns <tg-emoji emoji_id="{id}">{emoji}</tg-emoji>.
    Otherwise, returns the unicode emoji fallback.
    """
    # Normalize key (strip variation selector if passed as char)
    clean_key = key.replace("️", "") if isinstance(key, str) else key
    fallback = DEFAULT_EMOJIS.get(key, DEFAULT_EMOJIS.get(clean_key, key))

    # If premium custom emojis are disabled, ALWAYS return the safe unicode fallback
    if not ENABLE_PREMIUM_EMOJIS:
        return fallback

    # 1. Check in-memory database cache
    if key in EMOJI_CACHE:
        return EMOJI_CACHE[key]

    emoji_id = PREMIUM_EMOJI_IDS.get(key) or PREMIUM_EMOJI_IDS.get(clean_key)
    if not emoji_id and fallback in PREMIUM_EMOJI_IDS:
        emoji_id = PREMIUM_EMOJI_IDS[fallback]
    if not emoji_id and fallback.replace("️", "") in PREMIUM_EMOJI_IDS:
        emoji_id = PREMIUM_EMOJI_IDS[fallback.replace("️", "")]

    if emoji_id:
        return f'<tg-emoji emoji_id="{emoji_id}">{fallback}</tg-emoji>'

    return fallback

def format_custom_emoji(emoji_id: str, fallback: str = "✨") -> str:
    """Explicitly format a custom emoji tag."""
    return f'<tg-emoji emoji_id="{emoji_id}">{fallback}</tg-emoji>'
