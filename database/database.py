from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import config

engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def init_db():
    # Import all models so Base.metadata is fully populated before create_all
    import database.models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.begin() as conn:
        try:
            await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bot_emojis (
                key VARCHAR(50) PRIMARY KEY,
                emoji VARCHAR(255) NOT NULL,
                updated_at TIMESTAMP
            )
            """))
        except Exception as e:
            print(f"Error creating bot_emojis table: {e}")

    # Safe dynamic column migrations
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_weekly TIMESTAMP"))
        except Exception:
            pass

    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_monthly TIMESTAMP"))
        except Exception:
            pass

    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_yearly TIMESTAMP"))
        except Exception:
            pass

    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE active_spawns ADD COLUMN message_id INTEGER"))
        except Exception:
            pass

    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE rarity_types ADD COLUMN claim_enabled BOOLEAN DEFAULT FALSE"))
        except Exception:
            pass

    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE rarity_types ADD COLUMN claim_weight INTEGER DEFAULT 10"))
        except Exception:
            pass

    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE group_settings ADD COLUMN auto_nameguess_enabled BOOLEAN DEFAULT FALSE"))
        except Exception:
            pass

    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_characters_user_id ON user_characters (user_id)"))
        except Exception:
            pass

    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE user_daily_limits ADD COLUMN rob_count INTEGER DEFAULT 0"))
        except Exception:
            pass

    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE user_daily_limits ADD COLUMN last_rob_at BIGINT DEFAULT 0"))
        except Exception:
            pass

    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_characters_character_id ON user_characters (character_id)"))
        except Exception:
            pass

    async with engine.begin() as conn:
        try:
            if "sqlite" in str(engine.url):
                await conn.execute(text("PRAGMA journal_mode=WAL;"))
                await conn.execute(text("PRAGMA synchronous=NORMAL;"))
        except Exception:
            pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
