import asyncio
from database.database import AsyncSessionLocal
from database.models import Character
from sqlalchemy import select

async def fix_broken():
    async with AsyncSessionLocal() as session:
        stmt = select(Character).where(
            (Character.image_url == "https://img.jpg") | 
            (Character.image_url == "http://img.jpg")
        )
        res = await session.execute(stmt)
        broken_chars = res.scalars().all()
        print(f"Found {len(broken_chars)} characters with broken 'https://img.jpg' URL in DB.")
        
        default_url = "https://images7.alphacoders.com/133/1331826.jpeg"
        for c in broken_chars:
            c.image_url = default_url
        
        await session.commit()
        print("Successfully updated broken URLs in DB to default working image!")

if __name__ == "__main__":
    asyncio.run(fix_broken())
