from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from functools import wraps
from ..services.firebase_service import get_db, get_bucket
import logging
import datetime

logger = logging.getLogger(__name__)
corporate_bp = Blueprint('corporate', __name__, url_prefix='/corporate')


def corporate_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'company':
            flash('Please log in as a Corporate to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@corporate_bp.route('/')
@corporate_required
def home():
    db = get_db()
    total_donated = 0
    ngos_supported = 0
    recent_donations = []

    if db:
        try:
            docs = list(db.collection('donations').where('donor_id', '==', session['user_id']).stream())
            total_donated = sum(d.to_dict().get('amount', 0) for d in docs)
            ngo_ids = set(d.to_dict().get('ngo_id') for d in docs)
            ngos_supported = len(ngo_ids)
            recent_donations = sorted(
                [{'id': d.id, **d.to_dict()} for d in docs],
                key=lambda x: x.get('created_at', ''), reverse=True
            )[:5]
        except Exception as e:
            logger.error(f"Corporate stats: {e}")

    trees_funded = int(total_donated / 10)
    carbon_offset = round(total_donated * 0.0067, 1)

    return render_template('corporate/home.html',
        user_name=session.get('user_name', 'Corporate'),
        total_donated=total_donated,
        ngos_supported=ngos_supported,
        trees_funded=trees_funded,
        carbon_offset=carbon_offset,
        recent_donations=recent_donations,
        discover_url=url_for('corporate.discover')
    )


@corporate_bp.route('/donate')
@corporate_required
def donate():
    db = get_db()
    ngos = []
    if db:
        try:
            docs = db.collection('users').where('type', '==', 'ngo').stream()
            ngos = [{'id': doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            logger.error(f"NGO fetch: {e}")
    return render_template('corporate/donate.html', ngos=ngos)


@corporate_bp.route('/process-donation', methods=['POST'])
@corporate_required
def process_donation():
    db = get_db()
    if not db:
        flash('Donation service unavailable.', 'danger')
        return redirect(url_for('corporate.donate'))

    ngo_id = request.form.get('ngo_id')
    ngo_name = request.form.get('ngo_name', '')
    amount_raw = request.form.get('amount', '0')

    try:
        amount = float(amount_raw)
        if amount <= 0:
            raise ValueError("Amount must be positive")

        db.collection('donations').add({
            'donor_id': session['user_id'],
            'donor_name': session.get('user_name'),
            'ngo_id': ngo_id,
            'ngo_name': ngo_name,
            'amount': amount,
            'currency': 'INR',
            'status': 'completed',
            'created_at': datetime.datetime.utcnow().isoformat(),
        })

        flash(f'Donation of ₹{amount:,.0f} to {ngo_name} recorded successfully!', 'success')
        return redirect(url_for('corporate.impact'))
    except ValueError as e:
        flash(f'Invalid amount: {e}', 'danger')
        return redirect(url_for('corporate.donate'))
    except Exception as e:
        logger.error(f"Donation error: {e}")
        flash('Donation failed. Please try again.', 'danger')
        return redirect(url_for('corporate.donate'))


@corporate_bp.route('/impact')
@corporate_required
def impact():
    db = get_db()
    donations_list = []
    total = 0
    ngo_breakdown = {}

    if db:
        try:
            docs = list(db.collection('donations').where('donor_id', '==', session['user_id']).stream())
            donations_list = sorted(
                [{'id': d.id, **d.to_dict()} for d in docs],
                key=lambda x: x.get('created_at', ''), reverse=True
            )
            total = sum(d.get('amount', 0) for d in donations_list)
            for d in donations_list:
                name = d.get('ngo_name', 'Unknown')
                ngo_breakdown[name] = ngo_breakdown.get(name, 0) + d.get('amount', 0)
        except Exception as e:
            logger.error(f"Impact fetch: {e}")

    trees_funded = int(total / 10)
    carbon_offset = round(total * 0.0067, 1)
    area_restored = round(trees_funded / 500, 2)

    return render_template('corporate/impact.html',
        donations=donations_list,
        total=total,
        ngo_breakdown=ngo_breakdown,
        trees_funded=trees_funded,
        carbon_offset=carbon_offset,
        area_restored=area_restored
    )


@corporate_bp.route('/profile', methods=['GET', 'POST'])
@corporate_required
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
        allowed = {'company_name', 'contact_name', 'designation', 'phone', 'website',
                   'sector', 'csr_focus', 'csr_budget_lakhs', 'cin', 'preferred_states'}
        updates = {k: v.strip() for k, v in request.form.items() if v.strip() and k in allowed}
        if updates:
            try:
                db.collection('users').document(session['user_id']).update(updates)
                if 'company_name' in updates:
                    session['user_name'] = updates['company_name']
                flash('Profile updated.', 'success')
                return redirect(url_for('corporate.profile'))
            except Exception as e:
                flash(f'Update failed: {e}', 'danger')

    return render_template('corporate/profile.html', user=user_data)


@corporate_bp.route('/discover')
@corporate_required
def discover():
    db = get_db()
    ngos = []
    if db:
        try:
            docs = db.collection('users').where('type', '==', 'ngo').stream()
            ngos = [{'id': doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            logger.error(f"NGO discovery: {e}")
    return render_template('corporate/discover.html', ngos=ngos)


@corporate_bp.route('/csr-report')
@corporate_required
def csr_report():
    db = get_db()
    donations_list = []
    total = 0
    ngo_breakdown = {}
    user_data = {}

    if db:
        try:
            user_doc = db.collection('users').document(session['user_id']).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
        except Exception as e:
            logger.error(f"CSR report user fetch: {e}")

        try:
            docs = list(db.collection('donations').where('donor_id', '==', session['user_id']).stream())
            donations_list = sorted(
                [{'id': d.id, **d.to_dict()} for d in docs],
                key=lambda x: x.get('created_at', ''), reverse=True
            )
            total = sum(d.get('amount', 0) for d in donations_list)
            for d in donations_list:
                name = d.get('ngo_name', 'Unknown')
                ngo_breakdown[name] = ngo_breakdown.get(name, 0) + d.get('amount', 0)
        except Exception as e:
            logger.error(f"CSR report donations: {e}")

    trees_funded = int(total / 10)
    carbon_offset = round(total * 0.0067, 1)

    # Try carbon model for precise calculation
    try:
        from ..services.carbon_model import donation_to_carbon
        carbon_detail = donation_to_carbon(total) if total > 0 else None
    except Exception:
        carbon_detail = None

    report_year = datetime.datetime.now().year
    fy = f"{report_year - 1}–{str(report_year)[2:]}"

    return render_template('corporate/csr-report.html',
        user=user_data,
        donations=donations_list,
        total=total,
        ngo_breakdown=ngo_breakdown,
        trees_funded=trees_funded,
        carbon_offset=carbon_offset,
        carbon_detail=carbon_detail,
        fy=fy,
        report_date=datetime.datetime.now().strftime('%d %B %Y')
    )
