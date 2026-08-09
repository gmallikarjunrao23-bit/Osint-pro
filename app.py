from flask import Flask, render_template, request, jsonify
import requests
import json
import re
import time
import logging
from datetime import datetime
from functools import wraps
import hashlib

app = Flask(__name__)

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIG — 100X ULTIMATE
# ============================================================

API_URL = "https://sahil-33rd.onrender.com/api/leakpro"
API_KEY = "SAHILS"
DEVELOPER = "@DEVILHASHJ"
VERSION = "100X ULTIMATE"
SITE_NAME = "OSINT 100X"

# Cache
cache = {}
CACHE_TTL = 3600  # 1 hour

# Rate limiting
rate_limit = {}
RATE_LIMIT = 10  # requests per minute

# ============================================================
# DECORATORS
# ============================================================

def rate_limit_check(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = request.remote_addr
        now = time.time()
        if ip in rate_limit:
            requests = [t for t in rate_limit[ip] if now - t < 60]
            if len(requests) >= RATE_LIMIT:
                return jsonify({'error': 'Rate limit exceeded. Please wait a moment.'}), 429
            rate_limit[ip] = requests
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
                        logger.info(f"📦 Cache hit for: {query}")
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
    if 'tumblr' in title_lower: return '🌀'
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
    if 'aws' in title_lower or 'amazon' in title_lower: return '☁️'
    if 'azure' in title_lower: return '🔷'
    if 'gcp' in title_lower or 'google cloud' in title_lower: return '☁️'
    return '📁'

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
# ROUTES
# ============================================================

@app.route('/')
def index():
    return render_template('index.html', 
                         developer=DEVELOPER, 
                         version=VERSION,
                         site_name=SITE_NAME)

@app.route('/search', methods=['POST'])
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
        
        # Validate query length
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
        'cache_ttl': CACHE_TTL,
        'rate_limit': RATE_LIMIT
    })

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"500 Error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def rate_limit_error(e):
    return jsonify({'error': 'Too many requests. Please wait a moment.'}), 429

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║   ██████╗ ███████╗██╗███╗   ██╗████████╗    ██████╗ ██████╗   ║
    ║   ██╔══██╗██╔════╝██║████╗  ██║╚══██╔══╝   ██╔═══██╗██╔══██╗  ║
    ║   ██████╔╝███████╗██║██╔██╗ ██║   ██║      ██║   ██║██████╔╝  ║
    ║   ██╔══██╗╚════██║██║██║╚██╗██║   ██║      ██║   ██║██╔═══╝   ║
    ║   ██║  ██║███████║██║██║ ╚████║   ██║      ╚██████╔╝██║       ║
    ║   ╚═╝  ╚═╝╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝       ╚═════╝ ╚═╝       ║
    ║                                                                  ║
    ║   ██████╗ ██████╗   ██████╗                                    ║
    ║   ██╔══██╗██╔══██╗ ██╔═══██╗                                   ║
    ║   ██████╔╝██████╔╝ ██║   ██║                                   ║
    ║   ██╔══██╗██╔══██╗ ██║   ██║                                   ║
    ║   ██║  ██║██║  ██║ ╚██████╔╝                                   ║
    ║   ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═════╝                                    ║
    ║                                                                  ║
    ║   ╔══════════════════════════════════════════════════════════╗   ║
    ║   ║  🔥 100X ULTIMATE EDITION                              ║   ║
    ║   ║  💎 Powered by @DEVILHASHJ                             ║   ║
    ║   ║  🚀 Running on http://127.0.0.1:5000                   ║   ║
    ║   ╚══════════════════════════════════════════════════════════╝   ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)
