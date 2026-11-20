import re
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from app.models import User

class RegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[
        DataRequired(message="Full name is required."),
        Length(min=2, max=100, message="Full name must be between 2 and 100 characters.")
    ])
    email = StringField('Email Address', validators=[
        DataRequired(message="Email address is required."),
        Email(message="Please enter a valid email address.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required."),
        Length(min=8, message="Password must be at least 8 characters long.")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password."),
        EqualTo('password', message="Passwords must match.")
    ])
    submit = SubmitField('Create Account')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.lower().strip()).first()
        if user:
            raise ValidationError('An account with this email address already exists.')

    def validate_password(self, password):
        val = password.data
        if not re.search(r'[A-Za-z]', val) or not re.search(r'\d', val):
            raise ValidationError('Password must contain at least one letter and one number.')


class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[
        DataRequired(message="Email address is required."),
        Email(message="Please enter a valid email address.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required.")
    ])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class ContentUploadForm(FlaskForm):
    title = StringField('Content Title or Campaign Name', validators=[
        DataRequired(message="Title is required."),
        Length(min=3, max=200, message="Title must be between 3 and 200 characters.")
    ])
    pasted_text = TextAreaField('Paste Text Directly (Optional)')
    file = FileField('Upload Document (PDF, DOCX, DOC, PPTX, XLSX, CSV, TXT, PNG, JPG - Max 10MB)', validators=[
        Optional(),
        FileAllowed(
            ['txt', 'pdf', 'docx', 'doc', 'ppt', 'pptx', 'xls', 'xlsx', 'csv', 'png', 'jpg', 'jpeg', 'webp'],
            'Allowed formats: PDF, DOC/DOCX, PPT/PPTX, XLS/XLSX, CSV, TXT, PNG, JPG, WEBP'
        )
    ])
    submit = SubmitField('Submit for AI Document Review')


class ContentVersionUploadForm(FlaskForm):
    pasted_text = TextAreaField('Pasted Updated Text (Optional)')
    file = FileField('Upload Updated Document (Max 10MB)', validators=[
        Optional(),
        FileAllowed(
            ['txt', 'pdf', 'docx', 'doc', 'ppt', 'pptx', 'xls', 'xlsx', 'csv', 'png', 'jpg', 'jpeg', 'webp'],
            'Allowed formats: PDF, DOC/DOCX, PPT/PPTX, XLS/XLSX, CSV, TXT, PNG, JPG, WEBP'
        )
    ])
    notes = StringField('Summary of Changes (Optional)')
    submit = SubmitField('Upload New Version & Re-analyze')


class GuidelineForm(FlaskForm):
    type = SelectField('Category', choices=[
        ('WORDS', 'WORDS (Banned words & Preferred names)'),
        ('DETAILS', 'DETAILS (Approved Facts & Specs)'),
        ('PROMISES', 'PROMISES (Risky Claims vs Approved Claims)'),
        ('TONE', 'TONE (Brand Voice & Style Rules)'),
        ('PALETTE', 'PALETTE (Brand Hex Colors)'),
        ('LOGO', 'LOGO (Logo Requirements & Contrast)')
    ], validators=[DataRequired()])
    key = StringField('Key / Flagged Item / Fact Name', validators=[
        DataRequired(message="Key identifier is required."),
        Length(max=150)
    ])
    value = TextAreaField('Value / Preferred Replacement / Rule Detail', validators=[
        DataRequired(message="Rule value or guidance is required.")
    ])
    description = StringField('Why It Matters / Context Note', validators=[
        Optional(),
        Length(max=255)
    ])
    active = BooleanField('Active Rule', default=True)
    submit = SubmitField('Save Guideline')


class DecisionForm(FlaskForm):
    outcome = SelectField('Decision', choices=[
        ('Approve', 'Approve for Publishing'),
        ('Reject', 'Reject (Needs Revision)'),
        ('Approve with Exception', 'Approve with Exception')
    ], validators=[DataRequired()])
    reason = TextAreaField('Review Notes / Exception Reason', validators=[Optional()])
    submit = SubmitField('Record Decision')


class RoleChangeForm(FlaskForm):
    role_name = SelectField('Assign Role', choices=[
        ('Creator', 'Creator (Writer / Designer)'),
        ('Reviewer', 'Reviewer (QA / Approver)'),
        ('Manager', 'Manager (Brand Lead / Admin)')
    ], validators=[DataRequired()])
    submit = SubmitField('Update Role')


class ReviewerRuleForm(FlaskForm):
    reviewer_id = SelectField('Assign to Reviewer', coerce=int, validators=[
        DataRequired(message="Please select a reviewer.")
    ])
    title = StringField('Rule Title / Directive', validators=[
        DataRequired(message="Rule title is required."),
        Length(min=3, max=150, message="Title must be between 3 and 150 characters.")
    ])
    category = SelectField('Brand Category / Focus Scope', choices=[
        ('GENERAL', 'GENERAL (All Scope / Holistic Review)'),
        ('WORDS', 'WORDS (Terminology & Banned Names)'),
        ('DETAILS', 'DETAILS (Specs, Prices & Launch Dates)'),
        ('PROMISES', 'PROMISES (Claims, Guarantees & Legal)'),
        ('TONE', 'TONE (Brand Voice, Exclamations & Slang)'),
        ('DESIGN', 'DESIGN (Palette, Contrast & Visuals)')
    ], default='GENERAL', validators=[DataRequired()])
    instructions = TextAreaField('Reviewer Instructions / Checklist Criteria', validators=[
        DataRequired(message="Reviewer instructions are required.")
    ])
    severity = SelectField('Enforcement Level', choices=[
        ('Mandatory', 'Mandatory (Reviewer must verify before approval)'),
        ('Recommended', 'Recommended (Standard best practice checklist)'),
        ('Advisory', 'Advisory (Helpful reminder & brand guidance)')
    ], default='Mandatory', validators=[DataRequired()])
    active = BooleanField('Active Rule', default=True)
    submit = SubmitField('Save Reviewer Rule')

