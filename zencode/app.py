import os
from app import create_app
from app.models import db, Role

app = create_app()

with app.app_context():
    db.create_all()
    # Ensure standard default roles exist
    for role_name in ['Creator', 'Reviewer', 'Manager']:
        if not Role.query.filter_by(name=role_name).first():
            role = Role(name=role_name, description=f"{role_name} role in BrandGuard AI")
            db.session.add(role)
    db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

