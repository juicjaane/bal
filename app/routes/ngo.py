from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from ..services.firebase_service import get_db, get_bucket
from ..services.earth_engine import generate_mangrove_report, generate_air_quality_report
import logging
import datetime

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
                doc = db.collection('users').document(user_id).get()
                if doc.exists:
                    data = doc.to_dict()
                    area = data.get('area') or data.get('region') or area
            except Exception as e:
                logger.error(f"User area fetch: {e}")

        if report_type == 'mangrove':
            map_html, report_data = generate_mangrove_report(area)
            return render_template('ngo/insights.html',
                map_html=map_html, report_data=report_data, area=area, report_type='mangrove')
        else:
            chart, error = generate_air_quality_report(area)
            return render_template('ngo/insights.html',
                air_chart=chart, air_error=error, area=area, report_type='air')

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
            logger.error(f"Profile fetch: {e}")

    if request.method == 'POST' and db:
        updates = {
            'name': request.form.get('name', '').strip(),
            'address': request.form.get('address', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'website': request.form.get('website', '').strip(),
            'area': request.form.get('area', '').strip(),
            'mission': request.form.get('mission', '').strip(),
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


@ngo_bp.route('/alerts')
@ngo_required
def alerts():
    db = get_db()
    recent_alerts = []
    if db:
        try:
            docs = list(db.collection('alert_log')
                        .where('ngo_id', '==', session['user_id'])
                        .order_by('sent_at', direction='DESCENDING')
                        .limit(20).stream())
            recent_alerts = [{'id': d.id, **d.to_dict()} for d in docs]
        except Exception as e:
            logger.error(f"Alerts fetch: {e}")
    return render_template('ngo/alerts.html', alerts=recent_alerts)


@ngo_bp.route('/patch-health')
@ngo_required
def patch_health():
    db = get_db()
    user_data = {}
    health_data = None

    if db:
        try:
            doc = db.collection('users').document(session['user_id']).get()
            if doc.exists:
                user_data = doc.to_dict()
        except Exception as e:
            logger.error(f"Patch health fetch: {e}")

    area = user_data.get('area') or user_data.get('region') or 'India'
    try:
        from ..services.health_tracker import assess_patch_health
        health_data = assess_patch_health(area)
    except Exception as e:
        logger.error(f"Health assessment error: {e}")
        health_data = {'status': 'UNKNOWN', 'error': str(e)}

    return render_template('ngo/patch-health.html',
        health=health_data,
        area=area,
        user=user_data
    )


@ngo_bp.route('/carbon-report')
@ngo_required
def carbon_report():
    db = get_db()
    user_data = {}

    if db:
        try:
            doc = db.collection('users').document(session['user_id']).get()
            if doc.exists:
                user_data = doc.to_dict()
        except Exception as e:
            logger.error(f"Carbon report user fetch: {e}")

    area_km2 = float(user_data.get('mangrove_area_km2', 0) or 0)
    trees = int(user_data.get('trees_planted', 0) or 0)
    carbon_data = None

    try:
        from ..services.carbon_model import estimate_carbon, trees_to_carbon
        if area_km2 > 0:
            carbon_data = estimate_carbon(area_km2)
        elif trees > 0:
            carbon_data = trees_to_carbon(trees)
        else:
            carbon_data = estimate_carbon(1.0)  # 1 km² placeholder
            carbon_data['is_placeholder'] = True
    except Exception as e:
        logger.error(f"Carbon model error: {e}")

    # Fetch total donations received to show funded-carbon calculation
    total_donated = 0
    if db:
        try:
            docs = db.collection('donations').where('ngo_id', '==', session['user_id']).stream()
            total_donated = sum(d.to_dict().get('amount', 0) for d in docs)
        except Exception as e:
            logger.error(f"Donation fetch for carbon: {e}")

    return render_template('ngo/carbon-report.html',
        carbon=carbon_data,
        area_km2=area_km2,
        trees=trees,
        total_donated=total_donated,
        user=user_data
    )


@ngo_bp.route('/air-quality')
@ngo_required
def air_quality_correlation():
    db = get_db()
    user_data = {}

    if db:
        try:
            doc = db.collection('users').document(session['user_id']).get()
            if doc.exists:
                user_data = doc.to_dict()
        except Exception as e:
            logger.error(f"AQ user fetch: {e}")

    area = user_data.get('area') or user_data.get('region') or 'India'
    aq_chart = None
    aq_error = None
    ndvi_estimate = None

    # Try GEE air quality report first
    try:
        aq_chart, aq_error = generate_air_quality_report(area)
    except Exception as e:
        aq_error = str(e)

    # Also compute NDVI-based estimate
    try:
        from ..services.air_quality_correlator import assess_from_ndvi
        health_status = user_data.get('health_status', 'STABLE')
        ndvi_map = {'IMPROVING': 0.68, 'STABLE': 0.55, 'DECLINING': 0.38, 'UNKNOWN': 0.50}
        ndvi_val = ndvi_map.get(health_status, 0.55)
        ndvi_estimate = assess_from_ndvi(ndvi_val)
    except Exception as e:
        logger.error(f"NDVI AQ estimate: {e}")

    return render_template('ngo/air-quality-correlation.html',
        aq_chart=aq_chart,
        aq_error=aq_error,
        ndvi_estimate=ndvi_estimate,
        area=area,
        user=user_data
    )
