from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from functools import wraps
import requests
import json
import re
import time
import logging
from datetime import datetime
import hashlib
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIG
# ============================================================

API_URL = "https://sahil-33rd.onrender.com/api/leakpro"
API_KEY = "SAHILS"
DEVELOPER = "@DEVILHASHJ"
VERSION = "100X ULTIMATE"

# Users (in-memory)
users = {}

# Search history (per user)
search_history = {}

# Cache
cache = {}
CACHE_TTL = 3600

# Rate limiting
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
# AUTH ROUTES
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
        
        if email in users:
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        users[email] = {
            'password': generate_password_hash(password),
            'full_name': full_name,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        flash('✅ Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if email not in users:
            flash('Invalid credentials', 'error')
            return render_template('login.html')
        
        if not check_password_hash(users[email]['password'], password):
            flash('Invalid credentials', 'error')
            return render_template('login.html')
        
        session['user_id'] = email
        session['user_name'] = users[email]['full_name']
        flash(f'Welcome back, {users[email]["full_name"]}! 👋', 'success')
        return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

# ============================================================
# MAIN ROUTES
# ============================================================

@app.route('/')
def index():
    user = None
    if 'user_id' in session:
        user = {
            'email': session['user_id'],
            'name': session.get('user_name', 'User')
        }
    history = search_history.get(session.get('user_id'), []) if session.get('user_id') else []
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
    history = search_history.get(session['user_id'], [])
    return render_template('profile.html', user=user, history=history, developer=DEVELOPER)

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
        
        user_id = session.get('user_id')
        if user_id not in search_history:
            search_history[user_id] = []
        search_history[user_id].insert(0, {
            'query': query,
            'type': detect_type(query),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        search_history[user_id] = search_history[user_id][:20]
        
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
    user_id = session.get('user_id')
    history = search_history.get(user_id, [])
    return jsonify({'history': history})

@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    user_id = session.get('user_id')
    if user_id in search_history:
        search_history[user_id] = []
    return jsonify({'success': True})

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'version': VERSION,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/stats')
def stats():
    return jsonify({
        'cache_size': len(cache),
        'rate_limit_entries': len(rate_limit),
        'users': len(users)
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
    ║  ✅ Login/Register + Search + History                           ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)
