from aiohttp import web
from sqlalchemy import select, func
from database.database import AsyncSessionLocal
from database.models import User, UserCharacter, Character, RarityType
from utils.formatters import get_rarity_emoji
import logging

logger = logging.getLogger(__name__)

def cors_json_response(data, status=200):
    """Helper to return JSON responses with standard CORS headers."""
    return web.json_response(data, status=status, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    })

async def options_handler(request):
    """Preflight OPTIONS request handler for CORS."""
    return web.Response(status=200, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    })

async def get_user_profile_api(request):
    try:
        user_id_str = request.match_info.get("user_id")
        if not user_id_str or not user_id_str.isdigit():
            return cors_json_response({"error": "Invalid user ID"}, status=400)
        
        user_id = int(user_id_str)
        async with AsyncSessionLocal() as db:
            stmt = select(User).where(User.user_id == user_id)
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()
            
            if not user:
                return cors_json_response({"error": "User not found"}, status=404)
            
            # Count distinct characters owned
            count_stmt = select(func.count(UserCharacter.id)).where(UserCharacter.user_id == user_id)
            count_res = await db.execute(count_stmt)
            total_owned = count_res.scalar() or 0

            data = {
                "user_id": user.user_id,
                "first_name": user.first_name or "Trainer",
                "username": user.username or "",
                "coins": user.coins,
                "total_catches": user.total_catches,
                "custom_tag": user.premium_tag or "Novice Trainer",
                "total_owned": total_owned
            }
            return cors_json_response(data)
    except Exception as e:
        logger.error(f"Error in get_user_profile_api: {e}", exc_info=True)
        return cors_json_response({"error": str(e)}, status=500)

import time
LAST_REWARD_TIME = {}

async def post_game_reward_api(request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        game_id = data.get("game_id", "unknown")
        coins = data.get("coins", 0)

        if not user_id or not isinstance(coins, int):
            return cors_json_response({"error": "Invalid request parameters"}, status=400)

        # 1. Anti-Cheat: Cap coins per game round to 100
        if coins <= 0:
            return cors_json_response({"error": "Coins must be positive"}, status=400)
        if coins > 100:
            coins = 100  # Cap at max allowed

        # 2. Anti-Cheat: 15 seconds cooldown check per user
        current_time = time.time()
        last_time = LAST_REWARD_TIME.get(user_id, 0)
        if current_time - last_time < 15:
            return cors_json_response({"error": "Too fast! Please wait before claiming again."}, status=429)

        LAST_REWARD_TIME[user_id] = current_time

        # 3. Add coins to database user profile
        async with AsyncSessionLocal() as db:
            stmt = select(User).where(User.user_id == user_id)
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                return cors_json_response({"error": "User not found"}, status=404)

            user.coins += coins
            await db.commit()
            
            logger.info(f"User {user_id} earned {coins} coins in game '{game_id}'. New balance: {user.coins}")
            
            return cors_json_response({
                "success": True,
                "earned": coins,
                "coins": user.coins
            })
    except Exception as e:
        logger.error(f"Error in post_game_reward_api: {e}", exc_info=True)
        return cors_json_response({"error": str(e)}, status=500)
