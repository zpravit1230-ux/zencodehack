import os

basedir = os.path.abspath(os.path.dirname(__file__))
root_dir = os.path.abspath(os.path.join(basedir, '..'))

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'brandguard-secret-key-change-in-prod-xyz789')
    # Easy single-line switch to Postgres/MySQL via DATABASE_URL
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(root_dir, 'brandguard.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload settings: max 10MB
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(root_dir, 'uploads')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'doc', 'ppt', 'pptx', 'xls', 'xlsx', 'csv', 'png', 'jpg', 'jpeg', 'webp'}
    
    # Security & Lockout settings
    MAX_FAILED_LOGINS = 5
    LOCKOUT_DURATION_MINUTES = 15
    
    # AI Explain Hook (disabled by default, off without key)
    AI_EXPLAIN_ENABLED = os.getenv('AI_EXPLAIN_ENABLED', 'false').lower() in ('true', '1', 'yes')
    AI_EXPLAIN_API_KEY = os.getenv('AI_EXPLAIN_API_KEY', '')

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = os.path.join(root_dir, 'tests', 'test_uploads')

