from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from app.models import Content, ContentVersion, Guideline, Decision, Issue, ReviewerRule
from app.decorators import role_required

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role_name == 'Manager':
            return redirect(url_for('main.manager_dashboard'))
        elif current_user.role_name == 'Reviewer':
            return redirect(url_for('main.reviewer_dashboard'))
        else:
            return redirect(url_for('main.creator_dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard/creator')
@login_required
@role_required('Creator', 'Manager')
def creator_dashboard():
    contents = Content.query.filter_by(creator_id=current_user.id).order_by(Content.updated_at.desc()).all()
    pending_fix = 0
    approved = 0
    for c in contents:
        v = c.latest_version
        if v:
            if v.status == 'Needs Fixes':
                pending_fix += 1
            elif 'Approved' in v.status:
                approved += 1

    return render_template(
        'dashboard/creator.html',
        contents=contents,
        pending_fix_count=pending_fix,
        approved_count=approved
    )


@main_bp.route('/dashboard/reviewer')
@login_required
@role_required('Reviewer', 'Manager')
def reviewer_dashboard():
    # Review queue: all content where current user is NOT creator (or for manager, all awaiting review)
    # Reviewers cannot review their own uploads, so we filter out current_user's uploads from queue
    all_contents = Content.query.order_by(Content.updated_at.desc()).all()
    review_items = []
    waiting_count = 0
    needs_fix_count = 0

    for c in all_contents:
        v = c.latest_version
        if v:
            # Exclude own uploads for pure reviewers
            if current_user.role_name == 'Reviewer' and c.creator_id == current_user.id:
                continue
            if v.status in ['Waiting for Review', 'Needs Fixes']:
                review_items.append(c)
                if v.status == 'Waiting for Review':
                    waiting_count += 1
                elif v.status == 'Needs Fixes':
                    needs_fix_count += 1

    reviewed_by_me = Decision.query.filter_by(reviewer_id=current_user.id).count()
    my_reviewer_rules = ReviewerRule.query.filter_by(reviewer_id=current_user.id, active=True).all()

    return render_template(
        'dashboard/reviewer.html',
        review_items=review_items,
        waiting_review_count=waiting_count,
        needs_fix_count=needs_fix_count,
        reviewed_by_me_count=reviewed_by_me,
        my_reviewer_rules=my_reviewer_rules
    )


@main_bp.route('/dashboard/manager')
@login_required
@role_required('Manager')
def manager_dashboard():
    recent_contents = Content.query.order_by(Content.updated_at.desc()).limit(10).all()
    total_contents = Content.query.count()
    waiting_review = 0
    approved_total = 0

    all_contents = Content.query.all()
    for c in all_contents:
        v = c.latest_version
        if v:
            if v.status == 'Waiting for Review':
                waiting_review += 1
            elif 'Approved' in v.status:
                approved_total += 1

    active_rules = Guideline.query.filter_by(active=True).count()
    reviewer_rules_count = ReviewerRule.query.filter_by(active=True).count()

    return render_template(
        'dashboard/manager.html',
        recent_contents=recent_contents,
        total_contents=total_contents,
        waiting_review=waiting_review,
        approved_total=approved_total,
        active_guidelines=active_rules,
        reviewer_rules_count=reviewer_rules_count
    )
