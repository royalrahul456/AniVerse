import datetime
import time
from typing import Tuple
from sqlalchemy import select
from database.models import UserDailyLimit

async def check_game_limit(db, user_id: int, game_type: str, max_limit: int) -> Tuple[bool, int, int]:
    """
    Checks if a user is under the daily limit for a game.
    Daily reset is at 5:30 AM IST (UTC+5:30).
    Returns (can_play, current_count, seconds_remaining_until_reset)
    """
    stmt = select(UserDailyLimit).where(UserDailyLimit.user_id == user_id)
    res = await db.execute(stmt)
    limit = res.scalar_one_or_none()
    
    count = 0
    last_play_ts = 0
    
    if limit:
        if game_type == "dice":
            count = limit.dice_count
            last_play_ts = limit.last_dice_at
        elif game_type == "coinflip":
            count = limit.coinflip_count
            last_play_ts = limit.last_coinflip_at
        elif game_type == "spin":
            count = limit.spin_count
            last_play_ts = limit.last_spin_at
        elif game_type == "dart":
            count = limit.dart_count
            last_play_ts = limit.last_dart_at
            
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
    
    if last_play_dt < last_reset:
        count = 0
        
    remaining_seconds = int((next_reset - now).total_seconds())
    
    if count >= max_limit:
        return False, count, remaining_seconds
        
    return True, count, 0

async def record_game_play(db, user_id: int, game_type: str):
    stmt = select(UserDailyLimit).where(UserDailyLimit.user_id == user_id)
    res = await db.execute(stmt)
    limit = res.scalar_one_or_none()
    
    # IST timezone
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = datetime.datetime.now(ist_tz)
    today_reset = now.replace(hour=5, minute=30, second=0, microsecond=0)
    
    if now < today_reset:
        last_reset = today_reset - datetime.timedelta(days=1)
    else:
        last_reset = today_reset
        
    if not limit:
        limit = UserDailyLimit(user_id=user_id)
        db.add(limit)
        
    if game_type == "dice":
        last_play_dt = datetime.datetime.fromtimestamp(limit.last_dice_at, tz=ist_tz)
        limit.dice_count = 1 if last_play_dt < last_reset else limit.dice_count + 1
        limit.last_dice_at = int(time.time())
    elif game_type == "coinflip":
        last_play_dt = datetime.datetime.fromtimestamp(limit.last_coinflip_at, tz=ist_tz)
        limit.coinflip_count = 1 if last_play_dt < last_reset else limit.coinflip_count + 1
        limit.last_coinflip_at = int(time.time())
    elif game_type == "spin":
        last_play_dt = datetime.datetime.fromtimestamp(limit.last_spin_at, tz=ist_tz)
        limit.spin_count = 1 if last_play_dt < last_reset else limit.spin_count + 1
        limit.last_spin_at = int(time.time())
    elif game_type == "dart":
        last_play_dt = datetime.datetime.fromtimestamp(limit.last_dart_at, tz=ist_tz)
        limit.dart_count = 1 if last_play_dt < last_reset else limit.dart_count + 1
        limit.last_dart_at = int(time.time())
        
    await db.commit()
