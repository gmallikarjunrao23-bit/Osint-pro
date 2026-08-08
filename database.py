import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

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

def get_database_url():
    """Get DATABASE_URL from env, fallback to SQLite"""
    url = os.getenv("DATABASE_URL", "")
    
    # Remove quotes if present
    url = url.strip().strip('"').strip("'")
    
    # If empty or invalid, use SQLite
    if not url or url == '' or url == 'null' or url == 'None' or url.startswith('${'):
        logger.info("📦 No DATABASE_URL — using SQLite")
        return "sqlite:///osint.db"
    
    return url

def get_engine():
    """Create engine with proper settings"""
    url = get_database_url()
    logger.info(f"📦 Connecting to: {url[:50]}...")
    
    # SQLite
    if "sqlite" in url:
        return create_engine(
            url,
            connect_args={'check_same_thread': False},
            echo=False
        )
    
    # PostgreSQL
    try:
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

# ============================================================
# ENGINE & SESSION
# ============================================================

engine = get_engine()
SessionLocal = sessionmaker(bind=engine)

# ============================================================
# INIT DATABASE
# ============================================================

def init_db():
    """Create tables if not exist"""
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        
        if 'users' in inspector.get_table_names():
            logger.info("✅ Database already exists")
            return
        
        Base.metadata.create_all(engine)
        logger.info("✅ Database tables created")
        
    except Exception as e:
        logger.error(f"❌ Database init error: {e}")
        # Try SQLite fallback
        try:
            logger.info("🔄 Trying SQLite fallback...")
            fallback_engine = create_engine(
                "sqlite:///osint.db",
                connect_args={'check_same_thread': False},
                echo=False
            )
            Base.metadata.create_all(fallback_engine)
            global engine, SessionLocal
            engine = fallback_engine
            SessionLocal = sessionmaker(bind=engine)
            logger.info("✅ SQLite fallback successful")
        except Exception as e2:
            logger.error(f"❌ SQLite fallback failed: {e2}")
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
