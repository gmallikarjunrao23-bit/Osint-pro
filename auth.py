from flask import session, flash, redirect, url_for
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging
from database import SessionLocal, User
from utils import generate_referral_code

logger = logging.getLogger(__name__)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue', 'warning')
            return redirect(url_for('login'))
        
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(user_id=session['user_id']).first()
            if not user or not user.is_admin:
                flash('Admin access required', 'error')
                return redirect(url_for('index'))
        finally:
            db.close()
        
        return f(*args, **kwargs)
    return decorated

def register_user(email, password, full_name):
    """Register a new user"""
    db = SessionLocal()
    try:
        existing = db.query(User).filter_by(user_id=email).first()
        if existing:
            return {'success': False, 'error': 'Email already registered'}
        
        hashed = generate_password_hash(password)
        new_user = User(
            user_id=email,
            password=hashed,
            full_name=full_name,
            referral_code=generate_referral_code()
        )
        db.add(new_user)
        db.commit()
        return {'success': True, 'user': new_user}
    except Exception as e:
        db.rollback()
        logger.error(f"Registration error: {e}")
        return {'success': False, 'error': 'Registration failed'}
    finally:
        db.close()

def login_user(email, password):
    """Login user"""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(user_id=email).first()
        if user and check_password_hash(user.password, password):
            user.last_login = datetime.utcnow()
            db.commit()
            return {'success': True, 'user': user}
        return {'success': False, 'error': 'Invalid credentials'}
    except Exception as e:
        logger.error(f"Login error: {e}")
        return {'success': False, 'error': 'Login failed'}
    finally:
        db.close()

def get_current_user():
    """Get current logged-in user"""
    if 'user_id' not in session:
        return None
    
    db = SessionLocal()
    try:
        return db.query(User).filter_by(user_id=session['user_id']).first()
    except Exception as e:
        logger.error(f"Get user error: {e}")
        return None
    finally:
        db.close()

def update_user_tier(user_id, tier):
    """Update user tier"""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(user_id=user_id).first()
        if user:
            user.tier = tier
            if tier in ['premium', 'pro', 'enterprise']:
                from datetime import timedelta
                user.premium_expiry = datetime.utcnow() + timedelta(days=30)
            db.commit()
            return {'success': True}
        return {'success': False, 'error': 'User not found'}
    except Exception as e:
        db.rollback()
        logger.error(f"Update tier error: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        db.close()
