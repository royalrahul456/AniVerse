import asyncio
from database.database import AsyncSessionLocal
from database.models import Character
from sqlalchemy import select

async def check_urls():
    async with AsyncSessionLocal() as session:
        stmt = select(Character)
        res = await session.execute(stmt)
        chars = res.scalars().all()
        print(f"Total characters: {len(chars)}")
        for c in chars:
            print(f"ID #{c.id:03d} | Name: '{c.name}' | URL: {c.image_url}")

if __name__ == "__main__":
    asyncio.run(check_urls())
