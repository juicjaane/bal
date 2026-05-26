from flask import Flask
import os
import logging

logging.basicConfig(level=logging.INFO)

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    
    # Initialize Firebase eagerly (it's fine to fail at startup)
    from .services.firebase_service import init_firebase
    init_firebase()
    
    # Register blueprints
    from .routes.public import public_bp
    from .routes.auth import auth_bp
    from .routes.ngo import ngo_bp
    from .routes.corporate import corporate_bp
    
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(ngo_bp)
    app.register_blueprint(corporate_bp)
    
    return app
