from flask import request, jsonify, render_template, session, flash, redirect, url_for
import logging
from datetime import datetime
from functools import wraps
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(404)
    def not_found(e):
        if request.is_json:
            return jsonify({'error': 'Not found'}), 404
        return render_template('error.html', error='404 - Page Not Found', description='The page you are looking for does not exist.'), 404
    
    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"500 Error: {e}")
        if request.is_json:
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('error.html', error='500 - Server Error', description='Something went wrong. Please try again later.'), 500
    
    @app.errorhandler(403)
    def forbidden(e):
        if request.is_json:
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('error.html', error='403 - Forbidden', description='You do not have permission to access this resource.'), 403
    
    @app.errorhandler(401)
    def unauthorized(e):
        if request.is_json:
            return jsonify({'error': 'Unauthorized'}), 401
        return render_template('error.html', error='401 - Unauthorized', description='Please login to access this page.'), 401
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        if request.is_json:
            return jsonify({'error': e.description}), e.code
        return render_template('error.html', error=f'{e.code} - {e.name}', description=e.description), e.code
    
    @app.errorhandler(Exception)
    def handle_general_exception(e):
        logger.error(f"Unhandled exception: {e}")
        if request.is_json:
            return jsonify({'error': 'An unexpected error occurred'}), 500
        return render_template('error.html', error='500 - Server Error', description='An unexpected error occurred. Please try again.'), 500

def rate_limit_middleware(limit=10, window=60):
    """Simple in-memory rate limiting"""
    requests = {}
    
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Skip for admin
            if session.get('is_admin'):
                return f(*args, **kwargs)
            
            # Identify user
            user_id = session.get('user_id') or request.remote_addr
            now = datetime.utcnow().timestamp()
            
            if user_id not in requests:
                requests[user_id] = []
            
            # Clean old requests
            cutoff = now - window
            requests[user_id] = [ts for ts in requests[user_id] if ts > cutoff]
            
            if len(requests[user_id]) >= limit:
                if request.is_json:
                    return jsonify({'error': 'Rate limit exceeded. Please wait a moment.'}), 429
                flash('Too many requests. Please wait a moment.', 'warning')
                return redirect(url_for('index'))
            
            requests[user_id].append(now)
            return f(*args, **kwargs)
        return decorated
    return decorator

def log_request(f):
    """Log all requests"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = session.get('user_id', 'anonymous')
        logger.info(f"Request: {request.method} {request.path} from {user}")
        return f(*args, **kwargs)
    return decorated
