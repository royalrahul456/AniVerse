from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
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

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
