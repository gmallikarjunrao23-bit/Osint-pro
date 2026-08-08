import os

class Config:
    # Railway variables
    SECRET_KEY = os.getenv("SECRET_KEY", "osint-pro-secure-key-2024")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///osint.db")
    
    # API
    API_URL = "https://sahil-33rd.onrender.com/api/leakpro"
    API_KEY = "SAHILS"
    API_TIMEOUT = 30
    API_RETRIES = 3
    
    # Branding
    DEVELOPER = "@DEVILHASHJ"
    VERSION = "3.0 ULTIMATE"
    SITE_NAME = "OSINT PRO"
    
    # UPI
    UPI_ID = "9866583926@axl"
    BANK_NAME = "Union Bank Of India"
    
    # Tiers
    TIERS = {
        'free': {
            'name': 'Free',
            'searches': 3,
            'export': False,
            'price': 0,
            'color': '#6b7280',
            'badge': '🆓',
            'desc': 'Basic access'
        },
        'premium': {
            'name': 'Premium',
            'searches': 100,
            'export': True,
            'price': 99,
            'color': '#7c3aed',
            'badge': '👑',
            'desc': 'Daily 100 searches'
        },
        'pro': {
            'name': 'Pro',
            'searches': -1,
            'export': True,
            'price': 299,
            'color': '#06b6d4',
            'badge': '⚡',
            'desc': 'Unlimited searches'
        },
        'enterprise': {
            'name': 'Enterprise',
            'searches': -1,
            'export': True,
            'price': 999,
            'color': '#10b981',
            'badge': '🏢',
            'desc': 'Full access + API'
        }
    }
    
    # Limits
    MAX_QUERY_LENGTH = 200
    CACHE_TTL = 3600  # seconds
    SESSION_LIFETIME = 30  # days
