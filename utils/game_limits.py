import json
import os
import time
import datetime
from typing import Tuple

LIMIT_FILE = "data/game_limits.json"

def _load_limits() -> dict:
    if not os.path.exists(LIMIT_FILE):
        os.makedirs(os.path.dirname(LIMIT_FILE), exist_ok=True)
        with open(LIMIT_FILE, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(LIMIT_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_limits(limits: dict):
    os.makedirs(os.path.dirname(LIMIT_FILE), exist_ok=True)
    with open(LIMIT_FILE, "w") as f:
        json.dump(limits, f, indent=2)

def check_game_limit(user_id: int, game_type: str, max_limit: int) -> Tuple[bool, int, int]:
    """
    Checks if a user is under the daily limit for a game.
    Daily reset is at 5:30 AM IST (UTC+5:30).
    Returns (can_play, current_count, seconds_remaining_until_reset)
    """
    limits = _load_limits()
    str_id = str(user_id)
    user_data = limits.get(str_id, {})
    game_data = user_data.get(game_type, {"count": 0, "last_play": 0})
    
    last_play_ts = game_data.get("last_play", 0)
    count = game_data.get("count", 0)
    
    # IST timezone (UTC+5:30)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = datetime.datetime.now(ist_tz)
    
    # Daily reset is at 5:30 AM IST
    today_reset = now.replace(hour=5, minute=30, second=0, microsecond=0)
    
    if now < today_reset:
        # Before 5:30 AM today, so last reset was yesterday 5:30 AM IST
        last_reset = today_reset - datetime.timedelta(days=1)
        next_reset = today_reset
    else:
        # After 5:30 AM today, so last reset was today 5:30 AM IST
        last_reset = today_reset
        next_reset = today_reset + datetime.timedelta(days=1)
        
    last_play_dt = datetime.datetime.fromtimestamp(last_play_ts, tz=ist_tz)
    
    # If the last play was before the last reset time, count resets to 0
    if last_play_dt < last_reset:
        count = 0
        
    remaining_seconds = int((next_reset - now).total_seconds())
    
    if count >= max_limit:
        return False, count, remaining_seconds
        
    return True, count, 0

def record_game_play(user_id: int, game_type: str):
    limits = _load_limits()
    str_id = str(user_id)
    if str_id not in limits:
        limits[str_id] = {}
        
    user_data = limits[str_id]
    game_data = user_data.get(game_type, {"count": 0, "last_play": 0})
    
    last_play_ts = game_data.get("last_play", 0)
    count = game_data.get("count", 0)
    
    # IST timezone
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = datetime.datetime.now(ist_tz)
    today_reset = now.replace(hour=5, minute=30, second=0, microsecond=0)
    
    if now < today_reset:
        last_reset = today_reset - datetime.timedelta(days=1)
    else:
        last_reset = today_reset
        
    last_play_dt = datetime.datetime.fromtimestamp(last_play_ts, tz=ist_tz)
    
    if last_play_dt < last_reset:
        count = 1
    else:
        count += 1
        
    user_data[game_type] = {
        "count": count,
        "last_play": int(time.time())
    }
    
    _save_limits(limits)
