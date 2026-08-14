import asyncio
from database.database import AsyncSessionLocal
from database.models import Character
from sqlalchemy import select

async def check_all():
    async with AsyncSessionLocal() as session:
        stmt = select(Character)
        res = await session.execute(stmt)
        chars = res.scalars().all()
        print(f"Total characters in DB: {len(chars)}")
        for c in chars[:25]:
            img = c.image_url or "NONE"
            print(f"ID #{c.id} | Name: '{c.name}' | Rarity: '{c.rarity}' | Img: '{img}'")

if __name__ == "__main__":
    asyncio.run(check_all())
