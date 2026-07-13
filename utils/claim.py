import json
import os
import time
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
    claims = _load_claims()
    str_id = str(user_id)
    now = int(time.time())
    last_claim = claims.get(str_id, 0)
    cooldown = 86400 # 24 hours
    
    elapsed = now - last_claim
    if elapsed >= cooldown:
        return True, 0
    return False, cooldown - elapsed

def record_claim(user_id: int):
    claims = _load_claims()
    claims[str(user_id)] = int(time.time())
    _save_claims(claims)
