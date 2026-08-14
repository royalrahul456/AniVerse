import asyncio
import random
import config
from database.database import AsyncSessionLocal
from sqlalchemy import select
from database.models import Character, RarityType

async def select_random_character_test(db, custom_rarity=None):
    stmt = select(Character)
    res = await db.execute(stmt)
    characters = res.scalars().all()
    if not characters:
        return None

    if custom_rarity:
        selected_rarity = custom_rarity.title()
    else:
        # Build base rarity weight map from config
        weights_map = {r_name.title(): info["weight"] for r_name, info in config.RARITY_CONFIG.items()}

        # Merge DB enabled rarities
        db_rar_stmt = select(RarityType).where(RarityType.spawn_enabled == True)
        db_rarities = (await db.execute(db_rar_stmt)).scalars().all()
        for dr in db_rarities:
            weights_map[dr.name.title()] = dr.weight

        # Get set of actual existing rarities in DB
        available_rarities = list(set(c.rarity.title() for c in characters))

        choices = []
        weights = []
        for r in available_rarities:
            choices.append(r)
            weights.append(weights_map.get(r, 10))

        selected_rarity = random.choices(choices, weights=weights, k=1)[0]

    filtered = [c for c in characters if c.rarity.title() == selected_rarity]
    if not filtered:
        filtered = characters

    return random.choice(filtered)

async def run_simulation():
    async with AsyncSessionLocal() as db:
        counts = {}
        for _ in range(100):
            c = await select_random_character_test(db)
            key = f"{c.name} ({c.rarity})"
            counts[key] = counts.get(key, 0) + 1
        
        print(f"Simulated 100 character selections across DB ({len(counts)} unique characters picked):")
        for char_info, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {char_info}: {cnt} times")

if __name__ == "__main__":
    asyncio.run(run_simulation())
