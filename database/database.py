from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import config

# Supports both SQLite (local dev) and PostgreSQL (Railway production)
engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,       # Auto-reconnect on dropped connections
    pool_size=5,              # Max 5 persistent connections
    max_overflow=10,          # Up to 10 extra connections under load
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def init_db():
    """Create all tables if they don't exist. Works for both SQLite and PostgreSQL."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Safely alter tables to add new columns if they do not exist.
    # Note: Each alteration must run in its own transaction block (engine.begin()) 
    # to prevent PostgreSQL from aborting the entire block if one column already exists.
    
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
