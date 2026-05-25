import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, firestore, storage
import os
import json
import logging

logger = logging.getLogger(__name__)

_initialized = False
_db = None
_bucket = None

def init_firebase():
    global _initialized, _db, _bucket
    if _initialized or firebase_admin._apps:
        _initialized = True
        return True
    
    try:
        creds_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
        creds_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
        
        if creds_json:
            cred_dict = json.loads(creds_json)
            cred = credentials.Certificate(cred_dict)
        elif creds_path and os.path.exists(creds_path):
            cred = credentials.Certificate(creds_path)
        else:
            logger.warning("No Firebase credentials found. Running without Firebase.")
            return False
        
        bucket_name = os.environ.get('FIREBASE_STORAGE_BUCKET', 'blue-ai-75fc0.appspot.com')
        firebase_admin.initialize_app(cred, {'storageBucket': bucket_name})
        _db = firestore.client()
        _bucket = storage.bucket()
        _initialized = True
        return True
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        return False

def get_db():
    if not _initialized:
        init_firebase()
    return _db

def get_bucket():
    if not _initialized:
        init_firebase()
    return _bucket

def get_auth():
    if not _initialized:
        init_firebase()
    return firebase_auth if _initialized else None
