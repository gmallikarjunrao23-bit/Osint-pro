from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
import logging
import re

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
# DATABASE ENGINE — SQLITE DEFAULT
# ============================================================

def clean_db_url(url):
    if not url:
        return None
    url = url.strip()
    url = url.strip('"').strip("'")
    if not url or url == '' or url == 'null' or url == 'None':
        return None
    return url

def get_database_url():
    raw_url = os.getenv("DATABASE_URL", "")
    clean_url = clean_db_url(raw_url)
    
    if clean_url is None:
        logger.info("📦 No DATABASE_URL found — using SQLite")
        return "sqlite:///osint.db"
    
    if clean_url.startswith("postgresql://") or clean_url.startswith("postgres://"):
        logger.info("📦 Using PostgreSQL database")
        return clean_url
    
    if "sqlite" in clean_url:
        logger.info("📦 Using SQLite database")
        return clean_url
    
    logger.warning(f"⚠️ Unknown database URL format: {clean_url[:30]}... using SQLite")
    return "sqlite:///osint.db"

def create_engine_safe(url):
    if "sqlite" in url:
        return create_engine(
            url,
            connect_args={'check_same_thread': False},
            echo=False
        )
    
    if "postgresql" in url or "postgres" in url:
        try:
            return create_engine(
                url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                connect_args={'sslmode': 'require'},
                echo=False
            )
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            logger.info("🔄 Falling back to SQLite")
            return create_engine(
                "sqlite:///osint.db",
                connect_args={'check_same_thread': False},
                echo=False
            )
    
    return create_engine(
        "sqlite:///osint.db",
        connect_args={'check_same_thread': False},
        echo=False
    )

# ============================================================
# ENGINE & SESSION
# ============================================================

database_url = get_database_url()
engine = create_engine_safe(database_url)
SessionLocal = sessionmaker(bind=engine)

# ============================================================
# INIT DATABASE
# ============================================================

def init_db():
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        if 'users' in inspector.get_table_names():
            logger.info("✅ Database already initialized")
            return
        Base.metadata.create_all(engine)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Database init error: {e}")
        try:
            logger.info("🔄 Attempting SQLite fallback...")
            fallback_engine = create_engine(
                "sqlite:///osint.db",
                connect_args={'check_same_thread': False},
                echo=False
            )
            Base.metadata.create_all(fallback_engine)
            logger.info("✅ SQLite fallback successful")
        except Exception as e2:
            logger.error(f"❌ SQLite fallback also failed: {e2}")
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
