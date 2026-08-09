from flask import Flask, render_template, request, jsonify
import requests
import json
import re
import time
import logging
from datetime import datetime

app = Flask(__name__)

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIG
# ============================================================

API_URL = "https://sahil-3brd.onrender.com/api/leakpro"
API_KEY = "SAHILS"
DEVELOPER = "@DEVILHASHJ"
VERSION = "10X ULTIMATE"

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
# FORMAT OUTPUT — 10X CLEAN
# ============================================================

def format_output(query, processed, response_time):
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
    
    for src in processed['sources']:
        source_data = {
            'title': src['title'],
            'description': src['description'],
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
    return render_template('index.html', developer=DEVELOPER, version=VERSION)

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request'}), 400
        
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'Please enter a query'}), 400
        
        logger.info(f"🔍 Searching: {query}")
        
        start_time = time.time()
        response = requests.get(
            API_URL,
            params={'key': API_KEY, 'number': query},
            timeout=30,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        response_time = int((time.time() - start_time) * 1000)
        
        logger.info(f"📦 API Status: {response.status_code}")
        
        if response.status_code != 200:
            error_msg = f'API Error: {response.status_code}'
            try:
                error_data = response.json()
                error_msg = error_data.get('message', error_msg)
            except:
                pass
            return jsonify({'error': error_msg}), 500
        
        result = response.json()
        logger.info(f"📦 API Response OK")
        
        raw_data = result.get('data', {})
        processed = process_data(raw_data)
        
        logger.info(f"📦 Processed: {processed['total_sources']} sources, {processed['total']} records")
        
        output = format_output(query, processed, response_time)
        output['api_owner'] = result.get('owner', 'N/A')
        output['api_channel'] = result.get('channel', 'N/A')
        
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
        return jsonify({'error': str(e)}), 500

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

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  🔥 OSINT 10X ULTIMATE 🔥                               ║
    ║  💎 Powered by @DEVILHASHJ                              ║
    ║  🚀 Running on http://127.0.0.1:5000                    ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)
