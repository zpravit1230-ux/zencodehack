import pytest
from app.models import db, Guideline, AuditLog, User
from app.services.checker import run_brand_check
from app.services.trainer import train_brandguard_model, load_rules_from_csv

def login_as(client, email, password):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

def test_load_rules_from_csv():
    rules = load_rules_from_csv()
    assert len(rules) == 20
    assert rules[0]['rule_id'] == 'BG001'
    assert rules[19]['rule_id'] == 'BG020'

    rule_ids = [r['rule_id'] for r in rules]
    for i in range(1, 21):
        assert f"BG{i:03d}" in rule_ids


def test_train_brandguard_model_sync(client, init_database, app):
    with app.app_context():
        res = train_brandguard_model()
        assert res['total_rules'] == 20
        assert res['active'] == 20

        # Check guidelines were inserted
        bg001 = Guideline.query.filter(Guideline.key.like('%[BG001]%')).first()
        assert bg001 is not None
        assert bg001.type == 'TONE'

        bg002 = Guideline.query.filter(Guideline.key.like('%[BG002]%')).first()
        assert bg002 is not None
        assert bg002.type == 'WORDS'


def test_trained_rules_web_routes(client, init_database, app):
    # Creator cannot access trained-rules (403)
    login_as(client, 'creator@lumora.demo', 'Creator@123')
    res = client.get('/guidelines/trained-rules')
    assert res.status_code == 403
    client.get('/logout')

    # Manager can access trained-rules
    login_as(client, 'manager@lumora.demo', 'Manager@123')
    res_mgr = client.get('/guidelines/trained-rules')
    assert res_mgr.status_code == 200
    assert b'Trained Brand Governance Dataset' in res_mgr.data
    assert b'BG001' in res_mgr.data
    assert b'BG020' in res_mgr.data

    # Manager can trigger retraining
    res_retrain = client.post('/guidelines/train-dataset', follow_redirects=True)
    assert res_retrain.status_code == 200
    assert b'Successfully trained BrandGuard' in res_retrain.data


@pytest.mark.parametrize("text,expected_rule_id,expected_category,expected_severity", [
    ("Buy now or regret it forever!", "BG001", "TONE", "Warning"),
    ("Our users love this feature.", "BG002", "WORDS", "Info"),
    ("We guarantee 100% success on all products.", "BG003", "PROMISES", "Serious"),
    ("Subscribe for ₹799/month today.", "BG004", "DETAILS", "Serious"),
    ("Our competitor cheats every customer without exception.", "BG005", "PROMISES", "Serious"),
    ("Contact the customer at private.person@example.com directly.", "BG006", "DETAILS", "Serious"),
    ("A paid promotion is posted without disclosure.", "BG009", "PROMISES", "Serious"),
    ("A public post contains repeated spelling errors throughout.", "BG010", "WORDS", "Info"),
    ("This product will cure anxiety in seven days.", "BG011", "PROMISES", "Serious"),
    ("Click now or your account will be deleted immediately.", "BG012", "TONE", "Warning"),
    ("Our service is trusted by 10 million people across the globe.", "BG013", "DETAILS", "Serious"),
    ("A draft reveals an unreleased product launch date for next quarter.", "BG015", "DETAILS", "Serious"),
    ("A campaign uses an unlicensed stock photograph without attribution.", "BG016", "DESIGN", "Serious"),
    ("Campaign features an unapproved hashtag on social.", "BG018", "WORDS", "Warning"),
    ("AI-generated copy includes an invented product feature.", "BG019", "PROMISES", "Serious"),
    ("A critical-risk post is published while approval is pending.", "BG020", "DETAILS", "Serious")
])
def test_trained_dataset_detections(app, text, expected_rule_id, expected_category, expected_severity):
    with app.app_context():
        issues = run_brand_check(text, details={})
        flagged_rule_ids = [i['rule_id'] for i in issues]
        assert expected_rule_id in flagged_rule_ids

        matching_issue = next(i for i in issues if i['rule_id'] == expected_rule_id)
        assert matching_issue['category'] == expected_category
        assert matching_issue['severity'] == expected_severity
        assert len(matching_issue['suggestion']) > 0
        assert len(matching_issue['why_it_matters']) > 0


def test_clean_content_does_not_trigger_trained_violations(app):
    with app.app_context():
        clean_text = (
            "Lumora Plus is designed for thoughtful modern homes. "
            "Our members enjoy smooth ambient light transitions. "
            "Subscribe for ₹999/month backed by our 2 years warranty."
        )
        issues = run_brand_check(clean_text, details={'prices': ['₹999']})
        # Should have zero Serious issues and no BG violations
        bg_issues = [i for i in issues if i['rule_id'].startswith('BG')]
        assert len(bg_issues) == 0
