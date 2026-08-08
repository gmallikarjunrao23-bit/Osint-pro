from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import logging
from database import SessionLocal, User, Payment, SearchLog
from config import Config
from auth import admin_required

logger = logging.getLogger(__name__)
admin = Blueprint('admin', __name__, url_prefix='/admin')

@admin.route('/')
@admin_required
def dashboard():
    db = SessionLocal()
    try:
        stats = {
            'users': db.query(func.count(User.id)).scalar() or 0,
            'premium': db.query(func.count(User.id)).filter(User.tier != 'free').scalar() or 0,
            'pending': db.query(func.count(Payment.id)).filter_by(status='pending').scalar() or 0,
            'revenue': db.query(func.sum(Payment.amount)).filter_by(status='approved').scalar() or 0,
            'today': db.query(func.count(SearchLog.id)).filter(SearchLog.created_at >= datetime.utcnow().date()).scalar() or 0
        }
        payments = db.query(Payment).order_by(Payment.created_at.desc()).limit(10).all()
        return render_template('admin/dashboard.html', stats=stats, payments=payments, version=Config.VERSION)
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        flash('Failed to load dashboard', 'error')
        return redirect(url_for('index'))
    finally:
        db.close()

@admin.route('/payments')
@admin_required
def payments():
    db = SessionLocal()
    try:
        all_payments = db.query(Payment).order_by(Payment.created_at.desc()).all()
        return render_template('admin/payments.html', payments=all_payments)
    except Exception as e:
        logger.error(f"Admin payments error: {e}")
        flash('Failed to load payments', 'error')
        return redirect(url_for('admin.dashboard'))
    finally:
        db.close()

@admin.route('/approve/<int:pid>', methods=['POST'])
@admin_required
def approve(pid):
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter_by(id=pid).first()
        if not payment:
            flash('Payment not found', 'error')
            return redirect(url_for('admin.payments'))
        
        payment.status = 'approved'
        payment.approved_at = datetime.utcnow()
        
        user = db.query(User).filter_by(user_id=payment.user_id).first()
        if user:
            user.tier = payment.tier
            if payment.tier in ['premium', 'pro', 'enterprise']:
                user.premium_expiry = datetime.utcnow() + timedelta(days=30)
            db.commit()
            flash(f'✅ Payment approved! {user.full_name} upgraded to {payment.tier}', 'success')
        else:
            db.commit()
            flash('Payment approved but user not found', 'warning')
    except Exception as e:
        db.rollback()
        logger.error(f"Approve payment error: {e}")
        flash('Failed to approve payment', 'error')
    finally:
        db.close()
    return redirect(url_for('admin.payments'))

@admin.route('/reject/<int:pid>', methods=['POST'])
@admin_required
def reject(pid):
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter_by(id=pid).first()
        if payment:
            payment.status = 'rejected'
            db.commit()
            flash('❌ Payment rejected', 'warning')
        else:
            flash('Payment not found', 'error')
    except Exception as e:
        db.rollback()
        logger.error(f"Reject payment error: {e}")
        flash('Failed to reject payment', 'error')
    finally:
        db.close()
    return redirect(url_for('admin.payments'))

@admin.route('/users')
@admin_required
def users():
    db = SessionLocal()
    try:
        all_users = db.query(User).order_by(User.created_at.desc()).all()
        return render_template('admin/users.html', users=all_users, tiers=Config.TIERS)
    except Exception as e:
        logger.error(f"Admin users error: {e}")
        flash('Failed to load users', 'error')
        return redirect(url_for('admin.dashboard'))
    finally:
        db.close()

@admin.route('/upgrade/<user_id>', methods=['POST'])
@admin_required
def upgrade(user_id):
    tier = request.form.get('tier')
    if tier not in Config.TIERS:
        flash('Invalid tier', 'error')
        return redirect(url_for('admin.users'))
    
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(user_id=user_id).first()
        if user:
            user.tier = tier
            if tier in ['premium', 'pro', 'enterprise']:
                user.premium_expiry = datetime.utcnow() + timedelta(days=30)
            db.commit()
            flash(f'✅ {user.full_name} upgraded to {tier}', 'success')
        else:
            flash('User not found', 'error')
    except Exception as e:
        db.rollback()
        logger.error(f"Upgrade user error: {e}")
        flash('Failed to upgrade user', 'error')
    finally:
        db.close()
    return redirect(url_for('admin.users'))

@admin.route('/stats')
@admin_required
def stats():
    db = SessionLocal()
    try:
        stats = []
        for i in range(7):
            date = datetime.utcnow().date() - timedelta(days=i)
            count = db.query(func.count(SearchLog.id)).filter(
                SearchLog.created_at >= date,
                SearchLog.created_at < date + timedelta(days=1)
            ).scalar() or 0
            stats.append({'date': date.strftime('%Y-%m-%d'), 'searches': count})
        return jsonify({'stats': stats})
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
