from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime
import requests
import time
import logging
from config import Config
from database import init_db, SessionLocal, User, Payment, SearchLog
from auth import login_required, admin_required, register_user, login_user, get_current_user, update_user_tier
from utils import detect_type, get_tier, process_data, can_search, sanitize_query, generate_cache_key
from admin import admin as admin_blueprint
from middleware import register_error_handlers, rate_limit_middleware, log_request

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Init app
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = Config.SESSION_LIFETIME
app.config['JSON_SORT_KEYS'] = False

# Register blueprints
app.register_blueprint(admin_blueprint)

# Register error handlers
register_error_handlers(app)

# Init database
try:
    init_db()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Database init failed: {e}")

# Simple cache
cache = {}

# ============ ROUTES ============

@app.route('/')
@log_request
def index():
    user = get_current_user()
    tier_info = get_tier(user.tier) if user else None
    return render_template('index.html', 
                         developer=Config.DEVELOPER, 
                         version=Config.VERSION,
                         site_name=Config.SITE_NAME,
                         user=user, 
                         tier_info=tier_info)

@app.route('/register', methods=['GET', 'POST'])
@log_request
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        
        # Validation
        if not email or not '@' in email:
            flash('Please enter a valid email', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
            return render_template('register.html')
        if not full_name:
            flash('Please enter your full name', 'error')
            return render_template('register.html')
        
        result = register_user(email, password, full_name)
        if result['success']:
            flash('✅ Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash(result.get('error', 'Registration failed'), 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
@log_request
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Please fill all fields', 'error')
            return render_template('login.html')
        
        result = login_user(email, password)
        if result['success']:
            user = result['user']
            session['user_id'] = user.user_id
            session['user_name'] = user.full_name
            session['is_admin'] = user.is_admin
            session.permanent = True
            
            flash(f'Welcome back, {user.full_name}! 👋', 'success')
            return redirect(url_for('index'))
        else:
            flash(result.get('error', 'Login failed'), 'error')
    
    return render_template('login.html')

@app.route('/logout')
@log_request
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
@log_request
def profile():
    user = get_current_user()
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('login'))
    
    db = SessionLocal()
    try:
        total = db.query(SearchLog).filter_by(user_id=user.user_id).count()
        today = db.query(SearchLog).filter(
            SearchLog.user_id == user.user_id,
            SearchLog.created_at >= datetime.utcnow().date()
        ).count()
        payments = db.query(Payment).filter_by(user_id=user.user_id).order_by(Payment.created_at.desc()).limit(5).all()
        tier_info = get_tier(user.tier)
        return render_template('profile.html', user=user, tier_info=tier_info, 
                             total_searches=total, today_searches=today,
                             payments=payments, developer=Config.DEVELOPER)
    except Exception as e:
        logger.error(f"Profile error: {e}")
        flash('Failed to load profile', 'error')
        return redirect(url_for('index'))
    finally:
        db.close()

@app.route('/payment')
@login_required
@log_request
def payment():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('payment.html', user=user, upi_id=Config.UPI_ID, 
                         bank=Config.BANK_NAME, tiers=Config.TIERS, developer=Config.DEVELOPER)

@app.route('/submit_payment', methods=['POST'])
@login_required
@log_request
def submit_payment():
    tier = request.form.get('tier')
    transaction_id = request.form.get('transaction_id', '').strip()
    
    if tier not in Config.TIERS:
        flash('Invalid tier selected', 'error')
        return redirect(url_for('payment'))
    
    if not transaction_id or len(transaction_id) < 4:
        flash('Please enter a valid transaction ID', 'error')
        return redirect(url_for('payment'))
    
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    db = SessionLocal()
    try:
        # Check if transaction ID already used
        existing = db.query(Payment).filter_by(transaction_id=transaction_id).first()
        if existing:
            flash('Transaction ID already submitted', 'error')
            return redirect(url_for('payment'))
        
        payment = Payment(
            user_id=user.user_id,
            amount=Config.TIERS[tier]['price'],
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

@app.route('/search', methods=['POST'])
@login_required
@rate_limit_middleware(limit=20, window=60)
@log_request
def search():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400
    
    query = sanitize_query(data.get('query', ''))
    if not query:
        return jsonify({'error': 'Please enter a query'}), 400
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    # Check limits
    can, msg = can_search(user)
    if not can:
        return jsonify({
            'error': f'❌ {msg}',
            'limit_reached': True,
            'tier': user.tier,
            'limit': get_tier(user.tier)['searches']
        }), 403
    
    # Update usage
    db = SessionLocal()
    try:
        today = datetime.utcnow().date()
        if user.last_search_date and user.last_search_date.date() != today:
            user.searches_today = 0
        user.searches_today += 1
        user.total_searches += 1
        user.last_search_date = datetime.utcnow()
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Update usage error: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        db.close()
    
    # Check cache
    cache_key = generate_cache_key(query)
    if cache_key in cache:
        cached = cache[cache_key]
        if (datetime.now() - cached['time']).seconds < Config.CACHE_TTL:
            cached_data = cached['data'].copy()
            cached_data['cached'] = True
            cached_data['remaining'] = user.searches_today
            cached_data['limit'] = get_tier(user.tier)['searches']
            return jsonify(cached_data)
    
    # Call API
    try:
        start_time = time.time()
        response = requests.get(
            Config.API_URL,
            params={'key': Config.API_KEY, 'number': query},
            timeout=Config.API_TIMEOUT,
            headers={'User-Agent': 'OSINT-Pro/3.0'}
        )
        response_time = int((time.time() - start_time) * 1000)
        
        if response.status_code != 200:
            logger.warning(f"API error: {response.status_code} for {query}")
            return jsonify({
                'error': f'API Error: {response.status_code}',
                'details': response.text[:200] if response.text else ''
            }), 500
        
        result = response.json()
        raw_data = result.get('data', {})
        processed = process_data(raw_data, query)
        
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
        except Exception as e:
            db.rollback()
            logger.error(f"Log search error: {e}")
        finally:
            db.close()
        
        response_data = {
            'success': True,
            'data': processed,
            'query': query,
            'type': detect_type(query),
            'response_time': response_time,
            'remaining': user.searches_today,
            'limit': get_tier(user.tier)['searches'],
            'tier': user.tier,
            'cached': False
        }
        
        # Cache
        cache[cache_key] = {'data': response_data, 'time': datetime.now()}
        
        return jsonify(response_data)
        
    except requests.exceptions.Timeout:
        logger.error(f"API timeout for {query}")
        return jsonify({'error': 'Request timeout. Please try again.'}), 504
    except requests.exceptions.ConnectionError:
        logger.error(f"API connection error for {query}")
        return jsonify({'error': 'Connection error. Please try again later.'}), 503
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

# ============ MAIN ============
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
