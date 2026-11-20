from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.models import db, Guideline
from app.forms import GuidelineForm
from app.decorators import role_required
from app.services.audit import log_audit_event

guidelines_bp = Blueprint('guidelines', __name__)

@guidelines_bp.route('/')
@login_required
@role_required('Manager')
def list_guidelines():
    category = request.args.get('category', '').upper()
    query = Guideline.query.order_by(Guideline.type, Guideline.key)
    if category in ['WORDS', 'DETAILS', 'PROMISES', 'TONE', 'PALETTE', 'LOGO']:
        query = query.filter_by(type=category)
    
    guidelines = query.all()
    categories = ['WORDS', 'DETAILS', 'PROMISES', 'TONE', 'PALETTE', 'LOGO']
    
    return render_template(
        'guidelines/list.html',
        guidelines=guidelines,
        selected_category=category,
        categories=categories
    )


@guidelines_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required('Manager')
def add_guideline():
    form = GuidelineForm()
    if form.validate_on_submit():
        rule = Guideline(
            type=form.type.data,
            key=form.key.data.strip(),
            value=form.value.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            active=form.active.data
        )
        db.session.add(rule)
        db.session.commit()

        log_audit_event(
            'GUIDELINE_ADD',
            f"Created guideline [{rule.type}] '{rule.key}': '{rule.value}'",
            user=current_user
        )
        flash(f"Brand rule for '{rule.key}' has been added successfully.", 'success')
        return redirect(url_for('guidelines.list_guidelines', category=rule.type))
    
    return render_template('guidelines/form.html', form=form, title="Add Brand Guideline", action="Add")


@guidelines_bp.route('/<int:guideline_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Manager')
def edit_guideline(guideline_id):
    rule = db.session.get(Guideline, guideline_id)
    if not rule:
        abort(404)

    form = GuidelineForm(obj=rule)
    if form.validate_on_submit():
        old_val = rule.value
        rule.type = form.type.data
        rule.key = form.key.data.strip()
        rule.value = form.value.data.strip()
        rule.description = form.description.data.strip() if form.description.data else None
        rule.active = form.active.data
        db.session.commit()

        log_audit_event(
            'GUIDELINE_EDIT',
            f"Updated guideline #{rule.id} [{rule.type}] '{rule.key}' (was: '{old_val}', now: '{rule.value}')",
            user=current_user
        )
        flash(f"Guideline '{rule.key}' updated successfully.", 'success')
        return redirect(url_for('guidelines.list_guidelines', category=rule.type))
    
    return render_template('guidelines/form.html', form=form, title=f"Edit Rule: {rule.key}", action="Save Changes", rule=rule)


@guidelines_bp.route('/<int:guideline_id>/toggle', methods=['POST'])
@login_required
@role_required('Manager')
def toggle_guideline(guideline_id):
    rule = db.session.get(Guideline, guideline_id)
    if not rule:
        abort(404)
        
    rule.active = not rule.active
    db.session.commit()

    state = "Active" if rule.active else "Inactive"
    log_audit_event(
        'GUIDELINE_TOGGLE',
        f"Toggled guideline #{rule.id} '{rule.key}' to {state}",
        user=current_user
    )
    flash(f"Guideline '{rule.key}' is now {state.lower()}.", 'info')
    return redirect(url_for('guidelines.list_guidelines', category=rule.type))


@guidelines_bp.route('/<int:guideline_id>/delete', methods=['POST'])
@login_required
@role_required('Manager')
def delete_guideline(guideline_id):
    rule = db.session.get(Guideline, guideline_id)
    if not rule:
        abort(404)
        
    key_name = rule.key
    rule_type = rule.type
    db.session.delete(rule)
    db.session.commit()

    log_audit_event(
        'GUIDELINE_DELETE',
        f"Deleted guideline #{guideline_id} [{rule_type}] '{key_name}'",
        user=current_user
    )
    flash(f"Guideline '{key_name}' deleted.", 'warning')
    return redirect(url_for('guidelines.list_guidelines', category=rule_type))


@guidelines_bp.route('/trained-rules')
@login_required
@role_required('Manager')
def trained_rules():
    from app.services.trainer import load_rules_from_csv
    rules = load_rules_from_csv()
    
    # Category and severity metrics
    categories = sorted(list(set(r['category'] for r in rules)))
    severities = {'Critical': 0, 'High': 0, 'Medium': 0, 'Low': 0}
    for r in rules:
        s = r.get('severity', 'Medium')
        if s in severities:
            severities[s] += 1

    return render_template(
        'guidelines/trained_rules.html',
        rules=rules,
        categories=categories,
        severities=severities
    )


@guidelines_bp.route('/train-dataset', methods=['POST'])
@login_required
@role_required('Manager')
def train_dataset():
    from app.services.trainer import train_brandguard_model
    try:
        res = train_brandguard_model(current_user=current_user)
        flash(
            f"Successfully trained BrandGuard on the 20-Rule Dataset! "
            f"({res['total_rules']} rules processed: {res['created']} added, {res['updated']} updated, {res['active']} active).",
            'success'
        )
    except Exception as e:
        flash(f"Error training dataset: {str(e)}", 'danger')

    return redirect(url_for('guidelines.trained_rules'))
