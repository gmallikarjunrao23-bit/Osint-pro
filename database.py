from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import logging
from config import Config

logger = logging.getLogger(__name__)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), unique=True, nullable=False, index=True)
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
    user_id = Column(String(100), ForeignKey('users.user_id', ondelete='CASCADE'), index=True)
    amount = Column(Integer)
    tier = Column(String(20))
    transaction_id = Column(String(100), unique=True)
    screenshot_url = Column(String(500))
    status = Column(String(20), default='pending', index=True)
    admin_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime)
    user = relationship("User", back_populates="payments")

class SearchLog(Base):
    __tablename__ = 'search_logs'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), ForeignKey('users.user_id', ondelete='CASCADE'), index=True)
    query = Column(String(200))
    result_count = Column(Integer, default=0)
    response_time = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    user = relationship("User", back_populates="logs")

def get_engine():
    url = Config.DATABASE_URL
    try:
        if 'postgresql' in url:
            return create_engine(url, pool_size=10, max_overflow=20, pool_pre_ping=True)
        return create_engine(url, connect_args={'check_same_thread': False})
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

engine = get_engine()
SessionLocal = sessionmaker(bind=engine)

def init_db():
    try:
        Base.metadata.create_all(engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
