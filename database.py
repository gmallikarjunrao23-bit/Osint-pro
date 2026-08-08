from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)
Base = declarative_base()

# === User Model ===
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), unique=True, nullable=False)
    password = Column(String(200), nullable=False)
    full_name = Column(String(100))
    tier = Column(String(20), default='free')
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    total_searches = Column(Integer, default=0)
    searches_today = Column(Integer, default=0)
    last_search_date = Column(DateTime)
    premium_expiry = Column(DateTime)
    referral_code = Column(String(20), unique=True)
    referred_by = Column(String(100))
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    logs = relationship("SearchLog", back_populates="user", cascade="all, delete-orphan")

class Payment(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), ForeignKey('users.user_id', ondelete='CASCADE'))
    amount = Column(Integer)
    tier = Column(String(20))
    transaction_id = Column(String(100), unique=True)
    screenshot_url = Column(String(500))
    status = Column(String(20), default='pending')
    admin_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime)
    user = relationship("User", back_populates="payments")

class SearchLog(Base):
    __tablename__ = 'search_logs'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), ForeignKey('users.user_id', ondelete='CASCADE'))
    query = Column(String(200))
    result_count = Column(Integer, default=0)
    response_time = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="logs")

# === DATABASE ENGINE — FIXED ===
def get_database_url():
    """Get DATABASE_URL from env, fallback to SQLite"""
    url = os.getenv("DATABASE_URL", "")
    if not url or url == "" or url.startswith("${"):
        logger.warning("⚠️ DATABASE_URL empty — using SQLite fallback")
        return "sqlite:///osint.db"
    return url

def get_engine():
    url = get_database_url()
    
    # SQLite — special handling
    if "sqlite" in url:
        logger.info(f"📦 Using SQLite: {url}")
        return create_engine(
            url,
            connect_args={'check_same_thread': False},
            echo=False
        )
    
    # PostgreSQL
    try:
        logger.info(f"📦 Using PostgreSQL")
        return create_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False
        )
    except Exception as e:
        logger.error(f"❌ PostgreSQL failed: {e}")
        logger.info("🔄 Falling back to SQLite")
        return create_engine(
            "sqlite:///osint.db",
            connect_args={'check_same_thread': False},
            echo=False
        )

engine = get_engine()
SessionLocal = sessionmaker(bind=engine)

def init_db():
    try:
        Base.metadata.create_all(engine)
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database init failed: {e}")
        raise
