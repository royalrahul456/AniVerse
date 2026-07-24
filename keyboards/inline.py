from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Tuple
import config
def get_dm_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Generates the primary Hub menu keyboard for DMs in AniVerse."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎮 Launch Harem App", web_app=WebAppInfo(url=config.MINI_APP_URL))
    )
    builder.row(
        InlineKeyboardButton(text="👤 Profile", callback_data="dm_profile"),
        InlineKeyboardButton(text="🏆 AnimeDex", callback_data="dm_dex_All_1")
    )
    builder.row(        InlineKeyboardButton(text="🎒 Harem / Bag", callback_data="dm_bag_All_1"),
        InlineKeyboardButton(text="📊 Leaderboard", callback_data="dm_leaderboard")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Trade", callback_data="dm_trade_info"),
        InlineKeyboardButton(text="🎁 Redeem", callback_data="dm_redeem_info")
    )
    builder.row(
        InlineKeyboardButton(text="🛂 Shop", callback_data="dm_shop"),
        InlineKeyboardButton(text="🎮 Games Center", callback_data="dm_games")
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Streak", callback_data="dm_streak"),
        InlineKeyboardButton(text="❓ Guide", callback_data="dm_help")
    )
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="🛠️ Admin Tools", callback_data="admin_tools")
        )
    return builder.as_markup()

def get_games_keyboard() -> InlineKeyboardMarkup:
    """Generates the Games Center selection menu."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎰 Lucky Spin", callback_data="game_spin"),
        InlineKeyboardButton(text="🧠 Anime Trivia", callback_data="game_trivia")
    )
    builder.row(
        InlineKeyboardButton(text="🎲 Dice Bet", callback_data="game_dice"),
        InlineKeyboardButton(text="🎯 Dart Arena", callback_data="game_dart")
    )
    builder.row(
        InlineKeyboardButton(text="🪙 Coinflip", callback_data="game_coinflip"),
        InlineKeyboardButton(text="💣 Mines", callback_data="game_mines")
    )
    builder.row(
        InlineKeyboardButton(text="🧩 Word Scramble", callback_data="game_scramble")
    )
    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))
    return builder.as_markup()

def get_harem_keyboard(user_id: int, page: int, max_page: int, rarity: str = "All", sort_by: str = "anime") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Collection 🔄", switch_inline_query_current_chat=f"collection.{user_id}"),
        InlineKeyboardButton(text="💌 AMV 🔄", switch_inline_query_current_chat=f"collection.{user_id}.AMV")
    )
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"dm_bag_{rarity}_{page-1}_{sort_by}"))
    nav_row.append(InlineKeyboardButton(text=f"{page}/{max_page}", callback_data="noop"))
    if page < max_page:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"dm_bag_{rarity}_{page+1}_{sort_by}"))
    builder.row(*nav_row)
 
    builder.row(
        InlineKeyboardButton(text="🔍 Filter Rarity", callback_data=f"dm_bag_rarity_menu_{sort_by}")
    )
    return builder.as_markup()

def get_harem_sorting_keyboard(rarity: str, page: int, current_sort: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    modes = [("anime", "📺 Anime"), ("id", "🆔 ID"), ("name", "📛 Name"), ("rarity", "💮 Rarity")]
    buttons = []
    for key, label in modes:
        tick = " ✅" if current_sort.lower() == key else ""
        buttons.append(InlineKeyboardButton(text=f"{label}{tick}", callback_data=f"dm_bag_{rarity}_1_{key}"))
    
    builder.row(buttons[0], buttons[1])
    builder.row(buttons[2], buttons[3])
    builder.row(InlineKeyboardButton(text="🔙 Back to Harem", callback_data=f"dm_bag_{rarity}_{page}_{current_sort}"))
    return builder.as_markup()

def get_showcase_keyboard(user_id: int, mode: str, page: int, max_page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"harem_{mode}_{user_id}_{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page}/{max_page}", callback_data="noop"))
    if page < max_page:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"harem_{mode}_{user_id}_{page+1}"))
    builder.row(*nav_row)
    builder.row(InlineKeyboardButton(text="🔙 Back to Harem", callback_data="dm_bag_All_1"))
    return builder.as_markup()

def get_list_pagination_keyboard(cmd_prefix: str, query_str: str, page: int, max_page: int) -> InlineKeyboardMarkup:
    """Generates clean Prev/Next inline pagination for /anime and /search."""
    builder = InlineKeyboardBuilder()
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"{cmd_prefix}_{query_str}_{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page}/{max_page}", callback_data="noop"))
    if page < max_page:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"{cmd_prefix}_{query_str}_{page+1}"))
    builder.row(*nav_row)
    return builder.as_markup()


def get_check_character_keyboard(char_id: int) -> InlineKeyboardMarkup:
    """Generates the 'Who Has It' button for /check."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Who Has It", callback_data=f"who_has_{char_id}"))
    return builder.as_markup()

def get_check_back_keyboard(char_id: int) -> InlineKeyboardMarkup:
    """Generates the 'Back' button for /check owners page."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data=f"check_back_{char_id}"))
    return builder.as_markup()

def get_rarity_selection_menu_keyboard(rarity_items: List[Tuple[str, str]], sort_by: str = "anime") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = []
    for r_code, r_label in rarity_items:
        buttons.append(InlineKeyboardButton(text=r_label, callback_data=f"dm_bag_{r_code}_1_{sort_by}"))
    for i in range(0, len(buttons), 2):
        builder.row(*buttons[i:i+2])
    builder.row(InlineKeyboardButton(text="🔙 Back to Harem", callback_data=f"dm_bag_All_1_{sort_by}"))
    return builder.as_markup()

def get_back_to_hub_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))
    return builder.as_markup()

def get_profile_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎨 Themes", callback_data="cb_themes_menu"),
        InlineKeyboardButton(text="🎒 Harem", callback_data="dm_bag_All_1")
    )
    builder.row(
        InlineKeyboardButton(text="🎮 Launch Harem App", web_app=WebAppInfo(url=config.MINI_APP_URL))
    )
    return builder.as_markup()
def get_leaderboard_keyboard(current_category: str) -> InlineKeyboardMarkup:
    import config
    builder = InlineKeyboardBuilder()
    currency_name = getattr(config, "CURRENCY_NAME", "Gold")
    currency_emoji = getattr(config, "CURRENCY_EMOJI", "🪙")
    categories = [
        ("coins", f"{currency_emoji} Top {currency_name}"),
        ("catches", "⚡ Top Snatches"),
        ("premium", "👑 Premium")
    ]
    buttons = []
    for key, label in categories:
        tick = " ✅" if current_category.lower() == key else ""
        buttons.append(InlineKeyboardButton(text=f"{label}{tick}", callback_data=f"dm_leaderboard_{key}"))
    builder.row(buttons[0], buttons[1])
    builder.row(buttons[2])
    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))
    return builder.as_markup()
