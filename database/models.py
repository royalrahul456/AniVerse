import datetime
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from database.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    coins = Column(Integer, default=500)
    daily_streak = Column(Integer, default=0)
    last_daily = Column(DateTime, nullable=True)
    total_catches = Column(Integer, default=0)
    favorite_character_id = Column(Integer, ForeignKey("characters.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    premium_until = Column(DateTime, nullable=True)
    premium_tag = Column(String(100), nullable=True)
    selected_theme = Column(String(50), default="default")
    unlocked_themes = Column(Text, default="default")

    characters = relationship("UserCharacter", back_populates="owner", cascade="all, delete-orphan")
    favorite_character = relationship("Character", foreign_keys=[favorite_character_id])

class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    anime = Column(String(255), nullable=False, index=True)
    rarity = Column(String(50), nullable=False, default="Common")
    image_url = Column(Text, nullable=True)

    user_characters = relationship("UserCharacter", back_populates="character")

class UserCharacter(Base):
    __tablename__ = "user_characters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False, index=True)
    nickname = Column(String(255), nullable=True)
    caught_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="characters")
    character = relationship("Character", back_populates="user_characters")

class RarityType(Base):
    __tablename__ = "rarity_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    emoji = Column(String(10), nullable=False, default="⚪")
    weight = Column(Integer, default=10)
    color = Column(String(50), default="Gray")
    spawn_enabled = Column(Boolean, default=False)
    claim_enabled = Column(Boolean, default=False)
    claim_weight = Column(Integer, default=10)
class ActiveSpawn(Base):
    __tablename__ = "active_spawns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False, unique=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    spawned_at = Column(DateTime, default=datetime.datetime.utcnow)

    character = relationship("Character")

class GroupSettings(Base):
    __tablename__ = "group_settings"

    chat_id = Column(BigInteger, primary_key=True, index=True)
    spawn_threshold = Column(Integer, default=10)
    message_counter = Column(Integer, default=0)
    spawns_enabled = Column(Boolean, default=True)
    auto_nameguess_enabled = Column(Boolean, default=False)
class ActiveGame(Base):
    __tablename__ = "active_games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    game_type = Column(String(50), nullable=False)
    data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class RedeemCode(Base):
    __tablename__ = "redeem_codes"

    code = Column(String(50), primary_key=True, index=True)
    reward_type = Column(String(50), nullable=False)  # "character" or "coins"
    reward_id = Column(Integer, ForeignKey("characters.id"), nullable=True)
    reward_amount = Column(Integer, nullable=True)
    max_uses = Column(Integer, nullable=False, default=1)
    uses_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    character = relationship("Character")

class RedeemUsage(Base):
    __tablename__ = "redeem_usages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    code = Column(String(50), ForeignKey("redeem_codes.code"), nullable=False)
    claimed_at = Column(DateTime, default=datetime.datetime.utcnow)

class Auction(Base):
    __tablename__ = "auctions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    user_character_id = Column(Integer, ForeignKey("user_characters.id"), nullable=False)
    starting_price = Column(Integer, nullable=False)
    current_bid = Column(Integer, nullable=False)
    highest_bidder_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    status = Column(String(50), default="pending")  # "pending", "active", "completed", "cancelled"
    started_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    chat_id = Column(BigInteger, nullable=True)
    message_id = Column(Integer, nullable=True)

    seller = relationship("User", foreign_keys=[seller_id])
    highest_bidder = relationship("User", foreign_keys=[highest_bidder_id])
    character = relationship("Character")
    user_character = relationship("UserCharacter")

class Bid(Base):
    __tablename__ = "bids"

    id = Column(Integer, primary_key=True, autoincrement=True)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)
    bidder_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    amount = Column(Integer, nullable=False)
    placed_at = Column(DateTime, default=datetime.datetime.utcnow)

    bidder = relationship("User")

class UserDailyLimit(Base):
    __tablename__ = "user_daily_limits"

    user_id = Column(BigInteger, primary_key=True, index=True)
    last_claim_at = Column(BigInteger, default=0)
    dice_count = Column(Integer, default=0)
    last_dice_at = Column(BigInteger, default=0)
    coinflip_count = Column(Integer, default=0)
    last_coinflip_at = Column(BigInteger, default=0)
    spin_count = Column(Integer, default=0)
    last_spin_at = Column(BigInteger, default=0)
    dart_count = Column(Integer, default=0)
    last_dart_at = Column(BigInteger, default=0)
    rob_count = Column(Integer, default=0)
    last_rob_at = Column(BigInteger, default=0)

class BotAdmin(Base):
    __tablename__ = "bot_admins"

    user_id = Column(BigInteger, primary_key=True, index=True)
    role = Column(String(50), nullable=False)  # "snradmin" or "jradmin"
    promoted_at = Column(DateTime, default=datetime.datetime.utcnow)

class BotEmoji(Base):
    __tablename__ = "bot_emojis"

    key = Column(String(50), primary_key=True, index=True)
    emoji = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
