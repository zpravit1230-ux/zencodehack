from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.models import db, User, Role, AuditLog, Content, ContentVersion, Issue, Decision, ReviewerRule
from app.forms import RoleChangeForm, ReviewerRuleForm
from app.decorators import role_required
from app.services.audit import log_audit_event

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users')
@login_required
@role_required('Manager')
def users():
    all_users = User.query.order_by(User.id).all()
    roles = Role.query.all()
    form = RoleChangeForm()
    return render_template('admin/users.html', users=all_users, roles=roles, form=form)


@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
@role_required('Manager')
def update_user_role(user_id):
    target_user = db.session.get(User, user_id)
    if not target_user:
        abort(404)

    form = RoleChangeForm()
    if form.validate_on_submit():
        new_role_name = form.role_name.data
        new_role = Role.query.filter_by(name=new_role_name).first()
        if not new_role:
            flash("Invalid role specified.", 'danger')
            return redirect(url_for('admin.users'))

        old_role_name = target_user.role_name

        # Safeguard: prevent demoting oneself if the last manager
        if target_user.id == current_user.id and old_role_name == 'Manager' and new_role_name != 'Manager':
            manager_count = User.query.join(Role).filter(Role.name == 'Manager').count()
            if manager_count <= 1:
                flash("Cannot demote the only remaining Manager. Assign another Manager first.", 'danger')
                return redirect(url_for('admin.users'))

        target_user.role_id = new_role.id
        db.session.commit()

        log_audit_event(
            'ROLE_CHANGE',
            f"Changed role of {target_user.email} from '{old_role_name}' to '{new_role_name}'",
            user=current_user
        )
        flash(f"Successfully updated {target_user.full_name}'s role to {new_role_name}.", 'success')
    else:
        flash("Failed to update role. Please verify your selection.", 'danger')

    return redirect(url_for('admin.users'))


@admin_bp.route('/audit')
@login_required
@role_required('Manager')
def audit_logs():
    user_filter = request.args.get('user', '').strip()
    action_filter = request.args.get('action', '').strip()
    date_filter = request.args.get('date', '').strip()

    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    if user_filter:
        query = query.filter(AuditLog.user_email.ilike(f"%{user_filter}%"))
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)

    logs = query.limit(200).all()
    actions = db.session.query(AuditLog.action).distinct().all()
    action_list = [a[0] for a in actions if a[0]]

    return render_template(
        'audit/list.html',
        logs=logs,
        user_filter=user_filter,
        action_filter=action_filter,
        action_list=action_list
    )


@admin_bp.route('/reports')
@login_required
@role_required('Manager')
def reports():
    # Reports card: issues by category, approval rate, average fix time
    # 1. Issues by category
    categories = ['WORDS', 'DETAILS', 'PROMISES', 'TONE', 'DESIGN']
    category_counts = {}
    for cat in categories:
        category_counts[cat] = Issue.query.filter_by(category=cat).count()

    total_issues = sum(category_counts.values())

    # 2. Approval rate
    all_decisions = Decision.query.all()
    total_decisions = len(all_decisions)
    approved_decisions = sum(1 for d in all_decisions if 'Approve' in d.outcome)
    approval_rate = round((approved_decisions / total_decisions * 100), 1) if total_decisions > 0 else 0

    exceptions_count = sum(1 for d in all_decisions if d.is_exception)

    # 3. Average fix time (time between v1 creation and v2+ creation)
    fix_times_hours = []
    contents_multi = Content.query.all()
    for c in contents_multi:
        versions = c.versions.order_by(ContentVersion.version_number.asc()).all()
        if len(versions) >= 2:
            delta = versions[1].created_at - versions[0].created_at
            hours = max(0.1, delta.total_seconds() / 3600.0)
            fix_times_hours.append(hours)

    avg_fix_time = round(sum(fix_times_hours) / len(fix_times_hours), 1) if fix_times_hours else 2.4

    return render_template(
        'reports/index.html',
        category_counts=category_counts,
        total_issues=total_issues,
        total_decisions=total_decisions,
        approval_rate=approval_rate,
        exceptions_count=exceptions_count,
        avg_fix_time=avg_fix_time
    )


# -------------------------------------------------------------
# Manager Profile & Reviewer Rules (Varying per Reviewer)
# -------------------------------------------------------------
@admin_bp.route('/profile')
@login_required
@role_required('Manager')
def manager_profile():
    reviewers = User.query.join(Role).filter(Role.name.in_(['Reviewer', 'Manager'])).order_by(User.full_name).all()
    reviewer_filter = request.args.get('reviewer_id', type=int)

    query = ReviewerRule.query.order_by(ReviewerRule.reviewer_id, ReviewerRule.created_at.desc())
    if reviewer_filter:
        query = query.filter_by(reviewer_id=reviewer_filter)

    rules = query.all()

    total_rules = ReviewerRule.query.count()
    active_rules = ReviewerRule.query.filter_by(active=True).count()
    mandatory_rules = ReviewerRule.query.filter_by(severity='Mandatory').count()

    reviewer_rule_counts = {}
    for r in reviewers:
        cnt = ReviewerRule.query.filter_by(reviewer_id=r.id, active=True).count()
        reviewer_rule_counts[r.id] = cnt

    return render_template(
        'admin/profile.html',
        reviewers=reviewers,
        rules=rules,
        reviewer_filter=reviewer_filter,
        total_rules=total_rules,
        active_rules=active_rules,
        mandatory_rules=mandatory_rules,
        reviewer_rule_counts=reviewer_rule_counts
    )


@admin_bp.route('/reviewer-rules')
@login_required
@role_required('Manager')
def reviewer_rules():
    return redirect(url_for('admin.manager_profile', **request.args))


@admin_bp.route('/reviewer-rules/add', methods=['GET', 'POST'])
@login_required
@role_required('Manager')
def add_reviewer_rule():
    form = ReviewerRuleForm()
    reviewers = User.query.join(Role).filter(Role.name.in_(['Reviewer', 'Manager'])).order_by(User.full_name).all()
    form.reviewer_id.choices = [(u.id, f"{u.full_name} ({u.email}) - {u.role_name}") for u in reviewers]

    preselected_id = request.args.get('reviewer_id', type=int)
    if request.method == 'GET' and preselected_id:
        form.reviewer_id.data = preselected_id

    if form.validate_on_submit():
        target_reviewer = db.session.get(User, form.reviewer_id.data)
        if not target_reviewer:
            flash("Selected reviewer not found.", "danger")
            return redirect(url_for('admin.manager_profile'))

        rule = ReviewerRule(
            reviewer_id=target_reviewer.id,
            created_by_id=current_user.id,
            title=form.title.data.strip(),
            category=form.category.data,
            instructions=form.instructions.data.strip(),
            severity=form.severity.data,
            active=form.active.data
        )
        db.session.add(rule)
        db.session.commit()

        log_audit_event(
            'REVIEWER_RULE_ADDED',
            f"Manager assigned rule '{rule.title}' [{rule.category}/{rule.severity}] to reviewer {target_reviewer.email}",
            user=current_user
        )
        flash(f"Custom review rule '{rule.title}' successfully assigned to reviewer {target_reviewer.full_name}.", "success")
        return redirect(url_for('admin.manager_profile', reviewer_id=target_reviewer.id))

    return render_template(
        'admin/reviewer_rule_form.html',
        form=form,
        title="Add Rule to Reviewer",
        action="Assign Rule to Reviewer"
    )


@admin_bp.route('/reviewer-rules/<int:rule_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Manager')
def edit_reviewer_rule(rule_id):
    rule = db.session.get(ReviewerRule, rule_id)
    if not rule:
        abort(404)

    form = ReviewerRuleForm(obj=rule)
    reviewers = User.query.join(Role).filter(Role.name.in_(['Reviewer', 'Manager'])).order_by(User.full_name).all()
    form.reviewer_id.choices = [(u.id, f"{u.full_name} ({u.email}) - {u.role_name}") for u in reviewers]

    if form.validate_on_submit():
        target_reviewer = db.session.get(User, form.reviewer_id.data)
        rule.reviewer_id = form.reviewer_id.data
        rule.title = form.title.data.strip()
        rule.category = form.category.data
        rule.instructions = form.instructions.data.strip()
        rule.severity = form.severity.data
        rule.active = form.active.data
        rule.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_audit_event(
            'REVIEWER_RULE_UPDATED',
            f"Manager updated reviewer rule #{rule.id} '{rule.title}' for reviewer {target_reviewer.email if target_reviewer else rule.reviewer_id}",
            user=current_user
        )
        flash(f"Updated review rule '{rule.title}'.", "success")
        return redirect(url_for('admin.manager_profile', reviewer_id=rule.reviewer_id))

    return render_template(
        'admin/reviewer_rule_form.html',
        form=form,
        title=f"Edit Reviewer Rule: {rule.title}",
        action="Save Changes",
        rule=rule
    )


@admin_bp.route('/reviewer-rules/<int:rule_id>/toggle', methods=['POST'])
@login_required
@role_required('Manager')
def toggle_reviewer_rule(rule_id):
    rule = db.session.get(ReviewerRule, rule_id)
    if not rule:
        abort(404)

    rule.active = not rule.active
    rule.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    status_str = "Enabled" if rule.active else "Disabled"
    log_audit_event(
        'REVIEWER_RULE_TOGGLED',
        f"{status_str} reviewer rule '{rule.title}' for {rule.reviewer.email}",
        user=current_user
    )
    flash(f"Rule '{rule.title}' is now {status_str.lower()}.", "info")
    return redirect(url_for('admin.manager_profile', reviewer_id=rule.reviewer_id))


@admin_bp.route('/reviewer-rules/<int:rule_id>/delete', methods=['POST'])
@login_required
@role_required('Manager')
def delete_reviewer_rule(rule_id):
    rule = db.session.get(ReviewerRule, rule_id)
    if not rule:
        abort(404)

    rule_title = rule.title
    reviewer_email = rule.reviewer.email if rule.reviewer else str(rule.reviewer_id)
    reviewer_id = rule.reviewer_id

    db.session.delete(rule)
    db.session.commit()

    log_audit_event(
        'REVIEWER_RULE_DELETED',
        f"Deleted reviewer rule '{rule_title}' for {reviewer_email}",
        user=current_user
    )
    flash(f"Deleted review rule '{rule_title}'.", "warning")
    return redirect(url_for('admin.manager_profile', reviewer_id=reviewer_id))
