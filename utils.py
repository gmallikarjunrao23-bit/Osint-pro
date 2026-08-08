import re
import time
import hashlib
import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import session, flash, redirect, url_for
from config import Config

def detect_type(query):
    """Detect query type: phone, email, domain, or username"""
    query = query.strip()
    if re.match(r'^\+?[0-9\s\-()]{7,20}$', query):
        return 'phone'
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', query):
        return 'email'
    if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', query):
        return 'domain'
    return 'username'

def get_emoji(field):
    """Get emoji for field type"""
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

def get_tier(tier):
    """Get tier info"""
    return Config.TIERS.get(tier, Config.TIERS['free'])

def process_data(raw_data, query):
    """Process raw API data into structured format"""
    processed, total = [], 0
    if not raw_data:
        return {'sources': [], 'total': 0}
    
    for key, src in raw_data.items():
        if not src:
            continue
        title = src.get('title', key.replace('_', ' ').title())
        desc = src.get('description', '')
        records = src.get('records', [])
        
        pr = []
        for rec in records:
            if isinstance(rec, dict):
                fields = []
                for k, v in rec.items():
                    if v and str(v).strip():
                        fields.append({'key': k, 'value': str(v), 'emoji': get_emoji(k)})
                if fields:
                    pr.append(fields)
                    total += len(fields)
            else:
                pr.append([{'key': 'data', 'value': str(rec), 'emoji': '📌'}])
                total += 1
        
        processed.append({
            'title': title,
            'description': desc[:300] + '...' if len(desc) > 300 else desc,
            'records': pr
        })
    
    return {'sources': processed, 'total': total, 'total_sources': len(processed)}

def generate_cache_key(query):
    """Generate cache key for a query"""
    return hashlib.md5(f"{query}_{Config.API_KEY}".encode()).hexdigest()

def generate_referral_code():
    """Generate unique referral code"""
    return str(uuid.uuid4())[:8].upper()

def can_search(user):
    """Check if user can perform a search"""
    if not user:
        return False, "User not found"
    
    tier_info = get_tier(user.tier)
    limit = tier_info['searches']
    
    if limit == -1:
        return True, "Unlimited"
    
    today = datetime.utcnow().date()
    if user.last_search_date and user.last_search_date.date() != today:
        user.searches_today = 0
    
    if user.searches_today >= limit:
        return False, f"Daily limit reached ({limit})"
    
    return True, "OK"

def sanitize_query(query):
    """Sanitize user query"""
    query = query.strip()
    if len(query) > Config.MAX_QUERY_LENGTH:
        query = query[:Config.MAX_QUERY_LENGTH]
    # Remove potentially dangerous characters
    query = re.sub(r'[<>{}()\[\]]', '', query)
    return query
