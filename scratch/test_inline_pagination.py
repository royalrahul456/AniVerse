import asyncio
from database.database import AsyncSessionLocal
from sqlalchemy import select, func
from database.models import User, UserCharacter, Character

async def test_all_queries():
    async with AsyncSessionLocal() as db:
        # Test 1: Global search with empty query
        limit = 25
        offset = 0
        stmt1 = select(Character).order_by(Character.id).offset(offset).limit(limit)
        res1 = (await db.execute(stmt1)).scalars().all()
        next1 = str(offset + limit) if len(res1) == limit else ""
        print(f"Global Search (offset=0, limit=25): Count={len(res1)}, NextOffset='{next1}'")

        # Test 2: Collection search for existing user
        user_stmt = select(User.user_id).limit(1)
        user_id = (await db.execute(user_stmt)).scalar()
        if user_id:
            stmt2 = (
                select(Character, func.count(UserCharacter.id).label("cnt"))
                .join(UserCharacter, UserCharacter.character_id == Character.id)
                .where(UserCharacter.user_id == user_id)
                .group_by(Character.id)
                .order_by(Character.id)
                .offset(offset)
                .limit(limit)
            )
            res2 = (await db.execute(stmt2)).all()
            next2 = str(offset + limit) if len(res2) == limit else ""
            print(f"User Collection (user_id={user_id}, offset=0, limit=25): Count={len(res2)}, NextOffset='{next2}'")

if __name__ == "__main__":
    asyncio.run(test_all_queries())
