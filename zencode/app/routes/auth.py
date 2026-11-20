from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app.models import db, User, Role
from app.forms import RegistrationForm, LoginForm
from app.services.audit import log_audit_event

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        # Default role for any new user is Creator
        creator_role = Role.query.filter_by(name='Creator').first()
        if not creator_role:
            creator_role = Role(name='Creator', description='Creator role')
            db.session.add(creator_role)
            db.session.commit()

        user = User(
            full_name=form.full_name.data.strip(),
            email=email,
            role_id=creator_role.id
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        log_audit_event('REGISTER', f"New user registered: {user.email} with role Creator", user=user)
        flash('Registration successful! You can now log in with your credentials.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if request.method == 'GET':
        preset_role = request.args.get('role', '').lower()
        role_map = {
            'creator': ('priya@lumora.demo', 'Creator@123'),
            'reviewer': ('reviewer@lumora.demo', 'Reviewer@123'),
            'manager': ('manager@lumora.demo', 'Manager@123')
        }
        if preset_role in role_map:
            form.email.data, form.password.data = role_map[preset_role]

    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        user = User.query.filter_by(email=email).first()

        if user:
            # Check lockout
            if user.is_locked:
                now = datetime.now(timezone.utc)
                lock_time = user.locked_until
                if lock_time.tzinfo is None:
                    lock_time = lock_time.replace(tzinfo=timezone.utc)
                remaining = int((lock_time - now).total_seconds() / 60) + 1
                log_audit_event('LOGIN_BLOCKED_LOCKOUT', f"Blocked login attempt for locked account: {email}")
                flash(f"Account is temporarily locked due to repeated failed logins. Please try again in {remaining} minute(s).", 'danger')
                return render_template('auth/login.html', form=form)

            # Check password
            if user.check_password(form.password.data):
                # Reset counters
                user.failed_logins = 0
                user.locked_until = None
                db.session.commit()

                login_user(user, remember=form.remember_me.data)
                log_audit_event('LOGIN_SUCCESS', f"User {user.email} logged in successfully", user=user)
                flash(f"Welcome back, {user.full_name}!", 'success')

                next_page = request.args.get('next')
                if next_page and next_page.startswith('/'):
                    return redirect(next_page)
                
                # Role-specific redirect
                if user.role_name == 'Manager':
                    return redirect(url_for('main.manager_dashboard'))
                elif user.role_name == 'Reviewer':
                    return redirect(url_for('main.reviewer_dashboard'))
                else:
                    return redirect(url_for('main.creator_dashboard'))
            else:
                user.failed_logins += 1
                if user.failed_logins >= 5:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                    db.session.commit()
                    log_audit_event('ACCOUNT_LOCKOUT', f"Account {email} locked after 5 failed attempts")
                    flash("Too many failed attempts. Your account has been locked for 15 minutes.", 'danger')
                else:
                    db.session.commit()
                    remaining = 5 - user.failed_logins
                    log_audit_event('LOGIN_FAILED', f"Failed login for {email} ({remaining} attempts remaining)")
                    flash(f"Invalid email or password. {remaining} attempt(s) remaining before temporary lockout.", 'danger')
                return render_template('auth/login.html', form=form)
        else:
            log_audit_event('LOGIN_FAILED', f"Failed login attempt for non-existent email: {email}")
            flash("Invalid email or password.", 'danger')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    user = current_user._get_current_object()
    log_audit_event('LOGOUT', f"User {user.email} logged out", user=user)
    logout_user()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('auth.login'))
