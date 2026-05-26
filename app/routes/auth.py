from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..services.firebase_service import get_db, get_bucket, get_auth
import logging, os

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Receive Firebase ID token from client-side auth
        id_token = request.form.get('id_token')
        email = request.form.get('email')
        
        firebase_auth = get_auth()
        db = get_db()
        
        if not firebase_auth or not db:
            flash('Authentication service unavailable.', 'danger')
            return render_template('page-login.html')
        
        try:
            if id_token:
                decoded = firebase_auth.verify_id_token(id_token)
                uid = decoded['uid']
            else:
                # Fallback: look up by email (for server-side only, no password verify)
                user = firebase_auth.get_user_by_email(email)
                uid = user.uid
            
            user_doc = db.collection('users').document(uid).get()
            if not user_doc.exists:
                flash('User profile not found.', 'danger')
                return render_template('page-login.html')
            
            user_data = user_doc.to_dict()
            session['user_id'] = uid
            session['user_type'] = user_data.get('type')
            session['user_name'] = user_data.get('name', user_data.get('username', 'User'))
            session['user_email'] = user_data.get('email', '')
            
            flash(f"Welcome back, {session['user_name']}!", 'success')
            if user_data.get('type') == 'ngo':
                return redirect(url_for('ngo.home'))
            else:
                return redirect(url_for('corporate.home'))
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('Login failed. Please check your credentials.', 'danger')
    
    return render_template('page-login.html')

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('public.index'))

@auth_bp.route('/ngo-signup', methods=['GET'])
def ngo_signup_page():
    return render_template('ngo-signup.html')

@auth_bp.route('/register-ngo', methods=['POST'])
def register_ngo():
    db = get_db()
    bucket = get_bucket()
    firebase_auth = get_auth()
    
    if not firebase_auth or not db:
        flash('Registration service unavailable.', 'danger')
        return render_template('ngo-signup.html')
    
    name = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    website = request.form.get('website', '').strip()
    area = request.form.get('area', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    certificate = request.files.get('certificate')
    
    if not all([name, email, password, area]):
        flash('Please fill in all required fields.', 'warning')
        return render_template('ngo-signup.html')
    
    try:
        user = firebase_auth.create_user(email=email, password=password, display_name=username)
        
        certificate_url = None
        if certificate and certificate.filename and bucket:
            blob = bucket.blob(f'certificates/{user.uid}/{certificate.filename}')
            blob.upload_from_file(certificate)
            blob.make_public()
            certificate_url = blob.public_url
        
        db.collection('users').document(user.uid).set({
            'name': name, 'address': address, 'email': email, 'phone': phone,
            'website': website, 'certificate': certificate_url, 'area': area,
            'username': username, 'type': 'ngo', 'created_at': __import__('datetime').datetime.utcnow().isoformat()
        })
        
        session['user_id'] = user.uid
        session['user_type'] = 'ngo'
        session['user_name'] = name
        session['user_email'] = email
        
        flash(f'Welcome to Blue.AI, {name}!', 'success')
        return redirect(url_for('ngo.home'))
    except Exception as e:
        logger.error(f"NGO registration error: {e}")
        flash(f'Registration failed: {str(e)}', 'danger')
    
    return render_template('ngo-signup.html')

@auth_bp.route('/corporate-signup', methods=['GET'])
def corporate_signup_page():
    return render_template('corporate-signup.html')

@auth_bp.route('/register-corporate', methods=['POST'])
def register_corporate():
    db = get_db()
    bucket = get_bucket()
    firebase_auth = get_auth()
    
    if not firebase_auth or not db:
        flash('Registration service unavailable.', 'danger')
        return render_template('corporate-signup.html')
    
    name = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    website = request.form.get('website', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    certificate = request.files.get('certificate')
    
    if not all([name, email, password]):
        flash('Please fill in all required fields.', 'warning')
        return render_template('corporate-signup.html')
    
    try:
        user = firebase_auth.create_user(email=email, password=password, display_name=username)
        
        certificate_url = None
        if certificate and certificate.filename and bucket:
            blob = bucket.blob(f'certificates/{user.uid}/{certificate.filename}')
            blob.upload_from_file(certificate)
            blob.make_public()
            certificate_url = blob.public_url
        
        db.collection('users').document(user.uid).set({
            'name': name, 'address': address, 'email': email, 'phone': phone,
            'website': website, 'certificate': certificate_url,
            'username': username, 'type': 'company', 'created_at': __import__('datetime').datetime.utcnow().isoformat()
        })
        
        session['user_id'] = user.uid
        session['user_type'] = 'company'
        session['user_name'] = name
        session['user_email'] = email
        
        flash(f'Welcome to Blue.AI, {name}!', 'success')
        return redirect(url_for('corporate.home'))
    except Exception as e:
        logger.error(f"Corporate registration error: {e}")
        flash(f'Registration failed: {str(e)}', 'danger')
    
    return render_template('corporate-signup.html')
