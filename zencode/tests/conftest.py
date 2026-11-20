import os
import sys

# Ensure project root takes precedence over any site-packages
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from app import create_app
from app.config import TestConfig
from app.models import db, Role, User, Guideline

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        # Seed base roles
        for r_name in ['Creator', 'Reviewer', 'Manager']:
            if not Role.query.filter_by(name=r_name).first():
                db.session.add(Role(name=r_name, description=f"{r_name} role"))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def init_database(app):
    with app.app_context():
        creator_role = Role.query.filter_by(name='Creator').first()
        reviewer_role = Role.query.filter_by(name='Reviewer').first()
        manager_role = Role.query.filter_by(name='Manager').first()

        creator = User(full_name='Priya Writer', email='creator@lumora.demo', role=creator_role)
        creator.set_password('Creator@123')

        reviewer = User(full_name='Reviewer Rachel', email='reviewer@lumora.demo', role=reviewer_role)
        reviewer.set_password('Reviewer@123')

        manager = User(full_name='Manager Mike', email='manager@lumora.demo', role=manager_role)
        manager.set_password('Manager@123')

        db.session.add_all([creator, reviewer, manager])
        db.session.commit()

        yield db
