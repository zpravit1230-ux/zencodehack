import os
import csv
from typing import List, Dict, Any
from datetime import datetime, timezone
from app.models import db, Guideline, ReviewerRule, User, Role
from app.services.audit import log_audit_event

DATASET_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'brandguard_rules.csv')

# Category mapping to BrandGuard core types
CATEGORY_MAP = {
    'Tone': 'TONE',
    'Terminology': 'WORDS',
    'Unsupported Claim': 'PROMISES',
    'Factual Accuracy': 'DETAILS',
    'Competitor Claim': 'PROMISES',
    'Privacy': 'DETAILS',
    'Accessibility': 'DESIGN',
    'Visual Brand': 'DESIGN',
    'Disclosure': 'PROMISES',
    'Content Quality': 'WORDS',
    'Regulated Claim': 'PROMISES',
    'Authenticity': 'PROMISES',
    'Confidentiality': 'DETAILS',
    'Copyright': 'DESIGN',
    'Inclusivity': 'WORDS',
    'Campaign Compliance': 'WORDS',
    'Human Oversight': 'PROMISES',
    'Workflow Control': 'DETAILS'
}

# Severity normalization to BrandGuard standards (Serious, Warning, Info)
SEVERITY_MAP = {
    'Critical': 'Serious',
    'High': 'Serious',
    'Medium': 'Warning',
    'Low': 'Info'
}

def load_rules_from_csv(file_path: str = DATASET_PATH) -> List[Dict[str, str]]:
    """Reads the 20 rules from the CSV dataset."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found at: {file_path}")

    rules = []
    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rules.append({
                'rule_id': row.get('rule_id', '').strip(),
                'rule_name': row.get('rule_name', '').strip(),
                'rule_description': row.get('rule_description', '').strip(),
                'category': row.get('category', '').strip(),
                'severity': row.get('severity', '').strip(),
                'applicable_channels': row.get('applicable_channels', '').strip(),
                'example_violation': row.get('example_violation', '').strip(),
                'recommended_correction': row.get('recommended_correction', '').strip(),
                'responsible_roles': row.get('responsible_roles', '').strip(),
                'status': row.get('status', 'Active').strip()
            })
    return rules


def train_brandguard_model(file_path: str = DATASET_PATH, current_user: Any = None) -> Dict[str, Any]:
    """
    Trains / loads the web application on the dataset:
    1. Synchronizes guidelines in the database with BG001-BG020
    2. Maps rules to check engine categories and severity levels
    3. Configures reviewer directives for responsible reviewer roles
    4. Records an audit event for the dataset training run
    """
    rules = load_rules_from_csv(file_path)
    trained_count = 0
    updated_count = 0
    active_count = 0

    # Ensure Reviewers get assigned relevant directives
    reviewers = User.query.join(Role).filter(Role.name.in_(['Reviewer', 'Manager'])).all()
    manager_user = current_user or User.query.join(Role).filter(Role.name == 'Manager').first()

    for r in rules:
        rule_id = r['rule_id']
        mapped_type = CATEGORY_MAP.get(r['category'], 'WORDS')
        mapped_severity = SEVERITY_MAP.get(r['severity'], 'Warning')
        is_active = (r['status'].lower() == 'active')

        if is_active:
            active_count += 1

        # Check if guideline with this rule_id exists (we store rule_id in key or description)
        existing = Guideline.query.filter(
            (Guideline.key == f"[{rule_id}] {r['rule_name']}") | 
            (Guideline.description.like(f"%{rule_id}%"))
        ).first()

        rule_key = f"[{rule_id}] {r['rule_name']}"
        rule_value = f"{r['recommended_correction']} (Correction) | Description: {r['rule_description']}"
        desc = f"Rule {rule_id} | Cat: {r['category']} | Sev: {r['severity']} | Example: {r['example_violation']} | Roles: {r['responsible_roles']}"

        if existing:
            existing.type = mapped_type
            existing.key = rule_key
            existing.value = rule_value
            existing.description = desc[:255]
            existing.active = is_active
            existing.updated_at = datetime.now(timezone.utc)
            updated_count += 1
        else:
            new_guideline = Guideline(
                type=mapped_type,
                key=rule_key,
                value=rule_value,
                description=desc[:255],
                active=is_active
            )
            db.session.add(new_guideline)
            trained_count += 1

        # If rule specifies Reviewer responsibility, register ReviewerRule directive
        if 'Reviewer' in r['responsible_roles'] and manager_user:
            for rev in reviewers:
                existing_rr = ReviewerRule.query.filter_by(reviewer_id=rev.id, title=f"[{rule_id}] {r['rule_name']}").first()
                directive_severity = 'Mandatory' if r['severity'] in ['Critical', 'High'] else 'Recommended'
                if not existing_rr:
                    rr = ReviewerRule(
                        reviewer_id=rev.id,
                        created_by_id=manager_user.id,
                        title=f"[{rule_id}] {r['rule_name']}",
                        category=mapped_type,
                        instructions=f"{r['rule_description']} Recommended fix: {r['recommended_correction']}",
                        severity=directive_severity,
                        active=is_active
                    )
                    db.session.add(rr)

    db.session.commit()

    # Record training in audit log
    if manager_user:
        log_audit_event(
            'DATASET_TRAINED',
            f"Trained BrandGuard engine on dataset ({len(rules)} rules processed, {trained_count} created, {updated_count} refreshed, {active_count} active).",
            user=manager_user
        )

    return {
        'total_rules': len(rules),
        'created': trained_count,
        'updated': updated_count,
        'active': active_count,
        'categories': list(set(r['category'] for r in rules))
    }
