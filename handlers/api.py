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

async def get_user_harem_api(request):
    try:
        user_id_str = request.match_info.get("user_id")
        if not user_id_str or not user_id_str.isdigit():
            return cors_json_response({"error": "Invalid user ID"}, status=400)
        
        user_id = int(user_id_str)
        async with AsyncSessionLocal() as db:
            # Query user characters and character metadata
            stmt = (
                select(Character, func.count(UserCharacter.id).label("cnt"))
                .join(UserCharacter, UserCharacter.character_id == Character.id)
                .where(UserCharacter.user_id == user_id)
                .group_by(Character.id)
                .order_by(Character.id)
            )
            res = await db.execute(stmt)
            rows = res.all()
            
            harem_list = []
            for char, count in rows:
                r_emoji = get_rarity_emoji(char.rarity)
                harem_list.append({
                    "id": char.id,
                    "name": char.name,
                    "anime": char.anime,
                    "rarity": char.rarity,
                    "rarity_emoji": r_emoji,
                    "image_url": char.image_url,
                    "count": count
                })
            
            return cors_json_response({"harem": harem_list})
    except Exception as e:
        logger.error(f"Error in get_user_harem_api: {e}", exc_info=True)
        return cors_json_response({"error": str(e)}, status=500)
