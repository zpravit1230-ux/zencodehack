import os
import io
import uuid
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from flask import (
    Blueprint, render_template, redirect, url_for, flash, 
    request, abort, current_app, jsonify, send_file, Response
)
from flask_login import login_required, current_user
from app.models import db, Content, ContentVersion, Issue, Decision, Guideline, ReviewerRule
from app.forms import ContentUploadForm, ContentVersionUploadForm, DecisionForm
from app.decorators import role_required
from app.services.extractor import (
    extract_document_content, extract_text_from_file, extract_key_details
)
from app.services.checker import run_brand_check
from app.services.audit import log_audit_event
from app.services.exporter import (
    generate_excel_issues_summary, generate_pdf_review_report
)

content_bp = Blueprint('content', __name__)

def _process_content_version(content: Content, version: ContentVersion, file_obj=None, pasted_text=None):
    """
    Comprehensive multi-format document intake, multi-page extraction,
    and 7-category AI review analysis pipeline.
    """
    raw_text = pasted_text.strip() if pasted_text else ""
    extracted_text = ""
    file_type = 'text'
    pages_data = []

    if file_obj and file_obj.filename:
        filename = secure_filename(file_obj.filename)
        unique_name = f"{content.id}_v{version.version_number}_{uuid.uuid4().hex[:8]}_{filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name)
        file_obj.save(file_path)

        version.file_path = file_path
        version.original_filename = filename

        # Extract full document content with page-by-page mapping
        ext_text, ftype, p_data = extract_document_content(file_path=file_path, filename=filename)
        extracted_text = ext_text
        file_type = ftype
        pages_data = p_data
        if not raw_text:
            raw_text = extracted_text
    else:
        # Pasted text
        ext_text, ftype, p_data = extract_document_content(pasted_text=raw_text)
        extracted_text = ext_text
        file_type = 'text'
        pages_data = p_data

    version.raw_text = raw_text
    version.extracted_text = extracted_text
    version.corrected_text = extracted_text  # Defaults to extracted text; updated as suggestions are accepted/edited
    version.file_type = file_type
    version.page_data = pages_data

    # Extract key details (prices, dates, claims, dominant colors)
    details = extract_key_details(extracted_text, version.file_path)
    version.extracted_details = details
    db.session.commit()

    # Log extraction / intake
    log_audit_event(
        'READ_CONTENT',
        f"Analyzed {len(extracted_text)} chars across {len(pages_data)} pages for '{content.title}' v{version.version_number}",
        user=current_user
    )

    # Run Comprehensive AI Review Engine
    guidelines = Guideline.query.filter_by(active=True).all()
    detected_issues = run_brand_check(
        text=extracted_text,
        details=details,
        file_type=file_type,
        file_path=version.file_path,
        guidelines=guidelines,
        pages_data=pages_data
    )

    # Save Issue records
    for iss in detected_issues:
        issue_record = Issue(
            version_id=version.id,
            category=iss['category'],
            severity=iss['severity'],
            rule_id=iss['rule_id'],
            snippet=iss['snippet'],
            why_it_matters=iss['why_it_matters'],
            suggestion=iss['suggestion'],
            mistake_type=iss.get('mistake_type', 'Brand Guideline Violation'),
            improved_text=iss.get('improved_text', iss['suggestion']),
            page_number=iss.get('page_number', 1),
            section_heading=iss.get('section_heading', 'General Section'),
            status='Open'
        )
        db.session.add(issue_record)

    db.session.commit()

    # Compute Category Performance Breakdown
    cat_scores = {}
    for cat in ['WORDS', 'DETAILS', 'PROMISES', 'TONE', 'DESIGN']:
        total_in_cat = sum(1 for i in detected_issues if i['category'] == cat)
        cat_scores[cat] = max(0, 100 - (total_in_cat * 18))
    version.category_scores = cat_scores

    # Calculate initial compliance & quality scores
    version.recalculate_scores()

    # Determine status
    if version.has_open_serious_issue:
        version.status = 'Needs Fixes'
    else:
        version.status = 'Waiting for Review'

    db.session.commit()

    log_audit_event(
        'CHECK_RUN',
        f"AI analysis completed for '{content.title}' v{version.version_number}: {version.critical_issues_count} Critical, {version.high_issues_count} High, {version.medium_issues_count} Medium, {version.low_issues_count} Low. Score: {version.quality_score}/100. Status: {version.status}",
        user=current_user
    )


@content_bp.route('/')
@login_required
def list_content():
    if current_user.role_name == 'Reviewer':
        return redirect(url_for('main.reviewer_dashboard'))
    elif current_user.role_name == 'Manager':
        return redirect(url_for('main.manager_dashboard'))
    return redirect(url_for('main.creator_dashboard'))


@content_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_content():
    form = ContentUploadForm()
    if form.validate_on_submit():
        pasted = form.pasted_text.data
        file_item = form.file.data

        if not pasted and (not file_item or not file_item.filename):
            flash("Please either paste copy directly or select a file to upload.", 'danger')
            return render_template('content/new.html', form=form)

        # Create Content container
        content = Content(
            title=form.title.data.strip(),
            creator_id=current_user.id
        )
        db.session.add(content)
        db.session.commit()

        # Create Version 1
        version = ContentVersion(
            content_id=content.id,
            version_number=1,
            status='Processing'
        )
        db.session.add(version)
        db.session.commit()

        log_audit_event('UPLOAD', f"Created content submission '{content.title}' (v1)", user=current_user)

        # Ingest and analyze
        _process_content_version(content, version, file_obj=file_item, pasted_text=pasted)

        flash(f"Content '{content.title}' submitted and analyzed successfully.", 'success')
        return redirect(url_for('content.content_detail', content_id=content.id))

    return render_template('content/new.html', form=form)


@content_bp.route('/<int:content_id>')
@login_required
def content_detail(content_id):
    content = db.session.get(Content, content_id)
    if not content:
        abort(404)

    v_param = request.args.get('v', type=int)
    if v_param:
        version = content.versions.filter_by(version_number=v_param).first()
        if not version:
            version = content.latest_version
    else:
        version = content.latest_version

    versions = content.versions.order_by(ContentVersion.version_number.desc()).all()
    upload_form = ContentVersionUploadForm()
    decision_form = DecisionForm()

    # Ensure corrected_text is populated
    if version and not version.corrected_text:
        version.corrected_text = version.extracted_text or version.raw_text or ""
        version.recalculate_scores()
        db.session.commit()

    # Determine stepper step (1 to 6)
    step = 5
    if version:
        if version.status in ['Approved', 'Approve', 'Approved with Exception', 'Rejected', 'Reject']:
            step = 6
        elif version.status == 'Waiting for Review':
            step = 5
        elif version.status == 'Needs Fixes':
            step = 4
        elif version.status == 'Processing':
            step = 2

    # Group issues by severity
    issues = version.issues.all() if version else []
    serious_issues = [i for i in issues if i.severity in ['Serious', 'Critical', 'High']]
    warning_issues = [i for i in issues if i.severity in ['Warning', 'Medium']]
    info_issues = [i for i in issues if i.severity in ['Info', 'Low']]

    # Own upload check
    is_own_upload = (content.creator_id == current_user.id)

    # Reviewer directives
    assigned_reviewer_rules = []
    if current_user.is_authenticated and current_user.role_name in ['Reviewer', 'Manager']:
        assigned_reviewer_rules = ReviewerRule.query.filter_by(reviewer_id=current_user.id, active=True).all()

    # Page data
    pages = version.page_data if version else []
    if not pages and version:
        # Fallback single page
        pages = [{
            'page_number': 1,
            'heading': 'Document Text',
            'text': version.current_text,
            'tables': []
        }]

    return render_template(
        'content/detail.html',
        content=content,
        version=version,
        versions=versions,
        step=step,
        issues=issues,
        serious_issues=serious_issues,
        warning_issues=warning_issues,
        info_issues=info_issues,
        upload_form=upload_form,
        decision_form=decision_form,
        is_own_upload=is_own_upload,
        assigned_reviewer_rules=assigned_reviewer_rules,
        pages=pages
    )


@content_bp.route('/<int:content_id>/version', methods=['POST'])
@login_required
def upload_version(content_id):
    content = db.session.get(Content, content_id)
    if not content:
        abort(404)

    # Creators can upload fixes; managers can also upload
    if current_user.role_name == 'Creator' and content.creator_id != current_user.id:
        abort(403)

    form = ContentVersionUploadForm()
    if form.validate_on_submit():
        pasted = form.pasted_text.data
        file_item = form.file.data

        if not pasted and (not file_item or not file_item.filename):
            flash("Please upload a revised file or paste corrected text.", 'danger')
            return redirect(url_for('content.content_detail', content_id=content.id))

        latest_v = content.latest_version
        next_version_num = (latest_v.version_number + 1) if latest_v else 1

        new_version = ContentVersion(
            content_id=content.id,
            version_number=next_version_num,
            status='Processing'
        )
        db.session.add(new_version)
        db.session.commit()

        log_audit_event('FIX', f"Submitted revised version v{next_version_num} for '{content.title}'", user=current_user)

        # Automatically re-check the new version
        _process_content_version(content, new_version, file_obj=file_item, pasted_text=pasted)

        flash(f"Version {next_version_num} uploaded and re-checked automatically.", 'success')
        return redirect(url_for('content.content_detail', content_id=content.id, v=next_version_num))

    flash("Invalid revision upload.", 'danger')
    return redirect(url_for('content.content_detail', content_id=content.id))


@content_bp.route('/<int:content_id>/decision', methods=['POST'])
@login_required
@role_required('Reviewer', 'Manager')
def record_decision(content_id):
    content = db.session.get(Content, content_id)
    if not content:
        abort(404)

    # SAFEGUARD 4: Reviewers cannot review their own uploads
    if content.creator_id == current_user.id:
        flash("Safeguard Violation: Reviewers cannot review or approve their own uploads.", 'danger')
        log_audit_event(
            'SELF_REVIEW_BLOCKED',
            f"Blocked self-review attempt by {current_user.email} on '{content.title}'",
            user=current_user
        )
        return redirect(url_for('content.content_detail', content_id=content.id))

    v_param = request.args.get('v', type=int)
    if v_param:
        version = content.versions.filter_by(version_number=v_param).first()
    else:
        version = content.latest_version

    if not version:
        abort(404)

    form = DecisionForm()
    if form.validate_on_submit():
        raw_outcome = form.outcome.data
        reason = form.reason.data.strip() if form.reason.data else ""

        status_map = {
            'Approve': 'Approved',
            'Approved': 'Approved',
            'Reject': 'Rejected',
            'Rejected': 'Rejected',
            'Approve with Exception': 'Approved with Exception',
            'Approved with Exception': 'Approved with Exception'
        }
        outcome = status_map.get(raw_outcome, raw_outcome)

        # SAFEGUARD 1: Content with any open Serious issue cannot be approved
        if outcome == 'Approved' and version.has_open_serious_issue:
            flash("Safeguard Violation: Content with open Serious brand issues cannot be approved.", 'danger')
            log_audit_event(
                'APPROVAL_BLOCKED_SERIOUS_ISSUES',
                f"Blocked approval attempt for '{content.title}' v{version.version_number} due to {version.serious_issues_count} open Serious issues.",
                user=current_user
            )
            return redirect(url_for('content.content_detail', content_id=content.id, v=version.version_number))

        # SAFEGUARD 2: Approve with exception requires mandatory written reason
        is_exception = (outcome == 'Approved with Exception')
        if is_exception:
            if not reason or len(reason) < 5:
                flash("Safeguard Violation: A written justification reason is mandatory when approving with an exception.", 'danger')
                return redirect(url_for('content.content_detail', content_id=content.id, v=version.version_number))

        decision = version.decision
        if not decision:
            decision = Decision(
                version_id=version.id,
                reviewer_id=current_user.id,
                outcome=outcome,
                reason=reason,
                is_exception=is_exception
            )
            db.session.add(decision)
        else:
            decision.reviewer_id = current_user.id
            decision.outcome = outcome
            decision.reason = reason
            decision.is_exception = is_exception

        version.status = outcome
        db.session.commit()

        action_name = 'EXCEPTION' if is_exception else 'DECISION'
        log_audit_event(
            action_name,
            f"Decision recorded on '{content.title}' v{version.version_number}: {outcome}. Reason: {reason or 'Standard review'}",
            user=current_user
        )

        flash(f"Decision recorded: '{outcome}' on version {version.version_number}.", 'success')
        return redirect(url_for('content.content_detail', content_id=content.id, v=version.version_number))

    flash("Failed to process decision. Please check the form.", 'danger')
    return redirect(url_for('content.content_detail', content_id=content.id, v=version.version_number))


# ---------------------------------------------------------------------------
# Interactive Suggestion Engine APIs (Accept, Reject, Edit, Comment)
# ---------------------------------------------------------------------------

@content_bp.route('/<int:content_id>/issue/<int:issue_id>/accept', methods=['POST'])
@login_required
def accept_suggestion(content_id):
    content = db.session.get(Content, content_id)
    if not content:
        return jsonify({'error': 'Content not found'}), 404

    # Allow creator, reviewer, or manager
    issue = db.session.get(Issue, issue_id)
    if not issue or issue.version.content_id != content.id:
        return jsonify({'error': 'Issue not found'}), 404

    version = issue.version
    replacement = issue.improved_text or issue.suggestion

    # Apply replacement to corrected_text
    curr_text = version.current_text
    if issue.snippet in curr_text:
        version.corrected_text = curr_text.replace(issue.snippet, replacement)
    elif issue.snippet.strip("...") in curr_text:
        version.corrected_text = curr_text.replace(issue.snippet.strip("..."), replacement)

    issue.status = 'Accepted'
    version.recalculate_scores()
    db.session.commit()

    log_audit_event(
        'SUGGESTION_ACCEPTED',
        f"Accepted AI suggestion for #{issue.id} [{issue.rule_id}] on '{content.title}' v{version.version_number}",
        user=current_user
    )

    return jsonify({
        'success': True,
        'issue_id': issue.id,
        'status': 'Accepted',
        'replacement': replacement,
        'quality_score': version.quality_score,
        'compliance_score': version.compliance_score,
        'open_issues': version.open_issues_count,
        'has_open_serious': version.has_open_serious_issue
    })


@content_bp.route('/<int:content_id>/issue/<int:issue_id>/reject', methods=['POST'])
@login_required
def reject_suggestion(content_id):
    content = db.session.get(Content, content_id)
    if not content:
        return jsonify({'error': 'Content not found'}), 404

    issue = db.session.get(Issue, issue_id)
    if not issue or issue.version.content_id != content.id:
        return jsonify({'error': 'Issue not found'}), 404

    version = issue.version
    issue.status = 'Rejected'
    version.recalculate_scores()
    db.session.commit()

    log_audit_event(
        'SUGGESTION_REJECTED',
        f"Rejected AI suggestion for #{issue.id} [{issue.rule_id}] on '{content.title}' v{version.version_number}",
        user=current_user
    )

    return jsonify({
        'success': True,
        'issue_id': issue.id,
        'status': 'Rejected',
        'quality_score': version.quality_score,
        'compliance_score': version.compliance_score,
        'open_issues': version.open_issues_count,
        'has_open_serious': version.has_open_serious_issue
    })


@content_bp.route('/<int:content_id>/issue/<int:issue_id>/edit', methods=['POST'])
@login_required
def edit_suggestion(content_id):
    content = db.session.get(Content, content_id)
    if not content:
        return jsonify({'error': 'Content not found'}), 404

    issue = db.session.get(Issue, issue_id)
    if not issue or issue.version.content_id != content.id:
        return jsonify({'error': 'Issue not found'}), 404

    version = issue.version
    custom_text = request.form.get('custom_text', '').strip()
    if not custom_text and request.is_json:
        custom_text = (request.json or {}).get('custom_text', '').strip()

    if not custom_text:
        return jsonify({'error': 'Correction text cannot be empty'}), 400

    curr_text = version.current_text
    if issue.snippet in curr_text:
        version.corrected_text = curr_text.replace(issue.snippet, custom_text)
    elif issue.snippet.strip("...") in curr_text:
        version.corrected_text = curr_text.replace(issue.snippet.strip("..."), custom_text)

    issue.improved_text = custom_text
    issue.status = 'Modified'
    version.recalculate_scores()
    db.session.commit()

    log_audit_event(
        'SUGGESTION_MODIFIED',
        f"Manually edited correction for #{issue.id} on '{content.title}' v{version.version_number}",
        user=current_user
    )

    return jsonify({
        'success': True,
        'issue_id': issue.id,
        'status': 'Modified',
        'replacement': custom_text,
        'quality_score': version.quality_score,
        'compliance_score': version.compliance_score,
        'open_issues': version.open_issues_count,
        'has_open_serious': version.has_open_serious_issue
    })


@content_bp.route('/<int:content_id>/issue/<int:issue_id>/comment', methods=['POST'])
@login_required
def comment_issue(content_id):
    content = db.session.get(Content, content_id)
    if not content:
        return jsonify({'error': 'Content not found'}), 404

    issue = db.session.get(Issue, issue_id)
    if not issue or issue.version.content_id != content.id:
        return jsonify({'error': 'Issue not found'}), 404

    comment = request.form.get('comment', '').strip()
    if not comment and request.is_json:
        comment = (request.json or {}).get('comment', '').strip()

    issue.reviewer_comment = comment
    db.session.commit()

    return jsonify({
        'success': True,
        'issue_id': issue.id,
        'comment': comment
    })


# ---------------------------------------------------------------------------
# Document & Report Export Functionality (Section 11)
# ---------------------------------------------------------------------------

@content_bp.route('/<int:content_id>/export/original')
@login_required
def export_original(content_id):
    content = db.session.get(Content, content_id)
    if not content:
        abort(404)

    v_param = request.args.get('v', type=int)
    version = content.versions.filter_by(version_number=v_param).first() if v_param else content.latest_version
    if not version:
        abort(404)

    if version.file_path and os.path.exists(version.file_path):
        return send_file(
            version.file_path,
            as_attachment=True,
            download_name=version.original_filename or f"{content.title}_original.txt"
        )
    else:
        # Return plain text file
        buffer = io.BytesIO((version.raw_text or "").encode('utf-8'))
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{secure_filename(content.title)}_v{version.version_number}_original.txt",
            mimetype='text/plain'
        )


@content_bp.route('/<int:content_id>/export/corrected')
@login_required
def export_corrected(content_id):
    content = db.session.get(Content, content_id)
    if not content:
        abort(404)

    v_param = request.args.get('v', type=int)
    version = content.versions.filter_by(version_number=v_param).first() if v_param else content.latest_version
    if not version:
        abort(404)

    corrected_body = version.corrected_text or version.extracted_text or version.raw_text or ""
    buffer = io.BytesIO(corrected_body.encode('utf-8'))

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{secure_filename(content.title)}_v{version.version_number}_corrected.txt",
        mimetype='text/plain'
    )


@content_bp.route('/<int:content_id>/export/excel')
@login_required
def export_excel(content_id):
    content = db.session.get(Content, content_id)
    if not content:
        abort(404)

    v_param = request.args.get('v', type=int)
    version = content.versions.filter_by(version_number=v_param).first() if v_param else content.latest_version
    if not version:
        abort(404)

    output = generate_excel_issues_summary(version)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"BrandGuard_Issues_{secure_filename(content.title)}_v{version.version_number}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@content_bp.route('/<int:content_id>/export/pdf')
@login_required
def export_pdf(content_id):
    content = db.session.get(Content, content_id)
    if not content:
        abort(404)

    v_param = request.args.get('v', type=int)
    version = content.versions.filter_by(version_number=v_param).first() if v_param else content.latest_version
    if not version:
        abort(404)

    pdf_buffer = generate_pdf_review_report(version)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"BrandGuard_Report_{secure_filename(content.title)}_v{version.version_number}.pdf",
        mimetype='application/pdf'
    )
