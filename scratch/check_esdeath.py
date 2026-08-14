import asyncio
from database.database import AsyncSessionLocal
from database.models import Character
from sqlalchemy import select

async def check_esdeath():
    async with AsyncSessionLocal() as session:
        stmt = select(Character).where(Character.name.ilike("%esdeath%"))
        res = await session.execute(stmt)
        chars = res.scalars().all()
        print(f"Found {len(chars)} Esdeath characters:")
        for c in chars:
            img = c.image_url or "NONE"
            print(f"ID #{c.id} | Name: '{c.name}' | Rarity: '{c.rarity}' | Img: '{img[:30]}...' (Len: {len(img)})")

if __name__ == "__main__":
    asyncio.run(check_esdeath())
