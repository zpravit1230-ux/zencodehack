from datetime import datetime, timezone
from flask import request
from flask_login import current_user
from app.models import db, AuditLog

def log_audit_event(action: str, details: str, user=None, ip_address=None):
    """
    Writes an immutable record into the audit log.
    If user is not provided, extracts user details from current_user if authenticated.
    """
    try:
        user_id = None
        user_email = None
        user_role = None

        if user:
            user_id = user.id
            user_email = user.email
            user_role = user.role_name
        elif current_user and current_user.is_authenticated:
            user_id = current_user.id
            user_email = current_user.email
            user_role = current_user.role_name

        if not ip_address:
            try:
                ip_address = request.remote_addr
            except Exception:
                ip_address = '127.0.0.1'

        log_entry = AuditLog(
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            action=action,
            details=details,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # In audit service, failure to log shouldn't silently corrupt session, but record locally
        print(f"[AUDIT LOG ERROR] Failed to record action '{action}': {e}")

