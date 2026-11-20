import os
from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from app.config import Config
from app.models import db, User

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

csrf = CSRFProtect()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.content import content_bp
    from app.routes.guidelines import guidelines_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(content_bp, url_prefix='/content')
    app.register_blueprint(guidelines_bp, url_prefix='/guidelines')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Register error handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(413)
    def entity_too_large(error):
        return render_template('errors/413.html', message="The file uploaded exceeds the 10 MB limit."), 413

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.context_processor
    def inject_global_data():
        return {
            'app_name': 'BrandGuard AI',
            'brand_name': 'Lumora'
        }

    # Auto-create tables & upgrade SQLite schema if needed
    with app.app_context():
        db.create_all()
        _upgrade_sqlite_schema()

    return app


def _upgrade_sqlite_schema():
    from sqlalchemy import text
    try:
        # Check content_versions columns
        res = db.session.execute(text("PRAGMA table_info(content_versions)")).fetchall()
        cols = {row[1] for row in res}
        if cols:
            if 'corrected_text' not in cols:
                db.session.execute(text("ALTER TABLE content_versions ADD COLUMN corrected_text TEXT"))
            if 'page_data_json' not in cols:
                db.session.execute(text("ALTER TABLE content_versions ADD COLUMN page_data_json TEXT DEFAULT '[]'"))
            if 'quality_score' not in cols:
                db.session.execute(text("ALTER TABLE content_versions ADD COLUMN quality_score FLOAT DEFAULT 100.0"))
            if 'compliance_score' not in cols:
                db.session.execute(text("ALTER TABLE content_versions ADD COLUMN compliance_score FLOAT DEFAULT 100.0"))
            if 'category_scores_json' not in cols:
                db.session.execute(text("ALTER TABLE content_versions ADD COLUMN category_scores_json TEXT DEFAULT '{}'"))

        # Check issues columns
        res_iss = db.session.execute(text("PRAGMA table_info(issues)")).fetchall()
        iss_cols = {row[1] for row in res_iss}
        if iss_cols:
            if 'page_number' not in iss_cols:
                db.session.execute(text("ALTER TABLE issues ADD COLUMN page_number INTEGER DEFAULT 1"))
            if 'section_heading' not in iss_cols:
                db.session.execute(text("ALTER TABLE issues ADD COLUMN section_heading VARCHAR(150) DEFAULT 'General'"))
            if 'mistake_type' not in iss_cols:
                db.session.execute(text("ALTER TABLE issues ADD COLUMN mistake_type VARCHAR(100)"))
            if 'improved_text' not in iss_cols:
                db.session.execute(text("ALTER TABLE issues ADD COLUMN improved_text TEXT"))
            if 'reviewer_comment' not in iss_cols:
                db.session.execute(text("ALTER TABLE issues ADD COLUMN reviewer_comment TEXT"))
        db.session.commit()
    except Exception:
        db.session.rollback()

