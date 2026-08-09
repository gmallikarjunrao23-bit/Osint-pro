from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from functools import wraps
import requests
import re
import time
import logging
from datetime import datetime
import hashlib
import os
from werkzeug.security import generate_password_hash, check_password_hash
from database import SessionLocal, User, Payment, SearchLog, init_db

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize database
init_db()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIG
# ============================================================

API_URL = "https://sahil-33rd.onrender.com/api/leakpro"
API_KEY = "SAHILS"
DEVELOPER = "@DEVILHASHJ"
VERSION = "100X ULTIMATE"

# Cache (in-memory for performance)
cache = {}
CACHE_TTL = 3600
rate_limit = {}
RATE_LIMIT = 10

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

def rate_limit_check(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = request.remote_addr
        now = time.time()
        if ip in rate_limit:
            requests_list = [t for t in rate_limit[ip] if now - t < 60]
            if len(requests_list) >= RATE_LIMIT:
                return jsonify({'error': 'Rate limit exceeded. Please wait.'}), 429
            rate_limit[ip] = requests_list
        else:
            rate_limit[ip] = []
        rate_limit[ip].append(now)
        return f(*args, **kwargs)
    return decorated

def cache_response(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'POST':
            data = request.get_json()
            query = data.get('query', '').strip() if data else ''
            if query:
                cache_key = hashlib.md5(f"{query}_{API_KEY}".encode()).hexdigest()
                if cache_key in cache:
                    cached = cache[cache_key]
                    if (time.time() - cached['time']) < CACHE_TTL:
                        return jsonify(cached['data'])
                result = f(*args, **kwargs)
                if result.status_code == 200:
                    try:
                        data = result.get_json()
                        cache[cache_key] = {'data': data, 'time': time.time()}
                    except:
                        pass
                return result
        return f(*args, **kwargs)
    return decorated

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

def get_platform_emoji(title):
    title_lower = title.lower()
    if 'facebook' in title_lower: return '📘'
    if 'instagram' in title_lower: return '📸'
    if 'twitter' in title_lower or 'x' in title_lower: return '🐦'
    if 'linkedin' in title_lower: return '💼'
    if 'github' in title_lower: return '🐙'
    if 'google' in title_lower: return '🔴'
    if 'microsoft' in title_lower: return '🟦'
    if 'apple' in title_lower: return '🍎'
    if 'amazon' in title_lower: return '🛒'
    if 'netflix' in title_lower: return '🎬'
    if 'spotify' in title_lower: return '🎵'
    if 'youtube' in title_lower: return '▶️'
    if 'reddit' in title_lower: return '🤖'
    if 'discord' in title_lower: return '💬'
    if 'telegram' in title_lower: return '✈️'
    if 'whatsapp' in title_lower: return '💚'
    if 'signal' in title_lower: return '🔵'
    if 'tiktok' in title_lower: return '🎵'
    if 'snapchat' in title_lower: return '👻'
    if 'pinterest' in title_lower: return '📌'
    if 'vimeo' in title_lower: return '🎥'
    if 'dailymotion' in title_lower: return '🎬'
    if 'flickr' in title_lower: return '📷'
    if 'imgur' in title_lower: return '🖼️'
    if 'deviantart' in title_lower: return '🎨'
    if 'behance' in title_lower: return '💼'
    if 'dribbble' in title_lower: return '🏀'
    if 'medium' in title_lower: return '📝'
    if 'substack' in title_lower: return '📧'
    if 'quora' in title_lower: return '❓'
    if 'stackoverflow' in title_lower: return '📚'
    if 'gitlab' in title_lower: return '🦊'
    if 'bitbucket' in title_lower: return '🔷'
    if 'docker' in title_lower: return '🐳'
    if 'heroku' in title_lower: return '⚡'
    if 'netlify' in title_lower: return '🚀'
    if 'vercel' in title_lower: return '▲'
    if 'cloudflare' in title_lower: return '☁️'
    return '📢'

def process_data(raw_data):
    processed = []
    total_records = 0
    if not raw_data:
        return {'sources': [], 'total': 0}
    
    if 'data' in raw_data and isinstance(raw_data['data'], dict):
        raw_data = raw_data['data']
    
    for key, src in raw_data.items():
        if not src:
            continue
        title = src.get('title', key.replace('_', ' ').title())
        desc = src.get('description', '')
        records = src.get('records', [])
        if not records:
            records = src.get('record s', []) or src.get('record', [])
        
        platform_emoji = get_platform_emoji(title)
        
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
            'description': desc[:500] + '...' if len(desc) > 500 else desc,
            'records': pr,
            'platform_emoji': platform_emoji
        })
    return {'sources': processed, 'total': total_records, 'total_sources': len(processed)}

def format_output(query, processed, response_time, api_owner=None, api_channel=None):
    output = {
        'success': True,
        'query': query,
        'type': detect_type(query),
        'response_time': response_time,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_sources': processed['total_sources'],
        'total_records': processed['total'],
        'sources': []
    }
    
    if api_owner:
        output['api_owner'] = api_owner
    if api_channel:
        output['api_channel'] = api_channel
    
    for src in processed['sources']:
        source_data = {
            'title': src['title'],
            'description': src['description'],
            'platform_emoji': src['platform_emoji'],
            'fields': []
        }
        for record in src['records']:
            for field in record:
                source_data['fields'].append({
                    'label': field['key'],
                    'value': field['value'],
                    'emoji': field['emoji']
                })
        output['sources'].append(source_data)
    
    return output

# ============================================================
# AUTH ROUTES — WITH DATABASE
# ============================================================

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
                db.close()
                return render_template('register.html')
            
            hashed = generate_password_hash(password)
            import random
            ref_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=8))
            
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
            if not user:
                flash('Invalid credentials', 'error')
                db.close()
                return render_template('login.html')
            
            if not check_password_hash(user.password, password):
                flash('Invalid credentials', 'error')
                db.close()
                return render_template('login.html')
            
            session['user_id'] = user.user_id
            session['user_name'] = user.full_name
            flash(f'Welcome back, {user.full_name}! 👋', 'success')
            return redirect(url_for('index'))
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

# ============================================================
# MAIN ROUTES — WITH DATABASE
# ============================================================

@app.route('/')
def index():
    user = None
    if 'user_id' in session:
        user = {
            'email': session['user_id'],
            'name': session.get('user_name', 'User')
        }
    
    # Get user's search history from database
    history = []
    if 'user_id' in session:
        db = SessionLocal()
        try:
            user_obj = db.query(User).filter_by(user_id=session['user_id']).first()
            if user_obj:
                logs = db.query(SearchLog).filter_by(user_id=user_obj.user_id).order_by(SearchLog.created_at.desc()).limit(10).all()
                history = [{'query': l.query, 'type': detect_type(l.query), 'records': l.result_count, 'timestamp': l.created_at.strftime('%Y-%m-%d %H:%M:%S') if l.created_at else ''} for l in logs]
        except Exception as e:
            logger.error(f"Index history error: {e}")
        finally:
            db.close()
    
    return render_template('index.html', 
                         developer=DEVELOPER, 
                         version=VERSION,
                         user=user,
                         history=history)

@app.route('/profile')
@login_required
def profile():
    user = {
        'email': session['user_id'],
        'name': session.get('user_name', 'User')
    }
    
    db = SessionLocal()
    try:
        user_obj = db.query(User).filter_by(user_id=session['user_id']).first()
        total_searches = db.query(SearchLog).filter_by(user_id=user_obj.user_id).count()
        today = datetime.now().date()
        today_searches = db.query(SearchLog).filter(
            SearchLog.user_id == user_obj.user_id,
            SearchLog.created_at >= today
        ).count()
    except Exception as e:
        logger.error(f"Profile error: {e}")
        total_searches = 0
        today_searches = 0
    finally:
        db.close()
    
    return render_template('profile.html', 
                         user=user, 
                         total_searches=total_searches,
                         today_searches=today_searches,
                         developer=DEVELOPER)

@app.route('/search', methods=['POST'])
@login_required
@rate_limit_check
@cache_response
def search():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request'}), 400
        
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'Please enter a query'}), 400
        
        if len(query) > 200:
            return jsonify({'error': 'Query too long. Maximum 200 characters.'}), 400
        
        logger.info(f"🔍 Searching: {query}")
        
        start_time = time.time()
        response = requests.get(
            API_URL,
            params={'key': API_KEY, 'number': query},
            timeout=30,
            headers={
                'User-Agent': 'OSINT-100X/1.0',
                'Accept': 'application/json'
            }
        )
        response_time = int((time.time() - start_time) * 1000)
        
        logger.info(f"📦 API Status: {response.status_code}")
        
        if response.status_code != 200:
            error_msg = f'API Error: {response.status_code}'
            try:
                error_data = response.json()
                error_msg = error_data.get('message', error_msg)
            except:
                error_msg = response.text[:200] if response.text else error_msg
            return jsonify({'error': error_msg}), 500
        
        result = response.json()
        logger.info(f"📦 API Response OK")
        
        raw_data = result.get('data', {})
        processed = process_data(raw_data)
        
        logger.info(f"📦 Processed: {processed['total_sources']} sources, {processed['total']} records")
        
        # Save to database
        db = SessionLocal()
        try:
            user_obj = db.query(User).filter_by(user_id=session['user_id']).first()
            if user_obj:
                log_entry = SearchLog(
                    user_id=user_obj.user_id,
                    query=query,
                    result_count=processed['total'],
                    response_time=response_time
                )
                db.add(log_entry)
                db.commit()
        except Exception as e:
            logger.error(f"Save search log error: {e}")
        finally:
            db.close()
        
        output = format_output(
            query, 
            processed, 
            response_time,
            result.get('owner'),
            result.get('channel')
        )
        
        return jsonify(output)
        
    except requests.exceptions.Timeout:
        logger.error("Request timeout")
        return jsonify({'error': 'Request timeout. Please try again.'}), 504
    except requests.exceptions.ConnectionError:
        logger.error("Connection error")
        return jsonify({'error': 'Connection error. Please try again later.'}), 503
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return jsonify({'error': 'Invalid API response'}), 500
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/history')
@login_required
def history():
    db = SessionLocal()
    try:
        user_obj = db.query(User).filter_by(user_id=session['user_id']).first()
        logs = db.query(SearchLog).filter_by(user_id=user_obj.user_id).order_by(SearchLog.created_at.desc()).limit(50).all()
        history = [{'query': l.query, 'type': detect_type(l.query), 'records': l.result_count, 'timestamp': l.created_at.strftime('%Y-%m-%d %H:%M:%S') if l.created_at else ''} for l in logs]
        return jsonify({'history': history})
    except Exception as e:
        logger.error(f"History error: {e}")
        return jsonify({'history': []})
    finally:
        db.close()

@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    db = SessionLocal()
    try:
        user_obj = db.query(User).filter_by(user_id=session['user_id']).first()
        db.query(SearchLog).filter_by(user_id=user_obj.user_id).delete()
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        logger.error(f"Clear history error: {e}")
        return jsonify({'success': False})
    finally:
        db.close()

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'version': VERSION,
        'timestamp': datetime.now().isoformat()
    })

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='404', description='Page not found'), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"500 Error: {e}")
    return render_template('error.html', error='500', description='Internal server error'), 500

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║  🔥 OSINT 100X ULTIMATE 🔥                                      ║
    ║  💎 Powered by @DEVILHASHJ                                      ║
    ║  🚀 Running on http://127.0.0.1:5000                            ║
    ║  ✅ Database Enabled (SQLite)                                   ║
    ║  ✅ Login/Register + Search + History                           ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)
