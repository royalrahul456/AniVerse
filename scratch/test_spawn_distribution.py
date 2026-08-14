from utils.emojis import get_emoji
import asyncio
from database.database import AsyncSessionLocal
from handlers.catch import get_random_character
from collections import Counter

async def test_simulation():
    async with AsyncSessionLocal() as session:
        counts = Counter()
        iterations = 1000
        for _ in range(iterations):
            char = await get_random_character(session)
            if char:
                counts[char.rarity.title()] += 1
        
        print(f"--- {get_emoji('target')} SPAWN SIMULATION RESULTS ({iterations} runs) ---")
        for rarity, count in counts.most_common():
            pct = (count / iterations) * 100
            print(f"{rarity}: {count} ({pct:.1f}%)")

if __name__ == "__main__":
    asyncio.run(test_simulation())
