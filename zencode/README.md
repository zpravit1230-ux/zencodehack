# BrandGuard AI

> **One shared set of brand rules, one clear review before publishing.**  
> *People stay in charge: creators make changes, a reviewer makes the final decision.*

BrandGuard AI is a collaborative brand-governance web platform that helps distributed teams catch brand mistakes, factual errors, risky claims, and tone inconsistencies in content *before* it goes public.

---

## Quickstart

### 1. Requirements
- Python 3.11+
- Virtual environment (recommended)

### 2. Installation & Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Seed database with demo data (idempotent, safe to rerun anytime)
python seed.py

# To wipe and recreate from scratch:
python seed.py --reset

# 3. Start the application
python app.py
```
Open your browser at **`http://localhost:5000`**.

---

## Demo Accounts

All demo accounts are pre-configured in the database and visible in the **"🔑 Demo Accounts"** card on the login page for one-click autofill:

| Role | Name | Email | Password | What They Can Do |
| :--- | :--- | :--- | :--- | :--- |
| **Manager** | Maya Raman | `manager@lumora.demo` | `Manager@123` | Full access: manage guidelines, change team user roles, audit logs, and reports |
| **Reviewer** | Rachel Thorne | `reviewer@lumora.demo` | `Reviewer@123` | Review queue: approve, reject, or approve with exception (cannot review own uploads) |
| **Creator** | Priya Sharma | `priya@lumora.demo` | `Creator@123` | Creator space: uploads content, inspects issues, uploads fixed versions |
| **Creator** | Arjun Mehta | `arjun@lumora.demo` | `Creator@123` | Creator space: marketing copywriter submitting campaigns |

---

## The 6-Step Core Workflow

The entire lifecycle is visualized through a progress stepper on the review screen:

```
[1. ADD CONTENT] ➔ [2. READ IT] ➔ [3. CHECK IT] ➔ [4. SHOW ISSUES] ➔ [5. REVIEW] ➔ [6. SAVE]
```

1. **ADD CONTENT**: The creator pastes raw copy or uploads a file (TXT, PDF, DOCX, or PNG/JPG image up to 10 MB). Validated on the server.
2. **READ IT**: The extraction engine reads plain text, documents (`pdfplumber` / `python-docx`), and images (Pillow + Tesseract OCR with graceful fallback if the binary is absent). Key details such as prices, launch dates, product lines, and unverified promises are catalogued.
3. **CHECK IT**: The rule engine compares extracted copy against active guidelines across 5 brand pillars: **WORDS**, **DETAILS**, **PROMISES**, **TONE**, and **DESIGN**.
4. **SHOW ISSUES**: Issues are classified by severity (**Serious**, **Warning**, **Info**). Every issue includes an exact text snippet, why it matters, and a practical fix suggestion. Serious issues automatically set status to `Needs Fixes`.
5. **REVIEW**: The creator uploads revised version (e.g. v2) which triggers an automatic re-check. An authorized Reviewer or Manager makes the final call: **Approve**, **Reject**, or **Approve with Exception** (mandatory written justification required). Reviewers cannot review their own submissions.
6. **SAVE & KEEP**: Approved versions, decision outcomes, timestamps, reviewer notes, and version evolution are preserved permanently in the audit history.

---

## Checks Engine (The 5 Brand Categories)

1. **WORDS**: Flags deprecated codenames (e.g. "Lumora Pro" ➔ "Lumora Plus"), forbidden competitor slang ("knockoff", "cheap"), and casing inconsistencies.
2. **DETAILS**: Compares quoted prices, warranty periods, and specifications against the Approved Facts database. Flagged as **Serious** if prices or warranties conflict.
3. **PROMISES**: Scans for high-liability claims like "guaranteed", "100%", "best in the world", or "cure". If unapproved, flagged as **Serious**.
4. **TONE**: Detects excessive exclamation marks, shouting ALL CAPS words (excluding whitelisted industry acronyms like LED, USB, CRI), and pushy sales urgency.
5. **DESIGN & ACCESSIBILITY**: Computes dominant image colors via Pillow color quantization and checks Euclidean RGB distance against the brand palette (`#0B3D91`, `#F5B700`, `#FFFFFF`, `#1A1A1A`). Verifies WCAG alt-text presence for image assets.

*Optional AI Explain Hook:* Disabled by default; off without an API key. Rephrases explanations only—rules alone decide what is flagged.

---

## Safeguards Enforced in Code & Tests

- **Safeguard 1 (No Approval with Serious Issue):** Any submission with an open Serious issue cannot be approved.
- **Safeguard 2 (Mandatory Exception Justification):** Approving with an exception requires an authorized Reviewer or Manager and a mandatory written reason (recorded immutably).
- **Safeguard 3 (Automatic Re-Check):** Uploading a new version automatically reruns the intake extraction and checks engine.
- **Safeguard 4 (Self-Review Block):** Reviewers cannot review or approve content they created.
- **Safeguard 5 (Role-Based Route Protection):** Strict `@role_required` decorators return `403 Forbidden` on unauthorized URL attempts.
- **Safeguard 6 (Lockout Protection):** Account locks for 15 minutes after 5 consecutive failed login attempts.
- **Safeguard 7 (Immutable Audit Log):** Every login, upload, check, revision, decision, exception, and role change is logged with timestamp, user, and IP. No UI edit/delete capability exists.

---

## Switching From SQLite to MySQL / PostgreSQL

BrandGuard AI is architected using SQLAlchemy and an environment-configurable database URI.

To migrate to MySQL or PostgreSQL, change exactly one line or set the `DATABASE_URL` environment variable:

### Option A: Via Environment Variable (Zero Code Change)
```bash
# For PostgreSQL:
export DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/brandguard"

# For MySQL:
export DATABASE_URL="mysql+pymysql://user:password@localhost:3306/brandguard"

python seed.py
python app.py
```

### Option B: In `app/config.py`
Change line 9:
```python
# From:
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(root_dir, 'brandguard.db')}")

# To:
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', "postgresql+psycopg2://branduser:secret@localhost:5432/brandguard_prod")
```

---

## Production Deployment Notes

1. **WSGI Server:** Run behind a production WSGI server like Gunicorn:
   ```bash
   gunicorn --workers 4 --bind 0.0.0.0:8000 "app:create_app()"
   ```
2. **Reverse Proxy:** Terminate SSL/TLS with Nginx or Cloudflare, and set `ProxyFix` middleware in Flask for accurate remote IP logging in the audit service.
3. **Storage:** In production clusters, configure `UPLOAD_FOLDER` to point to an S3/GCS bucket or persistent network volume.
4. **Environment Variables:** Set a strong `SECRET_KEY`, disable `DEBUG=False`, and optionally provide `AI_EXPLAIN_API_KEY` if enabling AI explanation rephrasing.

---

## Running the Test Suite

```bash
pytest -v
```
All 21 unit, integration, and security safeguard tests execute and pass out-of-the-box.

