from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS
from datetime import datetime, timedelta
import requests
import json
import re
import os
import hashlib
import logging
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from database import SessionLocal, User, Payment, SearchLog, init_db
from sqlalchemy import func, desc

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "osint-pro-secret-key-2024")
app.permanent_session_lifetime = timedelta(days=30)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIG
# ============================================================

API_URL = "https://sahil-3brd.onrender.com/api/leakpro"
API_KEY = "SAHILS"
DEVELOPER = "@DEVILHASHJ"
VERSION = "3.0 ULTIMATE"
UPI_ID = "9866583926@axl"
BANK_NAME = "Union Bank Of India"

TIERS = {
    'free': {'name': 'Free', 'searches': 10, 'export': False, 'price': 0, 'color': '#6b7280', 'badge': '🆓'},
    'premium': {'name': 'Premium', 'searches': 100, 'export': True, 'price': 99, 'color': '#7c3aed', 'badge': '👑'},
    'pro': {'name': 'Pro', 'searches': -1, 'export': True, 'price': 299, 'color': '#06b6d4', 'badge': '⚡'},
    'enterprise': {'name': 'Enterprise', 'searches': -1, 'export': True, 'price': 999, 'color': '#10b981', 'badge': '🏢'}
}

# ============================================================
# HELPERS
# ============================================================

def detect_type(query):
    query = query.strip()
    if re.match(r'^\+?[0-9\s\-()]{7,20}$', query):
        return "phone"
    elif re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', query):
        return "email"
    elif re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', query):
        return "domain"
    else:
        return "username"

def get_tier(tier):
    return TIERS.get(tier, TIERS['free'])

def get_emoji(field):
    f = field.lower()
    if 'phone' in f or 'mobile' in f: return '📱'
    if 'email' in f: return '✉️'
    if 'name' in f: return '📛'
    if 'address' in f or 'adres' in f: return '📍'
    if 'passport' in f or 'aadhar' in f or 'id' in f: return '🛂'
    if 'region' in f or 'state' in f: return '🗺️'
    if 'father' in f or 'mother' in f: return '👨'
    if 'username' in f: return '👤'
    if 'url' in f or 'link' in f: return '🔗'
    return '📌'

def process_data(raw_data):
    processed = []
    total_records = 0
    if not raw_data:
        return {'sources': [], 'total': 0}
    
    # Handle nested data
    if 'data' in raw_data and isinstance(raw_data['data'], dict):
        raw_data = raw_data['data']
    
    for key, src in raw_data.items():
        if not src:
            continue
        title = src.get('title', key.replace('_', ' ').title())
        desc = src.get('description', '')
        
        # Fix: API has 'record s' instead of 'records'
        records = src.get('records', [])
        if not records:
            records = src.get('record s', []) or src.get('record', [])
        
        pr = []
        for rec in records:
            if isinstance(rec, dict):
                fields = []
                for k, v in rec.items():
                    if v and str(v).strip():
                        fields.append({'key': k, 'value': str(v), 'emoji': get_emoji(k)})
                if fields:
                    pr.append(fields)
                    total_records += len(fields)
            else:
                pr.append([{'key': 'data', 'value': str(rec), 'emoji': '📌'}])
                total_records += 1
        processed.append({
            'title': title,
            'description': desc[:300] + '...' if len(desc) > 300 else desc,
            'records': pr
        })
    return {'sources': processed, 'total': total_records, 'total_sources': len(processed)}

# ============================================================
# DECORATORS
# ============================================================

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

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    user = None
    tier_info = None
    if 'user_id' in session:
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(user_id=session['user_id']).first()
            if user:
                tier_info = get_tier(user.tier)
        finally:
            db.close()
    return render_template('index.html', developer=DEVELOPER, version=VERSION,
                         user=user, tier_info=tier_info)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        if not email or not '@' in email:
            flash('Please enter a valid email', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
            return render_template('register.html')
        if not full_name:
            flash('Please enter your full name', 'error')
            return render_template('register.html')
        db = SessionLocal()
        try:
            existing = db.query(User).filter_by(user_id=email).first()
            if existing:
                flash('Email already registered', 'error')
                return render_template('register.html')
            hashed = generate_password_hash(password)
            ref_code = ''.join(__import__('random').choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=8))
            new_user = User(
                user_id=email,
                password=hashed,
                full_name=full_name,
                referral_code=ref_code
            )
            db.add(new_user)
            db.commit()
            flash('✅ Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.rollback()
            logger.error(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'error')
        finally:
            db.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(user_id=email).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.user_id
                session['user_name'] = user.full_name
                session['is_admin'] = user.is_admin
                session.permanent = True
                user.last_login = datetime.utcnow()
                db.commit()
                flash(f'Welcome back, {user.full_name}! 👋', 'success')
                return redirect(url_for('index'))
            flash('Invalid credentials', 'error')
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('Login failed. Please try again.', 'error')
        finally:
            db.close()
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(user_id=session['user_id']).first()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('login'))
        total = db.query(SearchLog).filter_by(user_id=user.user_id).count()
        today = db.query(SearchLog).filter(
            SearchLog.user_id == user.user_id,
            SearchLog.created_at >= datetime.utcnow().date()
        ).count()
        payments = db.query(Payment).filter_by(user_id=user.user_id).order_by(Payment.created_at.desc()).limit(5).all()
        tier_info = get_tier(user.tier)
        return render_template('profile.html', user=user, tier_info=tier_info,
                             total_searches=total, today_searches=today,
                             payments=payments, developer=DEVELOPER)
    except Exception as e:
        logger.error(f"Profile error: {e}")
        flash('Failed to load profile', 'error')
        return redirect(url_for('index'))
    finally:
        db.close()

@app.route('/payment')
@login_required
def payment():
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(user_id=session['user_id']).first()
        if not user:
            return redirect(url_for('login'))
        return render_template('payment.html', user=user, upi_id=UPI_ID,
                             bank=BANK_NAME, tiers=TIERS, developer=DEVELOPER)
    finally:
        db.close()

@app.route('/submit_payment', methods=['POST'])
@login_required
def submit_payment():
    tier = request.form.get('tier')
    transaction_id = request.form.get('transaction_id', '').strip()
    if tier not in TIERS:
        flash('Invalid tier selected', 'error')
        return redirect(url_for('payment'))
    if not transaction_id or len(transaction_id) < 4:
        flash('Please enter a valid transaction ID', 'error')
        return redirect(url_for('payment'))
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(user_id=session['user_id']).first()
        if not user:
            return redirect(url_for('login'))
        existing = db.query(Payment).filter_by(transaction_id=transaction_id).first()
        if existing:
            flash('Transaction ID already submitted', 'error')
            return redirect(url_for('payment'))
        payment = Payment(
            user_id=user.user_id,
            amount=TIERS[tier]['price'],
            tier=tier,
            transaction_id=transaction_id,
            screenshot_url='/static/uploads/pending.png',
            status='pending'
        )
        db.add(payment)
        db.commit()
        flash('✅ Payment submitted! Admin will verify within 24 hours.', 'success')
        return redirect(url_for('profile'))
    except Exception as e:
        db.rollback()
        logger.error(f"Submit payment error: {e}")
        flash('Failed to submit payment', 'error')
        return redirect(url_for('payment'))
    finally:
        db.close()

# ============================================================
# SEARCH ROUTE — 2x IMPROVED
# ============================================================

@app.route('/search', methods=['POST'])
@login_required
def search():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request'}), 400
        
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'Please enter a query'}), 400
        
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(user_id=session['user_id']).first()
            if not user:
                return jsonify({'error': 'User not found'}), 401
            
            tier_info = get_tier(user.tier)
            limit = tier_info['searches']
            today = datetime.utcnow().date()
            
            if user.last_search_date and user.last_search_date.date() != today:
                user.searches_today = 0
            
            if limit != -1 and user.searches_today >= limit:
                db.close()
                return jsonify({
                    'error': f'❌ Daily limit reached ({limit}). Upgrade to continue.',
                    'limit_reached': True
                }), 403
            
            user.searches_today += 1
            user.total_searches += 1
            user.last_search_date = datetime.utcnow()
            db.commit()
            
        finally:
            db.close()
        
        # Call API
        try:
            start_time = datetime.utcnow()
            
            logger.info(f"🔍 Searching: {query}")
            
            response = requests.get(
                API_URL,
                params={'key': API_KEY, 'number': query},
                timeout=30,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            response_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            logger.info(f"📦 API Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f'API Error: {response.status_code}'
                if response.text:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('message', error_msg)
                    except:
                        error_msg = response.text[:200]
                return jsonify({'error': error_msg}), 500
            
            result = response.json()
            
            logger.info(f"📦 API Response: {str(result)[:200]}...")
            
            # Extract data
            raw_data = result.get('data', {})
            
            # Check if data exists
            if not raw_data:
                return jsonify({
                    'success': True,
                    'data': {'sources': [], 'total': 0, 'total_sources': 0},
                    'query': query,
                    'type': detect_type(query),
                    'response_time': response_time,
                    'remaining': user.searches_today,
                    'limit': limit,
                    'tier': user.tier,
                    'message': 'No data found'
                })
            
            processed = process_data(raw_data)
            
            logger.info(f"📦 Processed: {processed['total_sources']} sources, {processed['total']} records")
            
            # Log search
            db = SessionLocal()
            try:
                log_entry = SearchLog(
                    user_id=user.user_id,
                    query=query,
                    result_count=processed['total'],
                    response_time=response_time
                )
                db.add(log_entry)
                db.commit()
            finally:
                db.close()
            
            return jsonify({
                'success': True,
                'data': processed,
                'query': query,
                'type': detect_type(query),
                'response_time': response_time,
                'remaining': user.searches_today,
                'limit': limit,
                'tier': user.tier,
                'api_status': response.status_code,
                'api_owner': result.get('owner', 'N/A'),
                'api_channel': result.get('channel', 'N/A')
            })
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout for {query}")
            return jsonify({'error': 'Request timeout. Please try again.'}), 504
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error for {query}")
            return jsonify({'error': 'Connection error. Please try again later.'}), 503
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return jsonify({'error': 'Invalid API response'}), 500
        except Exception as e:
            logger.error(f"API error: {e}")
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# ADMIN ROUTES
# ============================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(user_id=email).first()
            if user and check_password_hash(user.password, password) and user.is_admin:
                session['user_id'] = user.user_id
                session['is_admin'] = True
                flash('Welcome Admin!', 'success')
                return redirect(url_for('admin_dashboard'))
            flash('Invalid admin credentials', 'error')
        finally:
            db.close()
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db = SessionLocal()
    try:
        stats = {
            'users': db.query(User).count(),
            'premium': db.query(User).filter(User.tier != 'free').count(),
            'pending': db.query(Payment).filter_by(status='pending').count(),
            'revenue': db.query(func.sum(Payment.amount)).filter_by(status='approved').scalar() or 0,
            'today': db.query(SearchLog).filter(SearchLog.created_at >= datetime.utcnow().date()).count()
        }
        payments = db.query(Payment).order_by(Payment.created_at.desc()).limit(10).all()
        return render_template('admin/dashboard.html', stats=stats, payments=payments, version=VERSION)
    finally:
        db.close()

@app.route('/admin/approve/<int:pid>', methods=['POST'])
@admin_required
def approve_payment(pid):
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter_by(id=pid).first()
        if payment:
            payment.status = 'approved'
            payment.approved_at = datetime.utcnow()
            user = db.query(User).filter_by(user_id=payment.user_id).first()
            if user:
                user.tier = payment.tier
                if payment.tier in ['premium', 'pro', 'enterprise']:
                    user.premium_expiry = datetime.utcnow() + timedelta(days=30)
            db.commit()
            flash('✅ Payment approved!', 'success')
    except Exception as e:
        db.rollback()
        logger.error(f"Approve payment error: {e}")
        flash('Failed to approve payment', 'error')
    finally:
        db.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject/<int:pid>', methods=['POST'])
@admin_required
def reject_payment(pid):
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter_by(id=pid).first()
        if payment:
            payment.status = 'rejected'
            db.commit()
            flash('❌ Payment rejected', 'warning')
    except Exception as e:
        db.rollback()
        logger.error(f"Reject payment error: {e}")
        flash('Failed to reject payment', 'error')
    finally:
        db.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/users')
@admin_required
def admin_users():
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        return render_template('admin/users.html', users=users, tiers=TIERS)
    finally:
        db.close()

@app.route('/admin/upgrade/<user_id>', methods=['POST'])
@admin_required
def admin_upgrade(user_id):
    tier = request.form.get('tier')
    if tier not in TIERS:
        flash('Invalid tier', 'error')
        return redirect(url_for('admin_users'))
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(user_id=user_id).first()
        if user:
            user.tier = tier
            if tier in ['premium', 'pro', 'enterprise']:
                user.premium_expiry = datetime.utcnow() + timedelta(days=30)
            db.commit()
            flash(f'✅ {user.full_name} upgraded to {tier}', 'success')
    except Exception as e:
        db.rollback()
        logger.error(f"Upgrade user error: {e}")
        flash('Failed to upgrade user', 'error')
    finally:
        db.close()
    return redirect(url_for('admin_users'))

# ============================================================
# LIMIT RESET ROUTE (Admin only)
# ============================================================

@app.route('/admin/reset_limits', methods=['POST'])
@admin_required
def reset_limits():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        for u in users:
            u.searches_today = 0
            u.last_search_date = None
        db.commit()
        flash(f'✅ Reset limits for {len(users)} users', 'success')
    except Exception as e:
        db.rollback()
        logger.error(f"Reset limits error: {e}")
        flash('Failed to reset limits', 'error')
    finally:
        db.close()
    return redirect(url_for('admin_dashboard'))

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='404 - Page Not Found', description='The page you are looking for does not exist.'), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"500 Error: {e}")
    return render_template('error.html', error='500 - Server Error', description='Something went wrong. Please try again.'), 500

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
