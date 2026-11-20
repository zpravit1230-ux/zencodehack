from app.models import Guideline
from app.services.checker import run_brand_check
from app.services.extractor import extract_key_details

def setup_guidelines(app):
    with app.app_context():
        rules = [
            # Words
            Guideline(type='WORDS', key='Lumora Pro', value='Lumora Plus', description='Prototype name banned externally', active=True),
            Guideline(type='WORDS', key='cheap', value='affordable', description='Cheap diminishes brand prestige', active=True),
            # Details
            Guideline(type='DETAILS', key='Price - Lumora Plus', value='Rs. 2,499', description='MSRP for Lumora Plus', active=True),
            Guideline(type='DETAILS', key='Warranty', value='2 years', description='Official hardware warranty', active=True),
            # Promises
            Guideline(type='PROMISES', key='gentle wake-up routines', value='Tested in 500+ home trials', description='Approved claim', active=True),
            # Palette
            Guideline(type='PALETTE', key='#0B3D91', value='Lumora Deep Blue', description='Primary brand color', active=True),
            Guideline(type='PALETTE', key='#F5B700', value='Lumora Amber', description='Accent color', active=True)
        ]
        return rules

def test_clean_sample_produces_no_serious_issues(app):
    with app.app_context():
        guidelines = setup_guidelines(app)
        clean_text = (
            "Lumora Plus is our flagship ambient lighting system. "
            "Designed for thoughtful homes, it delivers smooth transitions and gentle wake-up routines. "
            "Available now for Rs. 2,499 with a standard 2 years warranty."
        )
        details = extract_key_details(clean_text)
        issues = run_brand_check(clean_text, details, file_type='text', guidelines=guidelines)

        serious_issues = [i for i in issues if i['severity'] == 'Serious']
        warning_issues = [i for i in issues if i['severity'] == 'Warning']

        assert len(serious_issues) == 0, f"Expected 0 serious issues, found: {serious_issues}"
        assert len(warning_issues) == 0, f"Expected 0 warning issues, found: {warning_issues}"


def test_demo_flyer_produces_expected_serious_issues(app):
    with app.app_context():
        guidelines = setup_guidelines(app)
        # Flyer text with banned prototype name (Lumora Pro), wrong price (Rs. 1,999), and risky claim (100% guaranteed)
        flyer_text = (
            "ACT FAST! Buy the revolutionary Lumora Pro today for only Rs. 1,999! "
            "It is 100% guaranteed to be the best in the world! "
            "Get yours now before stock runs out!!!"
        )
        details = extract_key_details(flyer_text)
        issues = run_brand_check(flyer_text, details, file_type='text', guidelines=guidelines)

        serious_issues = [i for i in issues if i['severity'] == 'Serious']
        serious_categories = [i['category'] for i in serious_issues]

        # Verify Serious issues generated in WORDS, DETAILS, and PROMISES
        assert 'WORDS' in serious_categories, "Expected Serious WORDS issue for 'Lumora Pro'"
        assert 'DETAILS' in serious_categories, "Expected Serious DETAILS issue for wrong price 'Rs. 1,999'"
        assert 'PROMISES' in serious_categories, "Expected Serious PROMISES issue for '100% guaranteed'"

        # Verify TONE issues detected
        tone_issues = [i for i in issues if i['category'] == 'TONE']
        assert len(tone_issues) > 0, "Expected TONE issues for ALL CAPS and multiple exclamations"

        # Check suggestions are present
        for issue in issues:
            assert issue['suggestion'] != ""
            assert issue['why_it_matters'] != ""
            assert issue['snippet'] != ""

