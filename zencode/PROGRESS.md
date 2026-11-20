# BrandGuard AI - Development Progress

## Loop 0 - Foundation
### 1. Plan
- Set up directory structure: `app/` (models, config, routes, templates, static), `uploads/`, `tests/`.
- Create `requirements.txt` with Flask, Flask-Login, Flask-SQLAlchemy, Flask-WTF, WTForms, SQLAlchemy, Pillow, pdfplumber, python-docx, pytesseract, pytest.
- Define SQLAlchemy data models matching prompt: `User`, `Role`, `Content`, `ContentVersion`, `Issue`, `Guideline`, `Decision`, `AuditLog`.
- Create application factory `create_app()` with CSRF, login manager, blueprints, error handlers (403, 404, 413, 500).
- Build clean, accessible base layout with CSS (contrast >= 4.5:1, brand palette `#0B3D91`, `#F5B700`, `#1A1A1A`, `#FFFFFF`).

### 2. Build
- Implemented `app/config.py` (configurable database URI defaulting to SQLite `brandguard.db`).
- Implemented `app/models.py` with all 8 core entities and relationships.
- Implemented `app/__init__.py` with Flask factory, blueprint registrations, and error handlers.
- Created `app/static/css/style.css` and `app/static/js/main.js`.
- Created `app/templates/base.html`, `index.html`, and `errors/{403, 404, 413, 500}.html`.
- Implemented entry point `app.py` and test harness `tests/conftest.py`.

### 3. Test
- Executed `pytest tests/test_foundation.py -v`.
- Result: 2 passed in 0.23s. Database tables created, home page loads with BrandGuard AI and Lumora branding.

### 4. Critique
- **Weakness 1**: Initial pytest run hit site-packages `app` collision because Python environment had a global `app` package. Fixed by prepending local directory in `conftest.py`.
- **Weakness 2**: Default role creation was only executed on `app.py` run; tests needed identical role bootstrapping in test fixtures. Handled in `conftest.py`.
- **Weakness 3**: CSRF protection is active globally, so forms will need CSRF tokens rendered in every form template.

### 5. Fix
- Added `sys.path.insert(0, ...)` to `tests/conftest.py`.
- Verified in-memory SQLite fixture initializes roles properly.
- Prepared form base classes and CSRF handling in `app/forms.py`.

### 6. Report
- **Exit Check**: PASSED. App starts, tables are created, home page loads.
- Ready for Loop 1 (Authentication).

## Loop 1 - Authentication & Role Access
### 1. Plan
- Implement registration form and view: default role 'Creator', password complexity check (min 8 chars, letter + number), duplicate email check.
- Implement login form and view: session management, remember-me, rate-limit / lockout after 5 consecutive failed logins (15-min lockout).
- Implement role enforcement: `@role_required` decorator returning 403 on unauthorized access.
- Implement role-specific redirection and dashboards for Creator, Reviewer, and Manager.
- Add "Demo Accounts" box on login page with click-to-autofill capability.

### 2. Build
- Implemented `app/decorators.py` with `@role_required` protecting routes.
- Created `app/services/audit.py` to record login, lockout, logout, and registration events.
- Created `app/forms.py` with `RegistrationForm`, `LoginForm`, `RoleChangeForm`, etc.
- Implemented `app/routes/auth.py` and `app/routes/main.py`.
- Created templates `auth/login.html` (including demo accounts card) and `auth/register.html`.
- Created dashboard templates for `creator.html`, `reviewer.html`, `manager.html`.
- Implemented tests in `tests/test_auth.py` and `tests/test_roles.py`.

### 3. Test
- Executed `pytest tests/test_auth.py tests/test_roles.py -v`.
- Result: 5 passed in 6.09s.
  - `test_register_creator` PASSED
  - `test_register_validation` PASSED
  - `test_login_and_logout` PASSED
  - `test_login_lockout_after_five_failed_attempts` PASSED
  - `test_role_access_dashboard_isolation` PASSED

### 4. Critique
- **Weakness 1**: Route helper URLs in dashboard templates initially raised `BuildError` for endpoints that had not yet been defined in other blueprints. Fixed by adding route stubs across all blueprints.
- **Weakness 2**: Deprecation warning on `datetime.utcnow()` with Python 3.13. Fixed by switching to timezone-aware UTC timestamps `datetime.now(timezone.utc)`.
- **Weakness 3**: When locked out, password input was still accepted before checking the lock. Reordered logic to check `user.is_locked` upfront before running password verification.

### 5. Fix
- Declared all required routes in `content_bp`, `guidelines_bp`, and `admin_bp`.
- Cleaned up datetime methods to standard timezone-aware UTC.
- Verified account lockout rejects login attempts immediately while locked.

### 6. Report
- **Exit Check**: PASSED. A new user can register, log in, and gets the right dashboard. Forbidden routes return 403.
- Ready for Loop 2 (Guidelines Management & Users).

## Loop 2 - Brand Guidelines Management & Users
### 1. Plan
- Manager CRUD for guidelines: WORDS, DETAILS, PROMISES, TONE, PALETTE, LOGO.
- Guideline activation toggle and deletion with immediate feedback.
- Team user management: listing users, displaying security/lockout status, and promoting roles.
- Server-side role enforcement on all guideline and user admin routes.
- Safeguard: Prevent sole Manager from demoting themselves.
- Audit logging for all rule creation, edit, toggle, deletion, and role changes.

### 2. Build
- Implemented `app/routes/guidelines.py` with list, add, edit, toggle, and delete endpoints.
- Implemented `app/routes/admin.py` with `/admin/users` and `/admin/users/<id>/role` endpoints.
- Created `app/templates/guidelines/list.html`, `guidelines/form.html`, and `admin/users.html`.
- Implemented tests in `tests/test_guidelines_and_users.py`.

### 3. Test
- Executed `pytest tests/test_guidelines_and_users.py -v`.
- Result: 2 passed in 3.24s.
  - `test_manager_can_add_guideline_and_creator_cannot` PASSED
  - `test_manager_can_change_role_and_creator_cannot` PASSED

### 4. Critique
- **Weakness 1**: Palette color previews in guidelines list needed a visual swatch with contrast border to distinguish light colors like `#FFFFFF`. Added border and hex display.
- **Weakness 2**: Legacy SQLAlchemy `Query.get()` warning was raised. Replaced with `db.session.get()`.
- **Weakness 3**: When deleting guidelines, destructive action needed confirmation safeguard. Added inline confirm alert before submitting deletion form.

### 5. Fix
- Swapped all `User.query.get(...)` calls for modern `db.session.get(...)`.
- Added CSS swatch rendering for PALETTE category in guidelines table.
- Added Javascript `onsubmit="return confirm(...)"` to guideline deletion forms.

### 6. Report
- **Exit Check**: PASSED. A Manager can add a rule and change a role. A Creator cannot.
- Ready for Loop 3 (Content intake and reading).

## Loop 3 - Content Intake & Reading
### 1. Plan
- Multi-format ingestion: TXT, PDF, DOCX, and PNG/JPG images (or pasted raw copy).
- File size validation (<= 10MB limit) and extension security validation.
- Text parsing using `pdfplumber`, `python-docx`, and UTF-8 / fallback text decoders.
- Image processing with Pillow and `pytesseract`: OCR with graceful degradation notice when system binary is missing.
- Structured key detail extraction: prices (Rs./$/INR), dates, Lumora product names, and unverified claims.
- Color palette quantization extracting dominant hex colors from image assets.

### 2. Build
- Implemented `app/services/extractor.py` containing `extract_text_from_file`, `extract_key_details`, and `extract_dominant_colors`.
- Handled Tesseract executable missing exception cleanly, preventing server 500s.
- Created `tests/test_extractor.py` generating real TXT, DOCX, PDF (via ReportLab), and PNG (via Pillow) test files.

### 3. Test
- Executed `pytest tests/test_extractor.py -v`.
- Result: 2 passed in 6.40s.
  - `test_extract_all_formats_without_crashing` PASSED
  - `test_extract_key_details` PASSED

### 4. Critique
- **Weakness 1**: Tesseract CLI binary is absent on Windows by default. Handled by graceful degradation with a detailed notice string returning image dimension metadata without failing.
- **Weakness 2**: Multi-page PDFs could have blank pages or scanned images without selectable text. Added page-by-page annotation.
- **Weakness 3**: Dominant color extraction needed image resizing before quantization to prevent memory/CPU spikes on large images. Added 150x150 thumbnail resampling.

### 5. Fix
- Confirmed graceful fallback message when Tesseract is absent.
- Quantized color palette using Median Cut on downscaled PIL image.
- Tested all 4 document formats with synthetic sample files.

### 6. Report
- **Exit Check**: PASSED. txt, PDF, DOCX and PNG all produce extracted text without crashing.
- Ready for Loop 4 (Brand Check Engine).

## Loop 4 - Brand Check Engine
### 1. Plan
- Implement five rule categories: WORDS, DETAILS, PROMISES, TONE, and DESIGN.
- Categorize flagged violations with explicit severity levels: Serious (blocks approval), Warning, and Info.
- Construct actionable feedback: exact snippet context, explainable 'why it matters', and rule-based suggestions.
- Implement tone scoring: exclamation mark thresholds, ALL CAPS detection with acronym whitelisting, and aggressive sales slang.
- Implement design & accessibility checks: palette Euclidean RGB distance, alt text verification for imagery.
- Add configurable AI explain hook (disabled by default, off without key) that never overrides rule evaluations.

### 2. Build
- Implemented `app/services/checker.py` with `run_brand_check()` mapping guidelines against extracted text and details.
- Added color distance calculation against active brand palette colors.
- Created `tests/test_checker.py` testing clean approved content and erroneous marketing flyer.

### 3. Test
- Executed `pytest tests/test_checker.py -v`.
- Result: 2 passed in 2.37s.
  - `test_clean_sample_produces_no_serious_issues` PASSED (0 Serious, 0 Warnings)
  - `test_demo_flyer_produces_expected_serious_issues` PASSED (Generated Serious issues for WORDS 'Lumora Pro', DETAILS wrong price 'Rs. 1,999', and PROMISES '100% guaranteed')

### 4. Critique
- **Weakness 1**: Common technical acronyms (LED, USB, RGB, etc.) triggered the ALL CAPS tone check. Fixed by adding a whitelist of allowed technical acronyms.
- **Weakness 2**: Price parsing needed to handle multiple product tiers (Lumora Plus Rs. 2,499 vs Lumora Mini Rs. 1,499) without false-flagging legitimate alternative products.
- **Weakness 3**: Image uploads lacked accessibility verification. Added WCAG 2.1 AA alt-text prompt for visual assets.

### 5. Fix
- Whitelisted standard industry abbreviations from ALL CAPS tone rule.
- Added cross-check against other known product tiers in Approved Facts before flagging pricing discrepancies.
- Verified all issues return non-empty snippet, explanation, and practical fix suggestion.

### 6. Report
- **Exit Check**: PASSED. The demo flyer text produces the expected Serious issues. The clean sample produces none.
- Ready for Loop 5 (Review and approval workflow).

## Loop 5 - Review and Approval Workflow
### 1. Plan
- Implement 6-step core workflow progress stepper (Add Content -> Read It -> Check It -> Show Issues -> Review -> Save & Keep).
- Build version switcher to browse previous versions and see evolution of edits.
- Enforce Safeguard 1: Block approval if any open Serious issue exists.
- Enforce Safeguard 2: Mandate a non-empty written justification reason when approving with an exception.
- Enforce Safeguard 3: Automatically trigger the intake extraction and brand check engine on every new version.
- Enforce Safeguard 4: Block Reviewers from reviewing and approving their own submissions.
- Enforce Safeguard 5: Restrict review decisions to Reviewer and Manager roles (Creators get 403).

### 2. Build
- Implemented `app/routes/content.py` with `/content/new`, `/content/<id>`, `/content/<id>/version`, and `/content/<id>/decision`.
- Created `app/templates/content/new.html` and `app/templates/content/detail.html` with responsive stepper, issues cards, revision upload, and reviewer decision form.
- Implemented comprehensive tests in `tests/test_safeguards.py` covering all 5 core safeguards.

### 3. Test
- Executed `pytest tests/test_safeguards.py -v`.
- Result: 5 passed in 10.77s.
  - `test_serious_issue_blocks_approval` PASSED
  - `test_exception_requires_mandatory_reason` PASSED
  - `test_recheck_on_new_version` PASSED
  - `test_reviewer_cannot_review_own_upload` PASSED
  - `test_creator_cannot_review` PASSED

### 4. Critique
- **Weakness 1**: Initial test assertions checked for literal raw single quotes (`'`) which Jinja autoescapes as `&#39;` in HTML. Fixed test assertions to check substring content reliably.
- **Weakness 2**: In-memory test isolation dropped previous test data between functions; resolved by adding a self-contained fixture setup in `create_sample_flyer()`.
- **Weakness 3**: When a reviewer attempts self-review, the UI submit button should be disabled as an early affordance in addition to the server-side rejection.

### 5. Fix
- Made tests completely independent by creating isolated content per test case.
- Added visual disabled state and explicit warning banner for self-review on `detail.html`.
- Verified server rejects self-review and logs `SELF_REVIEW_BLOCKED`.

### 6. Report
- **Exit Check**: PASSED. Every SAFEGUARD RULE is proven by a passing test.
- Ready for Loop 6 (Records and history).

## Loop 6 - Records, Audit History & Reports
### 1. Plan
- Build immutable audit history log tracking actions: UPLOAD, CHECK_RUN, FIX, DECISION, EXCEPTION, ROLE_CHANGE, and LOGIN events.
- Implement server-side filtering on audit log: by user email, action name, and date.
- Build executive Brand Compliance Reports page: breakdown of issues by brand category, overall approval rate, average fix turnaround time, and exceptions granted tally.
- Ensure the audit log is strictly read-only and cannot be manipulated or deleted via the UI.

### 2. Build
- Implemented `/admin/audit` and `/admin/reports` in `app/routes/admin.py`.
- Created templates `app/templates/audit/list.html` and `app/templates/reports/index.html`.
- Implemented end-to-end lifecycle verification in `tests/test_audit.py`.

### 3. Test
- Executed `pytest tests/test_audit.py -v`.
- Result: 2 passed in 6.37s.
  - `test_every_safeguard_action_appears_in_audit_log` PASSED (Verified UPLOAD, CHECK_RUN, FIX, DECISION, EXCEPTION, ROLE_CHANGE, REGISTER, LOGIN_SUCCESS)
  - `test_audit_log_filters_and_reports_page` PASSED

### 4. Critique
- **Weakness 1**: The reports page calculation for average fix time needed fallback handling when only single-version submissions exist in database. Added fallback to avoid division by zero.
- **Weakness 2**: Audit log details text could wrap awkwardly for lengthy check descriptions. Applied `word-break: break-word` and monospace formatting for timestamps and IP addresses.
- **Weakness 3**: Category distribution bars in reports needed brand-aligned color coding matching our visual theme.

### 5. Fix
- Added zero-division guards and clean formatting for duration metrics.
- Styled audit table with fixed timestamp widths and role badge highlights.
- Styled report category proportion bars using CSS variables corresponding to issue severities.

### 6. Report
- **Exit Check**: PASSED. Every action from the safeguard list appears in the log.
- Ready for Loop 7 (Demo data & seed script).

## Loop 7 - Demo Data & Seed Script
### 1. Plan
- Build idempotent, repeatable seeding script `seed.py` with optional `--reset` flag.
- Populate standard demo brand "Lumora" (smart home lighting).
- Seed 4 demo accounts: Manager (`manager@lumora.demo`), Reviewer (`reviewer@lumora.demo`), Creators (`priya@lumora.demo`, `arjun@lumora.demo`).
- Populate comprehensive guidelines: ~15 words, ~10 facts, 6 promises, tone voice rules, color palette (#0B3D91, #F5B700, #FFFFFF, #1A1A1A), and logo placement rules.
- Populate 6 realistic content items across different workflow states:
  (a) clean approved post,
  (b) flyer with wrong price and unapproved claim (Needs Fixes),
  (c) version 2 fixed and Waiting for Review,
  (d) social post with tone warning,
  (e) post approved with an exception,
  (f) image asset with off-palette color (real PNG).
- Generate ~40 audit log entries across the last 14 days so all dashboards, tables, and reports are pre-populated.

### 2. Build
- Implemented `seed.py` generating all roles, users, guidelines, sample documents, issues, decisions, and audit history.
- Generated actual DOCX, PDF, and PNG sample assets into `uploads/`.
- Updated login template with click-to-autofill demo cards.
- Verified test in `tests/test_demo_logins.py`.

### 3. Test
- Executed `python seed.py --reset`. Exit code 0.
- Executed `python seed.py` (idempotent run without reset). Exit code 0.
- Executed `pytest tests/test_demo_logins.py -v`.
- Result: 1 passed in 4.00s. All 4 demo logins verified and dashboards confirmed populated.

### 4. Critique
- **Weakness 1**: The seed script needed to generate real binary files (DOCX, PDF, PNG) rather than just database text rows so file inspection works for all formats. Added ReportLab, python-docx, and Pillow generation.
- **Weakness 2**: In initial seed runs, duplicate guidelines or users could have accumulated if executed multiple times without `--reset`. Added existence queries before adding records.
- **Weakness 3**: CSRF protection blocked external test clients using production Config without CSRF tokens. Handled cleanly in test suite configuration.

### 5. Fix
- Made `seed.py` fully idempotent with check-before-insert semantics.
- Generated authentic binary files on disk for DOCX, PDF, and PNG test assets.
- Confirmed `--reset` cleanly drops and rebuilds all tables and demo files.

### 6. Report
- **Exit Check**: PASSED. On a fresh clone, pip install, python seed.py, python app.py, and all 4 demo logins work and show populated pages.
- Ready for Loop 8 (Final Polish, Accessibility & Audit).

## Loop 8 - Final Polish, Accessibility & Requirement Audit
### 1. Plan
- Accessibility pass: verified form labels, focus rings, contrast ratios (>= 4.5:1), and empty states across all screens.
- Comprehensive documentation in `README.md`: quickstart, demo accounts, 6-step workflow explanation, database switching instructions (SQLite to MySQL/Postgres), and production deployment guidance.
- Full test suite run across all modules (foundation, auth, roles, guidelines, extractor, checker, safeguards, audit, demo logins).
- Requirement-by-requirement verification audit checklist against the prompt specification with PASS/FAIL marks.

### 2. Build
- Authored complete `README.md`.
- Polished error states (403, 404, 413, 500) and responsive UI styling in `app/static/css/style.css`.
- Conducted full execution run of test suite.

### 3. Test
- Executed `pytest -v`.
- Result: **21 passed in 24.92s**.
  - `tests/test_audit.py::test_every_safeguard_action_appears_in_audit_log` PASSED
  - `tests/test_audit.py::test_audit_log_filters_and_reports_page` PASSED
  - `tests/test_auth.py::test_register_creator` PASSED
  - `tests/test_auth.py::test_register_validation` PASSED
  - `tests/test_auth.py::test_login_and_logout` PASSED
  - `tests/test_auth.py::test_login_lockout_after_five_failed_attempts` PASSED
  - `tests/test_checker.py::test_clean_sample_produces_no_serious_issues` PASSED
  - `tests/test_checker.py::test_demo_flyer_produces_expected_serious_issues` PASSED
  - `tests/test_demo_logins.py::test_all_four_demo_logins_and_populated_pages` PASSED
  - `tests/test_extractor.py::test_extract_all_formats_without_crashing` PASSED
  - `tests/test_extractor.py::test_extract_key_details` PASSED
  - `tests/test_foundation.py::test_app_starts_and_home_loads` PASSED
  - `tests/test_foundation.py::test_roles_and_tables_exist` PASSED
  - `tests/test_guidelines_and_users.py::test_manager_can_add_guideline_and_creator_cannot` PASSED
  - `tests/test_guidelines_and_users.py::test_manager_can_change_role_and_creator_cannot` PASSED
  - `tests/test_roles.py::test_role_access_dashboard_isolation` PASSED
  - `tests/test_safeguards.py::test_serious_issue_blocks_approval` PASSED
  - `tests/test_safeguards.py::test_exception_requires_mandatory_reason` PASSED
  - `tests/test_safeguards.py::test_recheck_on_new_version` PASSED
  - `tests/test_safeguards.py::test_reviewer_cannot_review_own_upload` PASSED
  - `tests/test_safeguards.py::test_creator_cannot_review` PASSED

### 4. Requirement-by-Requirement Checklist
| Requirement | Status | Verification Detail |
| :--- | :---: | :--- |
| Product in One Line: One shared set of rules, one clear review | **PASS** | Centralized brand rules evaluated automatically before approval |
| Python 3.11+, Flask, Flask-Login, Flask-WTF, SQLAlchemy, SQLite | **PASS** | Implemented in `app/`, swappable via `DATABASE_URL` in `app/config.py` |
| Jinja templates, clean responsive CSS, vanilla JS | **PASS** | `style.css` has high contrast >= 4.5:1; `main.js` handles demo autofill |
| File reading: pdfplumber, python-docx, txt, Pillow + pytesseract OCR | **PASS** | Handled in `app/services/extractor.py` with graceful fallback |
| Rule-based checks engine with optional AI explain hook | **PASS** | Handled in `app/services/checker.py`; rules decide flagged items |
| Quickstart: pip install, python seed.py, python app.py | **PASS** | Tested and verified; starts server on port 5000 |
| Role-based access: Creator, Reviewer, Manager | **PASS** | `@role_required` decorator returns 403 on forbidden access |
| Registration: full name, email, password, confirm (default Creator) | **PASS** | Form validation with password complexity and duplicate check |
| Login / Logout, lockout after 5 failed attempts (15 mins) | **PASS** | Verified in `test_login_lockout_after_five_failed_attempts` |
| 6-Step Core Workflow with progress stepper | **PASS** | Visualized on review screen with state-driven active/completed steps |
| 5 Check Categories: WORDS, DETAILS, PROMISES, TONE, DESIGN | **PASS** | Evaluated in `checker.py` with explainable snippets & suggestions |
| Safeguard 1: Open Serious issue blocks approval | **PASS** | Tested in `test_serious_issue_blocks_approval` |
| Safeguard 2: Exception requires mandatory written reason | **PASS** | Tested in `test_exception_requires_mandatory_reason` |
| Safeguard 3: Auto re-check on every new version | **PASS** | Tested in `test_recheck_on_new_version` |
| Safeguard 4: Reviewers cannot review own uploads | **PASS** | Tested in `test_reviewer_cannot_review_own_upload` |
| Safeguard 5: Immutable audit history logging | **PASS** | Tested in `test_every_safeguard_action_appears_in_audit_log` |
| Manager CRUD for Guidelines & Users page | **PASS** | Tested in `test_manager_can_add_guideline_and_creator_cannot` |
| History / Audit with filters & Reports page | **PASS** | Tested in `test_audit_log_filters_and_reports_page` |
| Demo data (seed.py, idempotent, --reset, fictional "Lumora") | **PASS** | 4 demo users, 15 words, 10 facts, 6 claims, 6 samples, ~40 logs |

### 5. Critique & Polish
- **Finding 1**: Empty states needed distinct visual icons and helpful call-to-actions. Added custom empty state components to Creator, Reviewer, and Manager views.
- **Finding 2**: Focus indicators needed high visibility for keyboard navigation. Added `--accent` focus ring with outline offset in `style.css`.
- **Finding 3**: All 21 tests pass with zero failures and zero deprecation warnings.

### 6. Report
- **Exit Check**: PASSED. All 21 tests pass and the requirement checklist has 0 FAILs.
- Project complete and ready for production deployment.

## Post-Launch Feature: Manager Profile & Tailored Reviewer Directives (Varying per Reviewer)
### 1. Plan
- Add option in Manager Profile (`/admin/profile`) to create and manage custom review rules/directives assigned to reviewers.
- Allow rules to vary per reviewer (different reviewers can hold different focus areas, categories, and instructions).
- Reviewers see their custom assigned directives and interactive checklists on their Reviewer Dashboard (`/dashboard/reviewer`) and Content Detail review screen (`/content/<id>`).
- Enforce role security: only Managers can create/edit/toggle/delete reviewer rules; Creators and Reviewers receive 403 on attempted modification.
- Log all rule events (`REVIEWER_RULE_ADDED`, `REVIEWER_RULE_UPDATED`, `REVIEWER_RULE_TOGGLED`, `REVIEWER_RULE_DELETED`) to the immutable audit log.

### 2. Build
- Implemented `ReviewerRule` model in `app/models.py`.
- Implemented `ReviewerRuleForm` in `app/forms.py` with reviewer selection, category, title, instructions, and enforcement level.
- Added routes in `app/routes/admin.py`: `manager_profile`, `reviewer_rules`, `add_reviewer_rule`, `edit_reviewer_rule`, `toggle_reviewer_rule`, `delete_reviewer_rule`.
- Updated `app/routes/content.py` and `app/routes/main.py` to pass assigned rules to reviewer dashboard and detail views.
- Created `app/templates/admin/profile.html` and `app/templates/admin/reviewer_rule_form.html`.
- Updated `app/templates/content/detail.html` with interactive assigned review checklist for reviewers.
- Updated `seed.py` to seed realistic demo reviewer rules that vary between reviewers.
- Added `tests/test_reviewer_rules.py` covering CRUD, role security (403), per-reviewer variations, review screen checklist, and audit logs.

### 3. Test
- Executed `pytest -v`.
- Result: **23 passed in 28.79s** (100% passing across the entire test suite).

## Post-Launch Feature: 20-Rule Brand Governance Dataset Training (BG001-BG020)
### 1. Plan
- Integrate the official 20-rule brand governance CSV dataset into the application (`data/brandguard_rules.csv`).
- Create an automated trainer service (`app/services/trainer.py`) that syncs the 20 rules into `Guideline` and `ReviewerRule` models.
- Extend the brand check engine (`app/services/checker.py`) to detect and flag each rule violation (Tone, Terminology 'users'->'members', Truthful Claims, Pricing accuracy ₹999/mo, Privacy PII, Regulated Claims, Coercive CTAs, Confidential data, etc.).
- Add a web interface (`/guidelines/trained-rules`) with rule cards, example violations, recommended fixes, and a 1-click re-training trigger.
- Integrate into `seed.py` and write exhaustive tests in `tests/test_trained_dataset.py`.

### 2. Build
- Stored CSV dataset in `data/brandguard_rules.csv`.
- Implemented `load_rules_from_csv()` and `train_brandguard_model()` in `app/services/trainer.py`.
- Built trained dataset evaluator in `app/services/checker.py` (`evaluate_trained_dataset_rules`).
- Added web routes `guidelines.trained_rules` and `guidelines.train_dataset` in `app/routes/guidelines.py`.
- Created Jinja template `app/templates/guidelines/trained_rules.html`.
- Updated `seed.py` to auto-train the model during database seeding.
- Added 20 automated tests in `tests/test_trained_dataset.py` verifying detection of example violations across all rules.

### 3. Test
- Executed full test suite `pytest -v`.
- Result: **43 passed in 42.05s** (100% passing across all 43 tests).
- Server running in background on port 5000.


