from flask import Blueprint, render_template, request
from ..services.firebase_service import get_db
import logging

logger = logging.getLogger(__name__)
public_bp = Blueprint('public', __name__)

def get_platform_stats():
    db = get_db()
    if not db:
        return {'ngo_count': 0, 'corp_count': 0, 'total_donated': 0}
    try:
        ngos = list(db.collection('users').where('type', '==', 'ngo').stream())
        corps = list(db.collection('users').where('type', '==', 'company').stream())
        donations = list(db.collection('donations').stream())
        total = sum(d.to_dict().get('amount', 0) for d in donations)
        return {'ngo_count': len(ngos), 'corp_count': len(corps), 'total_donated': total}
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {'ngo_count': 0, 'corp_count': 0, 'total_donated': 0}

@public_bp.route('/')
def index():
    stats = get_platform_stats()
    return render_template('index.html', stats=stats)

@public_bp.route('/corporates')
def corporates():
    return render_template('page-corporates.html')

@public_bp.route('/ngos')
def ngos_public():
    db = get_db()
    ngos = []
    if db:
        try:
            docs = db.collection('users').where('type', '==', 'ngo').stream()
            ngos = [{'id': doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            logger.error(f"NGO fetch error: {e}")
    return render_template('page-ngos.html', ngos=ngos)

@public_bp.route('/learnmore')
def learnmore():
    return render_template('page-learnmore.html')

@public_bp.route('/donate-nologin')
def donate_nologin():
    db = get_db()
    ngos = []
    if db:
        try:
            docs = db.collection('users').where('type', '==', 'ngo').stream()
            ngos = [{'id': doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            logger.error(f"NGO fetch error: {e}")
    return render_template('page-donate-nologin.html', ngos=ngos)

@public_bp.route('/ngodet/<ngo_id>')
def ngo_details(ngo_id):
    db = get_db()
    if not db:
        return render_template('page-ngo-details.html', ngo=None, error="Database unavailable")
    doc = db.collection('users').document(ngo_id).get()
    if not doc.exists:
        return "NGO not found", 404
    return render_template('page-ngo-details.html', ngo={'id': doc.id, **doc.to_dict()})

@public_bp.route('/map-learnmore')
def map_learnmore():
    return render_template('map-learnmore.html')
