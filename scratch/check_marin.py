import asyncio
from database.database import AsyncSessionLocal
from database.models import Character
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        stmt = select(Character).where(Character.name.ilike('%marin%'))
        res = await session.execute(stmt)
        for c in res.scalars().all():
            print(f"ID: {c.id} | Name: {repr(c.name)} | Anime: {c.anime}")

if __name__ == "__main__":
    asyncio.run(main())
