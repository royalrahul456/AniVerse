import json
import os
import time
import datetime
from typing import Tuple

CLAIM_FILE = "data/claim_cooldowns.json"

def _load_claims() -> dict:
    if not os.path.exists(CLAIM_FILE):
        os.makedirs(os.path.dirname(CLAIM_FILE), exist_ok=True)
        with open(CLAIM_FILE, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(CLAIM_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_claims(claims: dict):
    os.makedirs(os.path.dirname(CLAIM_FILE), exist_ok=True)
    with open(CLAIM_FILE, "w") as f:
        json.dump(claims, f, indent=2)

def check_claim_cooldown(user_id: int) -> Tuple[bool, int]:
    """
    Checks if a user is eligible for their daily claim.
    The claim resets daily at 5:30 AM IST (UTC+5:30).
    Returns (can_claim, seconds_remaining)
    """
    claims = _load_claims()
    str_id = str(user_id)
    last_claim_ts = claims.get(str_id, 0)
    
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

def record_claim(user_id: int):
    claims = _load_claims()
    claims[str(user_id)] = int(time.time())
    _save_claims(claims)
