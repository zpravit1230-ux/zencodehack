from datetime import datetime, timezone
import json
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # 'Creator', 'Reviewer', 'Manager'
    description = db.Column(db.String(255), nullable=True)
    
    users = db.relationship('User', back_populates='role', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    
    failed_logins = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    role = db.relationship('Role', back_populates='users')
    contents = db.relationship('Content', back_populates='creator', lazy='dynamic', cascade='all, delete-orphan')
    decisions = db.relationship('Decision', back_populates='reviewer', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', back_populates='user', lazy='dynamic')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_locked(self) -> bool:
        if self.locked_until:
            now = datetime.now(timezone.utc)
            lock_time = self.locked_until
            if lock_time.tzinfo is None:
                lock_time = lock_time.replace(tzinfo=timezone.utc)
            return now < lock_time
        return False

    @property
    def role_name(self) -> str:
        return self.role.name if self.role else 'Creator'

    def has_role(self, *role_names: str) -> bool:
        return self.role_name in role_names

    def __repr__(self):
        return f'<User {self.email} ({self.role_name})>'


class Content(db.Model):
    __tablename__ = 'contents'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    creator = db.relationship('User', back_populates='contents')
    versions = db.relationship('ContentVersion', back_populates='content', lazy='dynamic', cascade='all, delete-orphan', order_by='ContentVersion.version_number.desc()')

    @property
    def latest_version(self):
        return self.versions.first()

    def __repr__(self):
        return f'<Content {self.id}: {self.title}>'


class ContentVersion(db.Model):
    __tablename__ = 'content_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('contents.id'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False, default=1)
    
    file_path = db.Column(db.String(500), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)
    file_type = db.Column(db.String(50), nullable=False, default='text')  # 'text', 'pdf', 'docx', 'presentation', 'spreadsheet', 'image'
    
    raw_text = db.Column(db.Text, nullable=True)
    extracted_text = db.Column(db.Text, nullable=True)
    corrected_text = db.Column(db.Text, nullable=True)  # Dynamic text updated as suggestions are accepted/edited
    extracted_details_json = db.Column(db.Text, nullable=True, default='{}')
    page_data_json = db.Column(db.Text, nullable=True, default='[]')  # Full page-by-page mapping [{"page_number": 1, "heading": "...", "text": "..."}]
    
    quality_score = db.Column(db.Float, default=100.0, nullable=False)
    compliance_score = db.Column(db.Float, default=100.0, nullable=False)
    category_scores_json = db.Column(db.Text, nullable=True, default='{}')
    
    # Status: 'Draft', 'Processing', 'Needs Fixes', 'Waiting for Review', 'Approved', 'Rejected', 'Approved with Exception'
    status = db.Column(db.String(50), nullable=False, default='Draft')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    content = db.relationship('Content', back_populates='versions')
    issues = db.relationship('Issue', back_populates='version', lazy='dynamic', cascade='all, delete-orphan', order_by='Issue.id.asc()')
    decision = db.relationship('Decision', back_populates='version', uselist=False, cascade='all, delete-orphan')

    @property
    def extracted_details(self) -> dict:
        if not self.extracted_details_json:
            return {}
        try:
            return json.loads(self.extracted_details_json)
        except Exception:
            return {}

    @extracted_details.setter
    def extracted_details(self, data: dict):
        self.extracted_details_json = json.dumps(data)

    @property
    def page_data(self) -> list:
        if not self.page_data_json:
            return []
        try:
            return json.loads(self.page_data_json)
        except Exception:
            return []

    @page_data.setter
    def page_data(self, data: list):
        self.page_data_json = json.dumps(data)

    @property
    def category_scores(self) -> dict:
        if not self.category_scores_json:
            return {}
        try:
            return json.loads(self.category_scores_json)
        except Exception:
            return {}

    @category_scores.setter
    def category_scores(self, data: dict):
        self.category_scores_json = json.dumps(data)

    @property
    def current_text(self) -> str:
        return self.corrected_text or self.extracted_text or self.raw_text or ""

    @property
    def serious_issues_count(self) -> int:
        return self.issues.filter(Issue.severity.in_(['Serious', 'Critical', 'High']), Issue.status == 'Open').count()

    @property
    def warning_issues_count(self) -> int:
        return self.issues.filter(Issue.severity.in_(['Warning', 'Medium']), Issue.status == 'Open').count()

    @property
    def info_issues_count(self) -> int:
        return self.issues.filter(Issue.severity.in_(['Info', 'Low']), Issue.status == 'Open').count()

    @property
    def critical_issues_count(self) -> int:
        return self.issues.filter(Issue.severity.in_(['Critical', 'Serious']), Issue.status == 'Open').count()

    @property
    def high_issues_count(self) -> int:
        return self.issues.filter(Issue.severity == 'High', Issue.status == 'Open').count()

    @property
    def medium_issues_count(self) -> int:
        return self.issues.filter(Issue.severity.in_(['Medium', 'Warning']), Issue.status == 'Open').count()

    @property
    def low_issues_count(self) -> int:
        return self.issues.filter(Issue.severity.in_(['Low', 'Info']), Issue.status == 'Open').count()

    @property
    def accepted_issues_count(self) -> int:
        return self.issues.filter(Issue.status.in_(['Accepted', 'Modified'])).count()

    @property
    def rejected_issues_count(self) -> int:
        return self.issues.filter_by(status='Rejected').count()

    @property
    def open_issues_count(self) -> int:
        return self.issues.filter_by(status='Open').count()

    @property
    def total_issues_count(self) -> int:
        return self.issues.count()

    @property
    def has_open_serious_issue(self) -> bool:
        return self.serious_issues_count > 0

    def recalculate_scores(self):
        """Recalculates quality and compliance scores based on remaining open issues."""
        open_crit = self.critical_issues_count
        open_high = self.high_issues_count
        open_med = self.medium_issues_count
        open_low = self.low_issues_count

        # Deductions
        compliance_penalty = (open_crit * 25.0) + (open_high * 15.0) + (open_med * 8.0) + (open_low * 3.0)
        self.compliance_score = max(0.0, min(100.0, round(100.0 - compliance_penalty, 1)))

        quality_penalty = (open_crit * 20.0) + (open_high * 10.0) + (open_med * 5.0) + (open_low * 2.0)
        self.quality_score = max(0.0, min(100.0, round(100.0 - quality_penalty, 1)))

    def __repr__(self):
        return f'<ContentVersion {self.content_id} v{self.version_number} [{self.status}]>'


class Issue(db.Model):
    __tablename__ = 'issues'
    
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('content_versions.id'), nullable=False)
    
    # 7 AI Review Categories:
    # 'Grammar & Language', 'Brand Guidelines', 'Factual Accuracy', 
    # 'Marketing & Promotional Claims', 'Tone & Communication', 
    # 'Accessibility & Formatting', 'Privacy & Security' (or legacy WORDS, DETAILS, PROMISES, TONE, DESIGN)
    category = db.Column(db.String(80), nullable=False)
    # Severity: 'Critical', 'High', 'Medium', 'Low' (or legacy 'Serious', 'Warning', 'Info')
    severity = db.Column(db.String(20), nullable=False)
    rule_id = db.Column(db.String(100), nullable=True)
    
    page_number = db.Column(db.Integer, default=1, nullable=False)
    section_heading = db.Column(db.String(150), nullable=True, default='General')
    mistake_type = db.Column(db.String(100), nullable=True)
    
    snippet = db.Column(db.Text, nullable=False)
    why_it_matters = db.Column(db.Text, nullable=False)
    suggestion = db.Column(db.Text, nullable=False)
    improved_text = db.Column(db.Text, nullable=True)
    reviewer_comment = db.Column(db.Text, nullable=True)
    
    # Status: 'Open', 'Accepted', 'Rejected', 'Modified', 'Resolved', 'Waived'
    status = db.Column(db.String(20), default='Open', nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    version = db.relationship('ContentVersion', back_populates='issues')

    @property
    def display_severity(self) -> str:
        if self.severity in ['Critical', 'Serious']:
            return 'Critical'
        elif self.severity == 'High':
            return 'High'
        elif self.severity in ['Medium', 'Warning']:
            return 'Medium'
        return 'Low'

    @property
    def severity_badge_class(self) -> str:
        s = self.display_severity
        if s == 'Critical':
            return 'serious'
        elif s == 'High':
            return 'serious'
        elif s == 'Medium':
            return 'warning'
        return 'info'

    @property
    def review_category(self) -> str:
        if self.mistake_type and 'Privacy' in self.mistake_type or self.rule_id == 'BG006':
            return 'Privacy & Security'
        elif self.category == 'WORDS':
            if 'Brand' in (self.mistake_type or "") or 'Terminology' in (self.mistake_type or "") or 'BG002' in (self.rule_id or ""):
                return 'Brand Guidelines'
            return 'Grammar & Language'
        elif self.category == 'DETAILS':
            if 'Confidential' in (self.mistake_type or "") or 'BG015' in (self.rule_id or ""):
                return 'Privacy & Security'
            return 'Factual Accuracy'
        elif self.category == 'PROMISES':
            return 'Marketing & Promotional Claims'
        elif self.category == 'TONE':
            return 'Tone & Communication'
        elif self.category == 'DESIGN':
            return 'Accessibility & Formatting'
        return self.category

    def __repr__(self):
        return f'<Issue [{self.severity}] p.{self.page_number} {self.category}: {self.rule_id}>'


class Guideline(db.Model):
    __tablename__ = 'guidelines'
    
    id = db.Column(db.Integer, primary_key=True)
    # Types: WORDS, DETAILS, PROMISES, TONE, PALETTE, LOGO
    type = db.Column(db.String(50), nullable=False)
    key = db.Column(db.String(150), nullable=False)  # e.g. Banned word, Product attribute, Risky phrase, Palette hex
    value = db.Column(db.Text, nullable=False)  # e.g. Preferred replacement, Approved fact value, Guideline rule
    active = db.Column(db.Boolean, default=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f'<Guideline {self.type}: {self.key}>'


class Decision(db.Model):
    __tablename__ = 'decisions'
    
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('content_versions.id'), nullable=False, unique=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Outcome: 'Approve', 'Reject', 'Approve with Exception'
    outcome = db.Column(db.String(50), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    is_exception = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    version = db.relationship('ContentVersion', back_populates='decision')
    reviewer = db.relationship('User', back_populates='decisions')

    def __repr__(self):
        return f'<Decision v{self.version_id}: {self.outcome}>'


class ReviewerRule(db.Model):
    __tablename__ = 'reviewer_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Title / Directive name e.g. "Price Verification", "Strict Promises Check", "Tone & Slang"
    title = db.Column(db.String(150), nullable=False)
    # Category: WORDS, DETAILS, PROMISES, TONE, DESIGN, GENERAL
    category = db.Column(db.String(50), nullable=False, default='GENERAL')
    # Specific review instructions or checklist item
    instructions = db.Column(db.Text, nullable=False)
    # Severity / Enforcement: 'Mandatory', 'Recommended', 'Advisory'
    severity = db.Column(db.String(20), nullable=False, default='Mandatory')
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    reviewer = db.relationship('User', foreign_keys=[reviewer_id], backref=db.backref('assigned_rules', lazy='dynamic', cascade='all, delete-orphan'))
    creator = db.relationship('User', foreign_keys=[created_by_id])

    def __repr__(self):
        return f'<ReviewerRule {self.title} for User {self.reviewer_id} [{self.severity}]>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_email = db.Column(db.String(120), nullable=True)
    user_role = db.Column(db.String(50), nullable=True)
    
    action = db.Column(db.String(100), nullable=False)  # 'UPLOAD', 'CHECK_RUN', 'DECISION', 'EXCEPTION', 'ROLE_CHANGE', 'LOGIN', etc.
    details = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    user = db.relationship('User', back_populates='audit_logs')

    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user_email} at {self.created_at}>'
