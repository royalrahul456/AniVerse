import asyncio
from database.database import init_db

async def test():
    await init_db()
    print("init_db completed successfully!")

if __name__ == "__main__":
    asyncio.run(test())
