from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from ..services.firebase_service import get_db, get_bucket
from ..services.earth_engine import generate_mangrove_report, generate_air_quality_report
import logging, datetime

logger = logging.getLogger(__name__)
ngo_bp = Blueprint('ngo', __name__, url_prefix='/ngo')

def ngo_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'ngo':
            flash('Please log in as an NGO to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@ngo_bp.route('/')
@ngo_required
def home():
    db = get_db()
    user_id = session['user_id']
    donations_count = 0
    total_donated = 0
    recent_donations = []
    
    if db:
        try:
            donations = list(db.collection('donations').where('ngo_id', '==', user_id).stream())
            donations_count = len(donations)
            total_donated = sum(d.to_dict().get('amount', 0) for d in donations)
            recent_donations = sorted(
                [{'id': d.id, **d.to_dict()} for d in donations],
                key=lambda x: x.get('created_at', ''), reverse=True
            )[:5]
        except Exception as e:
            logger.error(f"Donations fetch error: {e}")
    
    return render_template('ngo/home.html',
        user_name=session.get('user_name', 'NGO'),
        donations_count=donations_count,
        total_donated=total_donated,
        recent_donations=recent_donations
    )

@ngo_bp.route('/insights', methods=['GET', 'POST'])
@ngo_required
def insights():
    if request.method == 'POST':
        db = get_db()
        user_id = session['user_id']
        report_type = request.form.get('report_type', 'mangrove')
        
        area = 'Sundarbans, India'
        if db:
            try:
                user_doc = db.collection('users').document(user_id).get()
                if user_doc.exists:
                    area = user_doc.to_dict().get('area', area)
            except Exception as e:
                logger.error(f"User area fetch error: {e}")
        
        if report_type == 'mangrove':
            map_html, report_data = generate_mangrove_report(area)
            return render_template('ngo/insights.html', map_html=map_html, report_data=report_data, area=area, report_type='mangrove')
        else:
            chart, error = generate_air_quality_report(area)
            return render_template('ngo/insights.html', air_chart=chart, air_error=error, area=area, report_type='air')
    
    return render_template('ngo/insights.html')

@ngo_bp.route('/donations')
@ngo_required
def donations():
    db = get_db()
    donations_list = []
    total = 0
    
    if db:
        try:
            docs = db.collection('donations').where('ngo_id', '==', session['user_id']).stream()
            donations_list = sorted(
                [{'id': d.id, **d.to_dict()} for d in docs],
                key=lambda x: x.get('created_at', ''), reverse=True
            )
            total = sum(d.get('amount', 0) for d in donations_list)
        except Exception as e:
            logger.error(f"Donations error: {e}")
    
    return render_template('ngo/donations.html', donations=donations_list, total=total)

@ngo_bp.route('/profile', methods=['GET', 'POST'])
@ngo_required
def profile():
    db = get_db()
    user_data = {}
    
    if db:
        try:
            doc = db.collection('users').document(session['user_id']).get()
            if doc.exists:
                user_data = doc.to_dict()
        except Exception as e:
            logger.error(f"Profile fetch error: {e}")
    
    if request.method == 'POST' and db:
        updates = {
            'name': request.form.get('name', '').strip(),
            'address': request.form.get('address', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'website': request.form.get('website', '').strip(),
            'area': request.form.get('area', '').strip(),
        }
        updates = {k: v for k, v in updates.items() if v}
        if updates:
            try:
                db.collection('users').document(session['user_id']).update(updates)
                if 'name' in updates:
                    session['user_name'] = updates['name']
                flash('Profile updated successfully.', 'success')
                return redirect(url_for('ngo.profile'))
            except Exception as e:
                flash(f'Update failed: {e}', 'danger')
    
    return render_template('ngo/profile.html', user=user_data)
