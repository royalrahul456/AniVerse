import datetime
import time
from typing import Tuple
from sqlalchemy import select
from database.models import UserDailyLimit

async def check_claim_cooldown(db, user_id: int) -> Tuple[bool, int]:
    """
    Checks if a user is eligible for their daily claim.
    The claim resets daily at 5:30 AM IST (UTC+5:30).
    Returns (can_claim, seconds_remaining)
    """
    stmt = select(UserDailyLimit).where(UserDailyLimit.user_id == user_id)
    res = await db.execute(stmt)
    limit = res.scalar_one_or_none()
    
    last_claim_ts = limit.last_claim_at if limit else 0
    
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
        
    last_claim_dt = datetime.datetime.fromtimestamp(last_claim_ts, tz=ist_tz)
    
    if last_claim_dt < last_reset:
        return True, 0
        
    remaining_seconds = int((next_reset - now).total_seconds())
    return False, remaining_seconds

async def record_claim(db, user_id: int):
    stmt = select(UserDailyLimit).where(UserDailyLimit.user_id == user_id)
    res = await db.execute(stmt)
    limit = res.scalar_one_or_none()
    
    if not limit:
        limit = UserDailyLimit(user_id=user_id, last_claim_at=int(time.time()))
        db.add(limit)
    else:
        limit.last_claim_at = int(time.time())
        
    await db.commit()
