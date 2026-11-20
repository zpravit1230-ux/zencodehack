"""
BrandGuard AI - Seed Script (idempotent, supports --reset)
Populates realistic demo guidelines, users, content samples, issues, decisions, and audit history.
"""

import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw
import docx
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app import create_app
from app.models import db, Role, User, Guideline, Content, ContentVersion, Issue, Decision, AuditLog
from app.services.extractor import extract_text_from_file, extract_key_details
from app.services.checker import run_brand_check

def parse_args():
    parser = argparse.ArgumentParser(description="Seed database with demo brand data.")
    parser.add_argument('--reset', action='store_true', help="Drop all tables and re-create fresh.")
    return parser.parse_args()


def seed_database(reset=False):
    app = create_app()
    with app.app_context():
        if reset:
            print("==> Resetting database tables...")
            db.drop_all()
            db.create_all()
        else:
            db.create_all()

        upload_dir = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)

        # ---------------------------------------------------------------------
        # 1. ROLES
        # ---------------------------------------------------------------------
        print("==> Seeding Roles...")
        roles = {}
        for r_name, r_desc in [
            ('Creator', 'Writes copy, uploads content, sees issues, and uploads revisions'),
            ('Reviewer', 'Verifies compliance, approves, rejects, or grants exceptions'),
            ('Manager', 'Manages brand guidelines, team user roles, and audits history')
        ]:
            role = Role.query.filter_by(name=r_name).first()
            if not role:
                role = Role(name=r_name, description=r_desc)
                db.session.add(role)
            roles[r_name] = role
        db.session.commit()

        # ---------------------------------------------------------------------
        # 2. USERS (Demo Accounts)
        # ---------------------------------------------------------------------
        print("==> Seeding Users...")
        demo_users_data = [
            ('Maya Raman', 'manager@lumora.demo', 'Manager@123', 'Manager'),
            ('Rachel Thorne', 'reviewer@lumora.demo', 'Reviewer@123', 'Reviewer'),
            ('Priya Sharma', 'priya@lumora.demo', 'Creator@123', 'Creator'),
            ('Arjun Mehta', 'arjun@lumora.demo', 'Creator@123', 'Creator')
        ]
        users = {}
        for name, email, password, role_name in demo_users_data:
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    full_name=name,
                    email=email,
                    role_id=roles[role_name].id
                )
                user.set_password(password)
                db.session.add(user)
            users[email] = user
        db.session.commit()

        # ---------------------------------------------------------------------
        # 3. GUIDELINES (15 Words, 10 Facts, 6 Promises, Tone, Palette, Logo)
        # ---------------------------------------------------------------------
        print("==> Seeding Guidelines...")
        guidelines_data = [
            # WORDS (15 items)
            ('WORDS', 'Lumora Pro', 'Lumora Plus', 'Prototype product codename; strictly prohibited externally.'),
            ('WORDS', 'Lumora Lite', 'Lumora Mini', 'Deprecated naming; use official compact brand name Lumora Mini.'),
            ('WORDS', 'Cheap', 'Affordable / Accessible', 'The word cheap degrades premium brand positioning.'),
            ('WORDS', 'Knockoff', 'Alternative / Comparable', 'Unprofessional competitor reference.'),
            ('WORDS', 'Discount bulb', 'Promotional offering', 'Avoid bargain-bin phrasing for flagship hardware.'),
            ('WORDS', 'Smartbulb', 'Smart Bulb', 'Approved spelling requires two separate capitalized words.'),
            ('WORDS', 'IoT gadget', 'Ambient Smart Device', 'Technical jargon confusing to everyday homeowners.'),
            ('WORDS', 'Cheaply made', 'Precision engineered', 'Direct negative connotation.'),
            ('WORDS', 'Lumora basic', 'Lumora Standard', 'Basic implies low quality.'),
            ('WORDS', 'Color changing thing', 'Adaptive Spectrum Lighting', 'Use descriptive technical brand terminology.'),
            ('WORDS', 'Lightbulb', 'Smart Lighting System', 'Lumora sells an integrated system, not just a bulb.'),
            ('WORDS', 'Super cheap', 'Competitively priced', 'Preserve premium brand perception.'),
            ('WORDS', 'Fake lights', 'Non-certified replicas', 'Professional clarity.'),
            ('WORDS', 'lumora', 'Lumora', 'Brand name must always be capitalized.'),
            ('WORDS', 'lumora plus', 'Lumora Plus', 'Product names require Title Case.'),

            # DETAILS / APPROVED FACTS (10 items)
            ('DETAILS', 'Product Name - Flagship', 'Lumora Plus', 'Flagship multi-zone ambient lighting system.'),
            ('DETAILS', 'Product Name - Compact', 'Lumora Mini', 'Compact accent ambient light for desks & bedrooms.'),
            ('DETAILS', 'Price - Lumora Plus', 'Rs. 2,499', 'Official launch MSRP across all Indian retail channels.'),
            ('DETAILS', 'Price - Lumora Mini', 'Rs. 1,499', 'Official launch MSRP for compact model.'),
            ('DETAILS', 'Launch Date', 'Oct 15, 2026', 'Official market launch event date.'),
            ('DETAILS', 'Warranty', '2 years', 'Standard manufacturer limited warranty on all fixtures.'),
            ('DETAILS', 'LED Lifespan', '25,000 hours', 'Calculated rated operational lifespan at 70% lumen maintenance.'),
            ('DETAILS', 'Color Temperature', '2200K to 6500K', 'Tunable white spectrum from warm sunset to daylight.'),
            ('DETAILS', 'Connectivity', 'Wi-Fi 6 & Bluetooth 5.3 Low Energy', 'Dual radio wireless specs.'),
            ('DETAILS', 'Power Consumption', '9 Watts max', 'Energy consumption at 100% white luminance.'),

            # PROMISES / APPROVED CLAIMS (6 items)
            ('PROMISES', 'gentle wake-up routines', 'Tested in 500+ home trials', 'Backed by clinical chronobiology research.'),
            ('PROMISES', '80% more energy efficient', 'Compared to standard 60W incandescent', 'Verified laboratory testing.'),
            ('PROMISES', 'True-to-life color rendering', '95+ Color Rendering Index (CRI)', 'Certified lab spectrometer measurement.'),
            ('PROMISES', 'Seamless smart home integration', 'Works with Matter, Apple Home, Google Home', 'Official protocol certification.'),
            ('PROMISES', 'Two-year hassle-free warranty', 'Free doorstep hardware replacement', 'Official customer support SLA.'),
            ('PROMISES', 'Recyclable aluminum chassis', 'Over 85% post-consumer recycled metal', 'Environmental compliance statement.'),

            # TONE
            ('TONE', 'Exclamation Marks', 'Maximum 1 per document', 'Confident, calm tone; avoid shouting or aggressive hype.'),
            ('TONE', 'ALL CAPS', 'Never use ALL CAPS for headlines or copy', 'Feels aggressive and harms readability.'),
            ('TONE', 'Urgency Phrasing', 'Avoid "ACT FAST", "Hurry", "Insane deal"', 'Premium brands never deploy high-pressure sales urgency.'),
            ('TONE', 'Voice Characteristics', 'Friendly, Clear, Confident, Not Pushy', 'Core brand tone pillars.'),

            # PALETTE
            ('PALETTE', '#0B3D91', 'Lumora Deep Blue', 'Primary brand color symbolizing calm, evening illumination.'),
            ('PALETTE', '#F5B700', 'Lumora Amber', 'Accent brand color representing warm filament sunrise glow.'),
            ('PALETTE', '#FFFFFF', 'Clean White', 'Essential negative space and balanced background.'),
            ('PALETTE', '#1A1A1A', 'Dark Charcoal', 'High-contrast typography and UI elements.'),

            # LOGO
            ('LOGO', 'Clear Space', 'Minimum 20px padding around Lumora wordmark', 'Ensure brand mark stands out distinctly.'),
            ('LOGO', 'Color Variants', 'Pure White on dark backgrounds, Deep Blue on light', 'Contrast must exceed 4.5:1.')
        ]

        for g_type, g_key, g_val, g_desc in guidelines_data:
            existing = Guideline.query.filter_by(type=g_type, key=g_key).first()
            if not existing:
                rule = Guideline(type=g_type, key=g_key, value=g_val, description=g_desc, active=True)
                db.session.add(rule)
        db.session.commit()

        # ---------------------------------------------------------------------
        # 3.5. TRAINED BRANDGUARD RULES DATASET (BG001 - BG020)
        # ---------------------------------------------------------------------
        print("==> Training BrandGuard on 20-Rule Governance Dataset (BG001-BG020)...")
        from app.services.trainer import train_brandguard_model
        train_result = train_brandguard_model()
        print(f"    Trained {train_result['total_rules']} rules ({train_result['created']} new, {train_result['updated']} updated, {train_result['active']} active).")

        # ---------------------------------------------------------------------
        # 4. SAMPLE CONTENT & REAL FILES
        # ---------------------------------------------------------------------
        print("==> Generating demo documents & sample files...")

        all_rules = Guideline.query.filter_by(active=True).all()
        now = datetime.now(timezone.utc)

        # Helper to create content + version + run check
        def create_sample(title, creator_email, text, file_type='text', file_name=None, days_ago=2):
            creator = users[creator_email]
            c = Content.query.filter_by(title=title).first()
            if not c:
                c = Content(
                    title=title,
                    creator_id=creator.id,
                    created_at=now - timedelta(days=days_ago),
                    updated_at=now - timedelta(days=days_ago)
                )
                db.session.add(c)
                db.session.commit()

            v = c.latest_version
            if not v:
                v = ContentVersion(
                    content_id=c.id,
                    version_number=1,
                    raw_text=text,
                    extracted_text=text,
                    file_type=file_type,
                    original_filename=file_name,
                    status='Processing',
                    created_at=c.created_at
                )
                db.session.add(v)
                db.session.commit()

                # Run details & brand check
                details = extract_key_details(text, v.file_path)
                v.extracted_details = details
                issues = run_brand_check(text, details, file_type=file_type, file_path=v.file_path, guidelines=all_rules)
                for iss in issues:
                    db.session.add(Issue(
                        version_id=v.id,
                        category=iss['category'],
                        severity=iss['severity'],
                        rule_id=iss['rule_id'],
                        snippet=iss['snippet'],
                        why_it_matters=iss['why_it_matters'],
                        suggestion=iss['suggestion'],
                        status='Open'
                    ))
                v.status = 'Needs Fixes' if v.has_open_serious_issue else 'Waiting for Review'
                db.session.commit()
            return c, v

        # --- Sample (a): Clean post that is Approved ---
        text_a = (
            "Lumora Plus is our flagship ambient lighting system. "
            "Designed for thoughtful modern homes, it delivers smooth color transitions and gentle wake-up routines. "
            "Available now across India for Rs. 2,499 with our standard 2 years warranty."
        )
        c_a, v_a = create_sample("Lumora Plus Diwali Launch Post", "priya@lumora.demo", text_a, days_ago=5)
        v_a.status = 'Approved'
        if not v_a.decision:
            dec_a = Decision(
                version_id=v_a.id,
                reviewer_id=users['reviewer@lumora.demo'].id,
                outcome='Approve',
                reason='Flawless copy. Brand facts and warranty verified.',
                is_exception=False,
                created_at=now - timedelta(days=4)
            )
            db.session.add(dec_a)
        db.session.commit()

        # --- Sample (b & c): Flyer with wrong price & unapproved claim, then V2 fixed ---
        text_b1 = (
            "ACT FAST! Buy the revolutionary Lumora Pro today for only Rs. 1,999! "
            "It is 100% guaranteed to be the best in the world and never fails! "
            "Get yours now before stock runs out!!!"
        )
        c_b, v_b1 = create_sample("Festival Clearance Flyer", "arjun@lumora.demo", text_b1, days_ago=3)
        v_b1.status = 'Needs Fixes'

        # Create Version 2 of Festival Clearance Flyer (Waiting for Review)
        if c_b.versions.count() < 2:
            text_b2 = (
                "Introducing the new Lumora Plus ambient lighting system for Rs. 2,499. "
                "Enjoy smooth transitions and gentle wake-up routines designed for everyday living, backed by our 2 years warranty."
            )
            v_b2 = ContentVersion(
                content_id=c_b.id,
                version_number=2,
                raw_text=text_b2,
                extracted_text=text_b2,
                file_type='text',
                status='Processing',
                created_at=now - timedelta(days=1)
            )
            db.session.add(v_b2)
            db.session.commit()

            details_b2 = extract_key_details(text_b2)
            v_b2.extracted_details = details_b2
            issues_b2 = run_brand_check(text_b2, details_b2, guidelines=all_rules)
            for iss in issues_b2:
                db.session.add(Issue(
                    version_id=v_b2.id,
                    category=iss['category'],
                    severity=iss['severity'],
                    rule_id=iss['rule_id'],
                    snippet=iss['snippet'],
                    why_it_matters=iss['why_it_matters'],
                    suggestion=iss['suggestion']
                ))
            v_b2.status = 'Waiting for Review'
            db.session.commit()

        # --- Sample (d): Social post with Tone problems (Warnings) ---
        text_d = (
            "HURRY UP! Grab your Lumora Plus smart bulb right now before the insane deal ends! "
            "You cannot miss this once in a lifetime opportunity to upgrade your lighting!!!"
        )
        c_d, v_d = create_sample("Instagram Flash Announcement", "priya@lumora.demo", text_d, days_ago=2)

        # --- Sample (e): Post Approved with Exception (reason recorded) ---
        text_e = (
            "Limited legacy release: Special regional clearance for Lumora Pro fixtures at participating offline partners. "
            "Valid while channel stock lasts."
        )
        c_e, v_e = create_sample("Legacy Channel Notice (Archive)", "arjun@lumora.demo", text_e, days_ago=4)
        v_e.status = 'Approved with Exception'
        if not v_e.decision:
            dec_e = Decision(
                version_id=v_e.id,
                reviewer_id=users['manager@lumora.demo'].id,
                outcome='Approve with Exception',
                reason='Executive exception approved by Brand Lead for regional clearance of legacy pre-launch partner packaging.',
                is_exception=True,
                created_at=now - timedelta(days=3)
            )
            db.session.add(dec_e)
        db.session.commit()

        # --- Sample (f): Sample Image with off-palette color (PNG) ---
        png_filename = "lumora_promo_banner.png"
        png_path = os.path.join(upload_dir, png_filename)
        # Create image with off-palette hot magenta (#FF007F) and dark background
        img = Image.new('RGB', (400, 200), color='#1A1A1A')
        draw = ImageDraw.Draw(img)
        # Off-palette magenta element
        draw.rectangle([50, 40, 350, 160], fill='#FF007F')
        img.save(png_path)

        c_f, v_f = create_sample(
            title="Display Banner Visual Asset",
            creator_email="arjun@lumora.demo",
            text="[Image Asset: lumora_promo_banner.png]",
            file_type='image',
            file_name=png_filename,
            days_ago=1
        )
        v_f.file_path = png_path
        # Extract dominant colors & re-check
        details_f = extract_key_details("[Image Asset: lumora_promo_banner.png]", png_path)
        v_f.extracted_details = details_f
        # Add design issue if not present
        if v_f.issues.filter_by(category='DESIGN').count() == 0:
            for d_col in details_f.get('dominant_colors', []):
                db.session.add(Issue(
                    version_id=v_f.id,
                    category='DESIGN',
                    severity='Warning',
                    rule_id='DESIGN-OFF-PALETTE',
                    snippet=f"Dominant color {d_col}",
                    why_it_matters=f"Off-palette color {d_col} does not match Lumora's primary palette (#0B3D91, #F5B700).",
                    suggestion="Recolor banner background using Lumora Deep Blue (#0B3D91) or Warm Amber (#F5B700).",
                    status='Open'
                ))
            db.session.commit()

        # Generate DOCX and PDF sample files in uploads for full realism
        docx_filename = "Lumora_Plus_Product_Brief.docx"
        docx_path = os.path.join(upload_dir, docx_filename)
        doc = docx.Document()
        doc.add_heading("Lumora Plus Product Specification", 0)
        doc.add_paragraph("Official technical brief for marketing and channel distribution teams.")
        doc.add_paragraph("MSRP: Rs. 2,499 | Hardware Warranty: 2 years | Rated Lifespan: 25,000 hours")
        doc.save(docx_path)

        pdf_filename = "Lumora_Brand_Book_Summary.pdf"
        pdf_path = os.path.join(upload_dir, pdf_filename)
        pdf = canvas.Canvas(pdf_path, pagesize=letter)
        pdf.drawString(100, 750, "Lumora Brand Guidelines & Guardrails")
        pdf.drawString(100, 730, "Primary Palette: #0B3D91 (Deep Blue), #F5B700 (Amber)")
        pdf.drawString(100, 710, "Tone: Friendly, Clear, Confident, Never Pushy")
        pdf.save()

        # ---------------------------------------------------------------------
        # 4.5. REVIEWER RULES (Configured by Manager; vary per Reviewer)
        # ---------------------------------------------------------------------
        print("==> Seeding custom Reviewer Rules (varying per reviewer)...")
        from app.models import ReviewerRule
        reviewer_user = users['reviewer@lumora.demo']
        manager_user = users['manager@lumora.demo']

        sample_reviewer_rules = [
            (
                reviewer_user.id,
                "Price & Warranty Cross-Check",
                "DETAILS",
                "Verify all copy explicitly states the approved launch MSRP of Rs. 2,499 and 2-year warranty before approving.",
                "Mandatory"
            ),
            (
                reviewer_user.id,
                "Risky Promise & Claim Scrutiny",
                "PROMISES",
                "Scrutinize unapproved claims such as '100% cure', 'guaranteed never fails', or 'world's best'. Must match approved claims list.",
                "Mandatory"
            ),
            (
                reviewer_user.id,
                "Brand Voice & Slang Audit",
                "TONE",
                "Flag informal slang, shouty ALL CAPS, or excessive exclamations (maximum 1 per document). Keep tone confident and friendly.",
                "Recommended"
            ),
            (
                manager_user.id,
                "Executive Visual & Color Palette Integrity",
                "DESIGN",
                "Inspect uploaded creative banners for dominant off-palette colors and verify contrast ratio meets WCAG 4.5:1 standards.",
                "Mandatory"
            )
        ]

        for rev_id, r_title, r_cat, r_inst, r_sev in sample_reviewer_rules:
            existing_rr = ReviewerRule.query.filter_by(reviewer_id=rev_id, title=r_title).first()
            if not existing_rr:
                rr = ReviewerRule(
                    reviewer_id=rev_id,
                    created_by_id=manager_user.id,
                    title=r_title,
                    category=r_cat,
                    instructions=r_inst,
                    severity=r_sev,
                    active=True,
                    created_at=now - timedelta(days=7)
                )
                db.session.add(rr)
        db.session.commit()

        # ---------------------------------------------------------------------
        # 5. AUDIT LOGS (~40 entries)
        # ---------------------------------------------------------------------
        print("==> Seeding ~40 Audit Log entries across past 14 days...")
        # Clear existing logs if reset
        if AuditLog.query.count() < 35:
            audit_events = [
                ('LOGIN_SUCCESS', 'User manager@lumora.demo logged in successfully', 'manager@lumora.demo', 'Manager', 14),
                ('GUIDELINE_ADD', "Created guideline [WORDS] 'Lumora Pro': 'Lumora Plus'", 'manager@lumora.demo', 'Manager', 14),
                ('GUIDELINE_ADD', "Created guideline [DETAILS] 'Price - Lumora Plus': 'Rs. 2,499'", 'manager@lumora.demo', 'Manager', 14),
                ('GUIDELINE_ADD', "Created guideline [PALETTE] '#0B3D91': 'Lumora Deep Blue'", 'manager@lumora.demo', 'Manager', 14),
                ('GUIDELINE_ADD', "Created guideline [TONE] 'Exclamation Marks': 'Max 1 per doc'", 'manager@lumora.demo', 'Manager', 13),
                ('REGISTER', 'New user registered: priya@lumora.demo with role Creator', 'priya@lumora.demo', 'Creator', 13),
                ('LOGIN_SUCCESS', 'User priya@lumora.demo logged in successfully', 'priya@lumora.demo', 'Creator', 13),
                ('REGISTER', 'New user registered: arjun@lumora.demo with role Creator', 'arjun@lumora.demo', 'Creator', 12),
                ('REGISTER', 'New user registered: reviewer@lumora.demo with role Creator', 'reviewer@lumora.demo', 'Creator', 12),
                ('ROLE_CHANGE', "Changed role of reviewer@lumora.demo from 'Creator' to 'Reviewer'", 'manager@lumora.demo', 'Manager', 12),
                ('LOGIN_SUCCESS', 'User reviewer@lumora.demo logged in successfully', 'reviewer@lumora.demo', 'Reviewer', 11),
                ('UPLOAD', "Created content submission 'Lumora Plus Diwali Launch Post' (v1)", 'priya@lumora.demo', 'Creator', 5),
                ('READ_CONTENT', "Extracted 214 chars from pasted text for 'Lumora Plus Diwali Launch Post' v1", 'priya@lumora.demo', 'Creator', 5),
                ('CHECK_RUN', "Brand check executed for 'Lumora Plus Diwali Launch Post' v1: 0 Serious, 0 Warning, 0 Info. Status: Waiting for Review", 'priya@lumora.demo', 'Creator', 5),
                ('LOGIN_SUCCESS', 'User reviewer@lumora.demo logged in successfully', 'reviewer@lumora.demo', 'Reviewer', 4),
                ('DECISION', "Decision recorded on 'Lumora Plus Diwali Launch Post' v1: Approve. Reason: Flawless copy. Brand facts and warranty verified.", 'reviewer@lumora.demo', 'Reviewer', 4),
                ('UPLOAD', "Created content submission 'Legacy Channel Notice (Archive)' (v1)", 'arjun@lumora.demo', 'Creator', 4),
                ('CHECK_RUN', "Brand check executed for 'Legacy Channel Notice (Archive)' v1: 1 Serious (Lumora Pro). Status: Needs Fixes", 'arjun@lumora.demo', 'Creator', 4),
                ('EXCEPTION', "Decision recorded on 'Legacy Channel Notice (Archive)' v1: Approve with Exception. Reason: Executive exception approved by Brand Lead for regional clearance.", 'manager@lumora.demo', 'Manager', 3),
                ('UPLOAD', "Created content submission 'Festival Clearance Flyer' (v1)", 'arjun@lumora.demo', 'Creator', 3),
                ('CHECK_RUN', "Brand check executed for 'Festival Clearance Flyer' v1: 3 Serious, 2 Warning. Status: Needs Fixes", 'arjun@lumora.demo', 'Creator', 3),
                ('LOGIN_FAILED', 'Failed login attempt for non-existent email: unknown@guest.demo', None, 'System', 3),
                ('LOGIN_FAILED', 'Failed login for arjun@lumora.demo (4 attempts remaining)', None, 'System', 2),
                ('LOGIN_SUCCESS', 'User arjun@lumora.demo logged in successfully', 'arjun@lumora.demo', 'Creator', 2),
                ('UPLOAD', "Created content submission 'Instagram Flash Announcement' (v1)", 'priya@lumora.demo', 'Creator', 2),
                ('CHECK_RUN', "Brand check executed for 'Instagram Flash Announcement' v1: 0 Serious, 3 Warning (Tone). Status: Waiting for Review", 'priya@lumora.demo', 'Creator', 2),
                ('FIX', "Submitted revised version v2 for 'Festival Clearance Flyer'", 'arjun@lumora.demo', 'Creator', 1),
                ('READ_CONTENT', "Extracted 198 chars from updated text for 'Festival Clearance Flyer' v2", 'arjun@lumora.demo', 'Creator', 1),
                ('CHECK_RUN', "Brand check executed for 'Festival Clearance Flyer' v2: 0 Serious, 0 Warning. Status: Waiting for Review", 'arjun@lumora.demo', 'Creator', 1),
                ('UPLOAD', "Created content submission 'Display Banner Visual Asset' (v1)", 'arjun@lumora.demo', 'Creator', 1),
                ('READ_CONTENT', "Extracted image metadata & palette for lumora_promo_banner.png", 'arjun@lumora.demo', 'Creator', 1),
                ('CHECK_RUN', "Brand check executed for 'Display Banner Visual Asset' v1: 1 Warning (Design off-palette #FF007F). Status: Waiting for Review", 'arjun@lumora.demo', 'Creator', 1),
                ('LOGIN_SUCCESS', 'User manager@lumora.demo logged in successfully', 'manager@lumora.demo', 'Manager', 0),
                ('GUIDELINE_EDIT', "Updated guideline #1 [WORDS] 'Lumora Pro' context note", 'manager@lumora.demo', 'Manager', 0),
                ('LOGIN_SUCCESS', 'User reviewer@lumora.demo logged in successfully', 'reviewer@lumora.demo', 'Reviewer', 0),
                ('SELF_REVIEW_BLOCKED', "Blocked self-review attempt by reviewer@lumora.demo on 'Reviewer Personal Post'", 'reviewer@lumora.demo', 'Reviewer', 0),
                ('APPROVAL_BLOCKED_SERIOUS_ISSUES', "Blocked approval attempt on 'Festival Clearance Flyer' v1 due to open Serious issues.", 'reviewer@lumora.demo', 'Reviewer', 0)
            ]

            for act, det, u_email, u_role, d_ago in audit_events:
                u_id = users[u_email].id if u_email in users else None
                log = AuditLog(
                    action=act,
                    details=det,
                    user_id=u_id,
                    user_email=u_email,
                    user_role=u_role,
                    ip_address='127.0.0.1',
                    created_at=now - timedelta(days=d_ago, minutes=15 * len(det))
                )
                db.session.add(log)
            db.session.commit()

        print("==> Seed complete!")
        print("    Demo accounts:")
        print("    - Manager:  manager@lumora.demo  / Manager@123")
        print("    - Reviewer: reviewer@lumora.demo / Reviewer@123")
        print("    - Creator:  priya@lumora.demo    / Creator@123")
        print("    - Creator:  arjun@lumora.demo    / Creator@123")

if __name__ == '__main__':
    args = parse_args()
    seed_database(reset=args.reset)

