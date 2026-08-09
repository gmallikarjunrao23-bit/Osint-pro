from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)
Base = declarative_base()

# ============================================================
# MODELS
# ============================================================

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

# ============================================================
# DATABASE ENGINE — SQLITE ONLY
# ============================================================

# Force SQLite — ignore DATABASE_URL
DATABASE_URL = "sqlite:///osint.db"
engine = create_engine(
    DATABASE_URL,
    connect_args={'check_same_thread': False},
    echo=False
)
SessionLocal = sessionmaker(bind=engine)

# ============================================================
# INIT DATABASE — FORCE CREATE TABLES
# ============================================================

def init_db():
    """Force create all tables — fresh start"""
    try:
        logger.info("📦 Creating database tables...")
        Base.metadata.create_all(engine)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Database init failed: {e}")
        raise

# ============================================================
# RESET DATABASE — Drop and recreate (for clean start)
# ============================================================

def reset_db():
    """Drop all tables and recreate — USE WITH CAUTION"""
    try:
        logger.info("🔄 Resetting database...")
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        logger.info("✅ Database reset successful")
    except Exception as e:
        logger.error(f"❌ Database reset failed: {e}")
        raise

# ============================================================
# GET DB SESSION
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_session():
    return SessionLocal()

# ============================================================
# AUTO INIT ON IMPORT
# ============================================================

try:
    init_db()
except Exception as e:
    logger.error(f"❌ Auto init failed: {e}")
