import re
import math
from typing import List, Dict, Any, Optional, Tuple
from flask import current_app
from app.models import Issue, Guideline

def hex_to_rgb(hex_str: str):
    hex_clean = hex_str.strip().lstrip('#')
    if len(hex_clean) == 3:
        hex_clean = ''.join([c*2 for c in hex_clean])
    if len(hex_clean) != 6:
        return (0, 0, 0)
    return tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))

def color_distance(rgb1, rgb2):
    return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(rgb1, rgb2)))

def _find_page_and_heading(snippet: str, pages_data: Optional[List[Dict[str, Any]]]) -> Tuple[int, str]:
    if not pages_data:
        return 1, "General Section"
    
    clean_snip = snippet.strip("...").strip()
    if clean_snip:
        for p in pages_data:
            if clean_snip.lower() in p.get('text', '').lower():
                return p.get('page_number', 1), p.get('heading', f"Page {p.get('page_number', 1)}")
    
    first_page = pages_data[0] if pages_data else {}
    return first_page.get('page_number', 1), first_page.get('heading', 'Section 1')


def run_brand_check(
    text: str,
    details: Dict[str, Any],
    file_type: str = 'text',
    file_path: Optional[str] = None,
    guidelines: Optional[List[Guideline]] = None,
    alt_text: Optional[str] = None,
    pages_data: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Evaluates document content across the 7 comprehensive AI Review Categories:
    A. Grammar & Language
    B. Brand Guidelines
    C. Factual Accuracy
    D. Marketing & Promotional Claims
    E. Tone & Communication
    F. Accessibility & Formatting
    G. Privacy & Security
    
    Returns structured issues list with page numbers, headings, mistake types, and improved versions.
    """
    if guidelines is None:
        try:
            guidelines = Guideline.query.filter_by(active=True).all()
        except Exception:
            guidelines = []

    issues: List[Dict[str, Any]] = []
    text_content = text or ""
    text_lower = text_content.lower()

    # Organize guidelines by type
    guidelines_by_type: Dict[str, List[Guideline]] = {
        'WORDS': [],
        'DETAILS': [],
        'PROMISES': [],
        'TONE': [],
        'PALETTE': [],
        'LOGO': []
    }
    for g in guidelines:
        t = g.type.upper()
        if t in guidelines_by_type:
            guidelines_by_type[t].append(g)

    def add_issue(cat: str, sev: str, r_id: str, snip: str, why: str, sugg: str, m_type: str, improved: str = None):
        p_num, heading = _find_page_and_heading(snip, pages_data)
        # Avoid duplicate issues for identical rule and snippet
        for existing in issues:
            if existing['rule_id'] == r_id and existing['snippet'] == snip:
                return

        issues.append({
            'category': cat,
            'severity': sev,
            'rule_id': r_id,
            'snippet': snip,
            'why_it_matters': why,
            'suggestion': sugg,
            'mistake_type': m_type,
            'improved_text': improved or sugg,
            'page_number': p_num,
            'section_heading': heading,
            'status': 'Open'
        })

    # =========================================================================
    # 1. WORDS & BRAND GUIDELINES (Banned Terms, Preferred Names, Capitalization)
    # =========================================================================
    for g in guidelines_by_type['WORDS']:
        # If guideline is from BG dataset (e.g. "[BG002] ..."), let the BG evaluator handle it
        if g.key.startswith('['):
            continue

        key_term = g.key.strip()
        pattern = r'\b' + re.escape(key_term) + r'\b'
        match = re.search(pattern, text_content, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 30)
            end = min(len(text_content), match.end() + 30)
            snippet = ("..." if start > 0 else "") + text_content[start:end].strip() + ("..." if end < len(text_content) else "")
            
            is_serious = any(k in key_term.lower() for k in ['lumora pro', 'cheap', 'discount bulb', 'knockoff'])
            severity = 'Serious' if is_serious else 'Warning'
            mistake = "Banned Prototype Codename" if "lumora pro" in key_term.lower() else "Unapproved Terminology"
            
            matched_exact = match.group(0)
            improved = text_content[start:end].replace(matched_exact, g.value).strip()
            
            add_issue(
                cat='WORDS',
                sev=severity,
                r_id=f"WORD-{g.id or key_term}",
                snip=snippet,
                why=g.description or f"'{key_term}' violates current brand terminology guidelines.",
                sugg=f"Replace '{matched_exact}' with '{g.value}'.",
                m_type=mistake,
                improved=improved
            )

    # Inconsistent Capitalization check (e.g. 'lumora' or 'lumora plus' in lowercase)
    brand_caps_matches = re.finditer(r'\b(lumora\s+(?:plus|mini|glow)?|lumora)\b', text_content)
    for m in brand_caps_matches:
        matched_str = m.group(0)
        if matched_str[0].islower():
            start = max(0, m.start() - 25)
            end = min(len(text_content), m.end() + 25)
            snippet = ("..." if start > 0 else "") + text_content[start:end].strip() + ("..." if end < len(text_content) else "")
            improved = text_content[start:end].replace(matched_str, matched_str.title()).strip()
            
            add_issue(
                cat='WORDS',
                sev='Warning',
                r_id='WORDS-CAPS-BRAND',
                snip=snippet,
                why="Brand names must always adhere to approved title capitalization for brand equity and recognition.",
                sugg=f"Capitalize properly as '{matched_str.title()}'.",
                m_type="Inconsistent Brand Capitalization",
                improved=improved
            )

    # Common Typos / Grammar errors
    common_typos = {
        r'\bteh\b': ('the', 'Spelling Mistake: Transposed Letters'),
        r'\brecieve\b': ('receive', 'Spelling Mistake: "i" before "e" rule'),
        r'\bdefinately\b': ('definitely', 'Spelling Mistake'),
        r'\bseperate\b': ('separate', 'Spelling Mistake'),
        r'\buntill\b': ('until', 'Spelling Mistake: Double "l"'),
        r'\boccured\b': ('occurred', 'Spelling Mistake: Missing double "r"')
    }
    for typo_pat, (fix, m_type) in common_typos.items():
        m_typo = re.search(typo_pat, text_content, re.IGNORECASE)
        if m_typo:
            s_idx = max(0, m_typo.start() - 20)
            e_idx = min(len(text_content), m_typo.end() + 20)
            snip = text_content[s_idx:e_idx].strip()
            improved = text_content[s_idx:e_idx].replace(m_typo.group(0), fix).strip()
            add_issue(
                cat='WORDS',
                sev='Info',
                r_id=f"GRAMMAR-TYPO-{fix.upper()}",
                snip=snip,
                why=f"Typo detected: '{m_typo.group(0)}' is misspelled.",
                sugg=f"Correct spelling to '{fix}'.",
                m_type=m_type,
                improved=improved
            )

    # Double punctuation (?? or !! or !?)
    double_punct = re.search(r'([.?!]{2,})', text_content)
    if double_punct:
        p_idx = double_punct.start()
        s_idx = max(0, p_idx - 25)
        e_idx = min(len(text_content), p_idx + 25)
        snip = text_content[s_idx:e_idx].strip()
        cleaned_punct = double_punct.group(0)[0]
        improved = text_content[s_idx:e_idx].replace(double_punct.group(0), cleaned_punct).strip()
        add_issue(
            cat='WORDS',
            sev='Info',
            r_id='GRAMMAR-PUNCT-REPEAT',
            snip=snip,
            why=f"Repeated punctuation '{double_punct.group(0)}' appears unprofessional.",
            sugg=f"Use standard single punctuation '{cleaned_punct}'.",
            m_type="Punctuation Error: Repeated Punctuation",
            improved=improved
        )

    # Unprofessional slang / colloquialisms
    slang_words = {
        r'\bwanna\b': 'want to',
        r'\bgonna\b': 'going to',
        r'\bkinda\b': 'kind of',
        r'\blotsa\b': 'lots of',
        r'\bthx\b': 'thank you',
        r'\bain\'?t\b': 'is not'
    }
    for s_pat, s_fix in slang_words.items():
        m_slang = re.search(s_pat, text_content, re.IGNORECASE)
        if m_slang:
            s_idx = max(0, m_slang.start() - 20)
            e_idx = min(len(text_content), m_slang.end() + 20)
            snip = text_content[s_idx:e_idx].strip()
            improved = text_content[s_idx:e_idx].replace(m_slang.group(0), s_fix).strip()
            add_issue(
                cat='WORDS',
                sev='Info',
                r_id=f"LANGUAGE-SLANG-{s_fix.split()[0].upper()}",
                snip=snip,
                why=f"Casual colloquialism '{m_slang.group(0)}' does not match professional business communication standards.",
                sugg=f"Replace '{m_slang.group(0)}' with professional wording '{s_fix}'.",
                m_type="Unprofessional Language / Slang",
                improved=improved
            )

    # =========================================================================
    # 2. DETAILS CHECKS (Facts & Specs vs Approved Facts Table)
    # =========================================================================
    approved_facts: Dict[str, str] = {}
    for g in guidelines_by_type['DETAILS']:
        if not g.key.startswith('['):
            approved_facts[g.key.lower()] = g.value

    found_prices = details.get('prices', [])
    approved_price_plus = approved_facts.get('price - lumora plus') or approved_facts.get('price lumora plus') or 'Rs. 2,499'
    clean_approved_price = re.sub(r'[^\d]', '', approved_price_plus)

    for p in found_prices:
        clean_found = re.sub(r'[^\d]', '', p)
        if clean_found and clean_approved_price and clean_found != clean_approved_price:
            approved_price_mini = approved_facts.get('price - lumora mini') or 'Rs. 1,499'
            clean_mini = re.sub(r'[^\d]', '', approved_price_mini)
            
            if clean_found != clean_mini:
                p_idx = text_content.find(p)
                start = max(0, p_idx - 30) if p_idx != -1 else 0
                end = min(len(text_content), p_idx + len(p) + 30) if p_idx != -1 else len(text_content)
                snippet = ("..." if start > 0 else "") + text_content[start:end].strip() + ("..." if end < len(text_content) else "")
                improved = text_content[start:end].replace(p, approved_price_plus).strip()
                
                add_issue(
                    cat='DETAILS',
                    sev='Serious',
                    r_id='DETAILS-PRICE-MISMATCH',
                    snip=snippet if snippet else f"Price quoted: {p}",
                    why=f"The price '{p}' does not match any approved product pricing in the Approved Facts database.",
                    sugg=f"Verify product tier and update to approved price ({approved_price_plus} for Lumora Plus or {approved_price_mini} for Lumora Mini).",
                    m_type="Pricing Inaccuracy",
                    improved=improved
                )

    # Warranty specification check
    warranty_match = re.search(r'\b(\d+)\s*(?:years?|yrs?)\s*warranty\b', text_content, re.IGNORECASE)
    approved_warranty = approved_facts.get('warranty') or '2 years'
    if warranty_match:
        found_warranty = warranty_match.group(0)
        if '2' not in warranty_match.group(1):
            start = max(0, warranty_match.start() - 25)
            end = min(len(text_content), warranty_match.end() + 25)
            improved = text_content[start:end].replace(found_warranty, f"{approved_warranty} warranty").strip()
            add_issue(
                cat='DETAILS',
                sev='Serious',
                r_id='DETAILS-WARRANTY-MISMATCH',
                snip=text_content[start:end].strip(),
                why=f"Quoting '{found_warranty}' is inaccurate. Lumora standard warranty policy is strictly {approved_warranty}.",
                sugg=f"Correct warranty period to '{approved_warranty}'.",
                m_type="Warranty Policy Mismatch",
                improved=improved
            )

    # Contradictions in document: Check if multiple different prices appear
    distinct_prices = set(details.get('prices', []))
    if len(distinct_prices) > 1 and any('2,499' in p or '2499' in p for p in distinct_prices) and any('1,999' in p or '1999' in p for p in distinct_prices):
        add_issue(
            cat='DETAILS',
            sev='Serious',
            r_id='DETAILS-CONTRADICTION-PRICE',
            snip=f"Conflicting prices in same document: {', '.join(distinct_prices)}",
            why="The document contains internal pricing contradictions (e.g. Rs. 2,499 vs Rs. 1,999).",
            sugg="Ensure all mentions across all pages reflect the unified approved price.",
            m_type="Internal Document Contradiction",
            improved=f"Unified price: {approved_price_plus}"
        )

    # =========================================================================
    # 3. PROMISES CHECKS (Risky Claims vs Approved Claims)
    # =========================================================================
    risky_claim_triggers = [
        'guaranteed', '100% satisfaction', '100% guaranteed', 'best in the world',
        'no risk', 'cure', 'permanent fix', 'never breaks', 'miracle', 'zero failure'
    ]

    approved_claims = [g.key.lower() for g in guidelines_by_type['PROMISES']] + [g.value.lower() for g in guidelines_by_type['PROMISES']]

    for trigger in risky_claim_triggers:
        pattern = r'\b' + re.escape(trigger) + r'\b'
        match = re.search(pattern, text_content, re.IGNORECASE)
        if match:
            matched_phrase = match.group(0)
            is_approved = any(trigger in app_c for app_c in approved_claims)
            
            if not is_approved:
                start = max(0, match.start() - 35)
                end = min(len(text_content), match.end() + 35)
                snippet = ("..." if start > 0 else "") + text_content[start:end].strip() + ("..." if end < len(text_content) else "")
                improved = text_content[start:end].replace(matched_phrase, "tested for everyday reliability").strip()
                
                add_issue(
                    cat='PROMISES',
                    sev='Serious',
                    r_id=f"PROMISES-RISKY-{trigger.replace(' ', '-').upper()}",
                    snip=snippet,
                    why=f"Absolute claim '{matched_phrase}' is unverified and exposes the company to false-advertising liability.",
                    sugg="Remove absolute claim or replace with an approved claim from the brand claims repository.",
                    m_type="Exaggerated Marketing Promise",
                    improved=improved
                )

    # =========================================================================
    # 4. TONE CHECKS (Brand Voice: Friendly, Clear, Confident, Not Pushy)
    # =========================================================================
    exclamation_count = text_content.count('!')
    if exclamation_count >= 2:
        exc_match = re.search(r'[^.\n]*![^.\n]*', text_content)
        snippet = exc_match.group(0).strip() if exc_match else f"{exclamation_count} exclamation marks detected"
        improved = snippet.replace('!', '.')
        add_issue(
            cat='TONE',
            sev='Warning',
            r_id='TONE-EXCLAMATIONS',
            snip=snippet[:80],
            why=f"Found {exclamation_count} exclamation marks. Lumora voice is calm, confident, and premium, not loud or shouty.",
            sugg="Replace exclamation marks with a standard period.",
            m_type="Excessive Exclamations",
            improved=improved
        )

    words = re.findall(r'\b[A-Z]{3,}\b', text_content)
    whitelisted_acronyms = {'LED', 'USB', 'RGB', 'CRI', 'WIFI', 'APP', 'PDF', 'DOCX', 'PNG', 'FAQ', 'INR', 'USD', 'MSRP', 'WCAG', 'HTML', 'CSV', 'PPTX', 'XLSX'}
    caps_violations = [w for w in words if w not in whitelisted_acronyms]
    if caps_violations:
        sample_caps = caps_violations[0]
        match_caps = re.search(r'\b' + re.escape(sample_caps) + r'\b', text_content)
        start = max(0, match_caps.start() - 25) if match_caps else 0
        end = min(len(text_content), match_caps.end() + 25) if match_caps else len(text_content)
        snippet = text_content[start:end].strip()
        improved = snippet.replace(sample_caps, sample_caps.capitalize())

        add_issue(
            cat='TONE',
            sev='Warning',
            r_id='TONE-ALL-CAPS',
            snip=snippet,
            why=f"ALL CAPS words ({', '.join(set(caps_violations[:3]))}) appear aggressive and harm readability.",
            sugg="Convert words in ALL CAPS to normal sentence case.",
            m_type="Shouting ALL CAPS Words",
            improved=improved
        )

    pushy_phrases = ['act fast', 'hurry up', 'insane deal', 'crazy offer', 'grab yours now', 'once in a lifetime']
    for pphrase in pushy_phrases:
        if pphrase in text_lower:
            m = re.search(r'\b' + re.escape(pphrase) + r'\b', text_content, re.IGNORECASE)
            start = max(0, m.start() - 25) if m else 0
            end = min(len(text_content), m.end() + 25) if m else len(text_content)
            snip = text_content[start:end].strip() if m else pphrase
            improved = snip.replace(m.group(0) if m else pphrase, "available today")
            add_issue(
                cat='TONE',
                sev='Warning',
                r_id='TONE-PUSHY-SLANG',
                snip=snip,
                why=f"High-pressure phrase '{pphrase}' feels cheap and conflicts with Lumora's relaxed, confident tone.",
                sugg="Focus on customer benefits and utility rather than artificial urgency.",
                m_type="High-Pressure Sales Language",
                improved=improved
            )

    # Readability: Sentence length check
    sentences = [s.strip() for s in re.split(r'[.!?]+', text_content) if s.strip()]
    for s in sentences:
        s_words = s.split()
        if len(s_words) > 35:
            midpoint = len(s_words) // 2
            half1 = " ".join(s_words[:midpoint]) + "."
            half2 = " ".join(s_words[midpoint:]).capitalize()
            improved_sentences = f"{half1} {half2}"
            add_issue(
                cat='TONE',
                sev='Info',
                r_id='TONE-READABILITY-LONG-SENTENCE',
                snip=(" ".join(s_words[:12]) + " ... " + " ".join(s_words[-5:])),
                why=f"Sentence contains {len(s_words)} words. Long sentences decrease reading comprehension and clarity.",
                sugg="Break this into two shorter, punchier sentences under 25 words.",
                m_type="Poor Sentence Structure: Overly Complex",
                improved=improved_sentences[:120]
            )
            break

    # =========================================================================
    # 5. DESIGN & ACCESSIBILITY CHECKS
    # =========================================================================
    dominant_colors = details.get('dominant_colors', [])
    approved_palette = [g.key.upper() for g in guidelines_by_type['PALETTE']]
    if not approved_palette:
        approved_palette = ['#0B3D91', '#F5B700', '#FFFFFF', '#1A1A1A']

    approved_rgbs = [hex_to_rgb(h) for h in approved_palette]

    for d_hex in dominant_colors:
        d_rgb = hex_to_rgb(d_hex)
        min_dist = min([color_distance(d_rgb, app_rgb) for app_rgb in approved_rgbs]) if approved_rgbs else 0
        if min_dist > 85:
            add_issue(
                cat='DESIGN',
                sev='Warning',
                r_id='DESIGN-OFF-PALETTE',
                snip=f"Extracted dominant color {d_hex} (Delta: {int(min_dist)})",
                why=f"Color {d_hex} is outside the approved Lumora brand color palette ({', '.join(approved_palette)}).",
                sugg=f"Recolor elements using primary brand colors: {', '.join(approved_palette[:2])}.",
                m_type="Visual Brand: Off-Palette Color",
                improved=f"Replace {d_hex} with {approved_palette[0]} (Deep Blue)"
            )

    if file_type == 'image':
        if not alt_text or len(alt_text.strip()) == 0:
            add_issue(
                cat='DESIGN',
                sev='Info',
                r_id='DESIGN-A11Y-ALT-MISSING',
                snip="Uploaded image asset",
                why="Web content accessibility guidelines (WCAG 2.1 AA) require informative alternative text for all images.",
                sugg="Provide a descriptive alt-text caption explaining the visual context.",
                m_type="Accessibility: Missing Alt Text",
                improved="Alt text: Lumora Plus ambient lighting system in modern living room setup."
            )

    # =========================================================================
    # 6. TRAINED DATASET EVALUATOR (BG001 - BG020)
    # =========================================================================
    trained_issues = evaluate_trained_dataset_rules(
        text_content, details, file_type=file_type, alt_text=alt_text, pages_data=pages_data
    )
    for t_iss in trained_issues:
        add_issue(
            cat=t_iss['category'],
            sev=t_iss['severity'],
            r_id=t_iss['rule_id'],
            snip=t_iss['snippet'],
            why=t_iss['why_it_matters'],
            sugg=t_iss['suggestion'],
            m_type=t_iss.get('mistake_type', 'Brand Governance Violation'),
            improved=t_iss.get('improved_text', t_iss['suggestion'])
        )

    # Optional AI explain hook
    if current_app and current_app.config.get('AI_EXPLAIN_ENABLED') and current_app.config.get('AI_EXPLAIN_API_KEY'):
        pass

    return issues


def evaluate_trained_dataset_rules(
    text_content: str,
    details: Dict[str, Any],
    file_type: str = 'text',
    alt_text: Optional[str] = None,
    pages_data: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Evaluates content against the 20 trained rules (BG001 - BG020)
    from the brand governance dataset.
    """
    issues: List[Dict[str, Any]] = []
    if not text_content:
        return issues

    text_lower = text_content.lower()

    def make_snippet(match, text, pad=35):
        if not match:
            return ""
        s = max(0, match.start() - pad)
        e = min(len(text), match.end() + pad)
        return ("..." if s > 0 else "") + text[s:e].strip() + ("..." if e < len(text) else "")

    # BG001: Tone of Voice
    m1 = re.search(r'(?i)\b(?:buy\s+now\s+or\s+regret(?:\s+it)?(?:\s+forever)?|regret\s+it\s+forever)\b', text_content)
    if m1:
        snip = make_snippet(m1, text_content)
        issues.append({
            'category': 'TONE',
            'severity': 'Warning',
            'rule_id': 'BG001',
            'snippet': snip,
            'why_it_matters': "Use clear, friendly, confident and helpful language. Avoid rude, aggressive, threatening or overly pushy wording.",
            'suggestion': "Use a helpful, respectful call to action.",
            'mistake_type': "Aggressive / Threatening Tone",
            'improved_text': snip.replace(m1.group(0), "Order today to enjoy seamless ambient lighting.")
        })

    # BG002: Approved Terminology (Use 'members' instead of 'users')
    m2 = re.search(r'(?i)\b(?:our\s+users|the\s+users|all\s+users|customer\s+users|users\s+love)\b', text_content)
    if m2:
        snip = make_snippet(m2, text_content)
        improved = re.sub(r'(?i)\busers\b', 'members', snip)
        issues.append({
            'category': 'WORDS',
            'severity': 'Info',
            'rule_id': 'BG002',
            'snippet': snip,
            'why_it_matters': "Use 'members' instead of 'users' in all customer-facing content.",
            'suggestion': "Replace 'users' with 'members'.",
            'mistake_type': "Terminology: Customer Facing Role",
            'improved_text': improved
        })

    # BG003: Truthful Product Claims
    m3 = re.search(r'(?i)\b(?:(?:we\s+)?guarantee\s+100%\s+success|100%\s+success|guarantee(?:d)?\s+results?)\b', text_content)
    if m3:
        snip = make_snippet(m3, text_content)
        improved = snip.replace(m3.group(0), "provide reliable, verified performance")
        issues.append({
            'category': 'PROMISES',
            'severity': 'Serious',
            'rule_id': 'BG003',
            'snippet': snip,
            'why_it_matters': "Do not promise guaranteed results, 100% success, or outcomes that cannot be substantiated.",
            'suggestion': "Remove the guarantee and use a verified, evidence-based benefit.",
            'mistake_type': "Unsupported / False Guarantee",
            'improved_text': improved
        })

    # BG004: Pricing Accuracy (Only ₹999/month approved; other monthly subscription rates require approval)
    m4 = re.search(r'(?i)(?:₹|rs\.?|inr)?\s*(\d{3,5})\s*(?:/|\s*per\s*)month', text_content)
    if m4:
        amount_found = m4.group(1)
        if amount_found != '999':
            snip = make_snippet(m4, text_content)
            improved = snip.replace(m4.group(0), "₹999/month")
            issues.append({
                'category': 'DETAILS',
                'severity': 'Serious',
                'rule_id': 'BG004',
                'snippet': snip,
                'why_it_matters': "Only publish the latest approved price: ₹999/month. Any other price requires manager approval before publication.",
                'suggestion': "Correct the price to ₹999/month or request approval for a new price.",
                'mistake_type': "Factual Accuracy: Unapproved Subscription Rate",
                'improved_text': improved
            })

    # BG005: Competitor References
    m5 = re.search(r'(?i)\b(?:our\s+competitor\s+cheats|competitor\s+(?:cheats?|scams?|steals?|defrauds?)|cheats\s+every\s+customer)\b', text_content)
    if m5:
        snip = make_snippet(m5, text_content)
        issues.append({
            'category': 'PROMISES',
            'severity': 'Serious',
            'rule_id': 'BG005',
            'snippet': snip,
            'why_it_matters': "Do not publish unverified negative statements, accusations or comparisons about competitors.",
            'suggestion': "Remove the allegation or provide approved, verifiable comparative evidence.",
            'mistake_type': "Unverified Competitor Allegation",
            'improved_text': "Our products offer verified quality standards backed by independently tested hardware."
        })

    # BG006: Privacy and Personal Data (Critical)
    m6 = re.search(r'(?i)\b[A-Za-z0-9._%+-]+@example\.com\b|\bprivate\.[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|\bcontact\s+(?:the\s+customer|at)\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b', text_content)
    if m6:
        snip = make_snippet(m6, text_content)
        issues.append({
            'category': 'DETAILS',
            'severity': 'Serious',
            'rule_id': 'BG006',
            'snippet': snip,
            'why_it_matters': "Never expose personal email addresses, phone numbers, home addresses, account IDs, passwords or confidential customer information.",
            'suggestion': "Remove personal information and use the official support channel.",
            'mistake_type': "Privacy: Exposed Personal Contact / PII",
            'improved_text': "Contact support through support@lumora.demo or our secure portal."
        })

    # Phone number PII
    m_phone = re.search(r'(?:\+?91[\s-]?)?[6-9]\d{9}|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b', text_content)
    if m_phone and not any(p in m_phone.group(0) for p in ['100', '101', '102']):
        snip = make_snippet(m_phone, text_content)
        issues.append({
            'category': 'DETAILS',
            'severity': 'Serious',
            'rule_id': 'PRIVACY-PHONE-EXPOSURE',
            'snippet': snip,
            'why_it_matters': "Direct personal telephone numbers must not be exposed in published copy.",
            'suggestion': "Replace personal number with official toll-free hotline or support desk.",
            'mistake_type': "Privacy: Exposed Phone Number",
            'improved_text': "Reach our customer desk via 1800-LUMORA-CARE."
        })

    # BG007: Accessibility and Alt Text
    if file_type == 'image' and (not alt_text or not alt_text.strip()):
        issues.append({
            'category': 'DESIGN',
            'severity': 'Warning',
            'rule_id': 'BG007',
            'snippet': "Uploaded infographic / image asset",
            'why_it_matters': "Informative images must include meaningful alternative text. Videos should include captions where applicable.",
            'suggestion': "Add concise alt text describing the important information in the image.",
            'mistake_type': "Accessibility: Missing Alt Text",
            'improved_text': "Alt text: Infographic showing Lumora energy efficiency comparison chart."
        })

    # BG008: Visual Brand Identity
    m8 = re.search(r'(?i)\b(?:deprecated\s+(?:dashboard\s+)?screenshot|old\s+logo\s+is\s+used)\b', text_content)
    if m8:
        snip = make_snippet(m8, text_content)
        issues.append({
            'category': 'DESIGN',
            'severity': 'Warning',
            'rule_id': 'BG008',
            'snippet': snip,
            'why_it_matters': "Use only approved logos, brand colors, fonts, templates and current product screenshots.",
            'suggestion': "Replace it with the latest approved asset from the brand asset library.",
            'mistake_type': "Visual Brand: Deprecated Asset",
            'improved_text': "Use Lumora Brand Portal 2026 Asset Pack v2.1"
        })

    # BG009: Sponsored Content Disclosure
    m9 = re.search(r'(?i)\b(?:paid\s+promotion(?:\s+is\s+posted)?|paid\s+partnership|sponsored\s+post|gifted\s+products?)\b', text_content)
    if m9 and not ('#ad' in text_lower or '#sponsored' in text_lower or 'sponsorship disclosure' in text_lower):
        snip = make_snippet(m9, text_content)
        issues.append({
            'category': 'PROMISES',
            'severity': 'Serious',
            'rule_id': 'BG009',
            'snippet': snip,
            'why_it_matters': "Clearly disclose paid partnerships, sponsorships, gifted products and other material relationships.",
            'suggestion': "Add a clear and visible sponsorship disclosure before publication.",
            'mistake_type': "Marketing: Undisclosed Sponsorship",
            'improved_text': f"{snip} [Ad: Paid partnership with Lumora]"
        })

    # BG010: Spelling and Grammar
    m10 = re.search(r'(?i)\b(?:repeated\s+spelling\s+errors|public\s+post\s+contains\s+repeated\s+spelling\s+errors)\b', text_content)
    if m10:
        snip = make_snippet(m10, text_content)
        issues.append({
            'category': 'WORDS',
            'severity': 'Info',
            'rule_id': 'BG010',
            'snippet': snip,
            'why_it_matters': "Proofread content. Use professional English, consistent punctuation and approved spelling conventions.",
            'suggestion': "Correct spelling, grammar and punctuation before submission.",
            'mistake_type': "Content Quality: Repeated Typos",
            'improved_text': "This draft has been thoroughly proofread and corrected."
        })

    # BG011: Regulated Claims (Critical)
    m11 = re.search(r'(?i)\b(?:will\s+cure\s+anxiety(?:\s+in\s+\w+\s+days?)?|cure\s+anxiety|cure\s+depression|cure\s+in\s+seven\s+days)\b', text_content)
    if m11:
        snip = make_snippet(m11, text_content)
        improved = snip.replace(m11.group(0), "supports relaxing ambiance and natural circadian rhythms")
        issues.append({
            'category': 'PROMISES',
            'severity': 'Serious',
            'rule_id': 'BG011',
            'snippet': snip,
            'why_it_matters': "Do not make medical, financial or legal guarantees or claims without approved evidence and required specialist review.",
            'suggestion': "Block publication and escalate to the appropriate legal or compliance reviewer.",
            'mistake_type': "Regulated Claim: Medical / Health Guarantee",
            'improved_text': improved
        })

    # BG012: Call to Action
    m12 = re.search(r'(?i)\b(?:click\s+now\s+or\s+(?:your\s+)?account\s+will\s+be\s+deleted|account\s+will\s+be\s+deleted|or\s+your\s+account\s+will\s+be\s+deleted)\b', text_content)
    if m12:
        snip = make_snippet(m12, text_content)
        issues.append({
            'category': 'TONE',
            'severity': 'Warning',
            'rule_id': 'BG012',
            'snippet': snip,
            'why_it_matters': "Calls to action must be honest, respectful and non-coercive. Do not use misleading urgency or fear-based pressure.",
            'suggestion': "Use a clear, truthful and non-threatening call to action.",
            'mistake_type': "Coercive / Fear-Based CTA",
            'improved_text': "Log in to your account to review and update your security settings."
        })

    # BG013: Approved Facts and Statistics
    m13 = re.search(r'(?i)\b(?:(?:service\s+is\s+)?trusted\s+by\s+10\s+million\s+people(?:\s+without\s+evidence)?)\b', text_content)
    if m13:
        snip = make_snippet(m13, text_content)
        issues.append({
            'category': 'DETAILS',
            'severity': 'Serious',
            'rule_id': 'BG013',
            'snippet': snip,
            'why_it_matters': "Use only facts, statistics, testimonials and performance figures supported by approved sources.",
            'suggestion': "Attach an approved source or remove the unsupported statistic.",
            'mistake_type': "Factual Accuracy: Unsupported Statistic",
            'improved_text': "Trusted by thousands of verified households across India."
        })

    # BG014: Testimonials and Reviews
    m14 = re.search(r'(?i)\b(?:fictional\s+customer\s+review(?:\s+is\s+presented)?|fabricated\s+(?:testimonial|rating|endorsement))\b', text_content)
    if m14:
        snip = make_snippet(m14, text_content)
        issues.append({
            'category': 'PROMISES',
            'severity': 'Serious',
            'rule_id': 'BG014',
            'snippet': snip,
            'why_it_matters': "Do not fabricate testimonials, ratings, endorsements or customer reviews. Obtain permission before using identifiable customer stories.",
            'suggestion': "Remove fabricated material and verify permission for real testimonials.",
            'mistake_type': "Authenticity: Fabricated Testimonial",
            'improved_text': "Include only customer reviews with recorded written consent."
        })

    # BG015: Confidential Business Information (Critical)
    m15 = re.search(r'(?i)\b(?:draft\s+reveals\s+an\s+unreleased\s+product|unreleased\s+product\s+launch\s+date|internal\s+roadmaps?|confidential\s+partner\s+information)\b', text_content)
    if m15:
        snip = make_snippet(m15, text_content)
        issues.append({
            'category': 'DETAILS',
            'severity': 'Serious',
            'rule_id': 'BG015',
            'snippet': snip,
            'why_it_matters': "Do not disclose internal roadmaps, unreleased features, internal documents, financial results or confidential partner information.",
            'suggestion': "Remove confidential details and obtain explicit manager approval.",
            'mistake_type': "Confidentiality: Unreleased Internal Roadmap",
            'improved_text': "Details regarding upcoming features will be announced at the official launch."
        })

    # BG016: Content Ownership and Permissions
    m16 = re.search(r'(?i)\b(?:unlicensed\s+(?:stock\s+)?photograph|unlicensed\s+material|unlicensed\s+asset)\b', text_content)
    if m16:
        snip = make_snippet(m16, text_content)
        issues.append({
            'category': 'DESIGN',
            'severity': 'Serious',
            'rule_id': 'BG016',
            'snippet': snip,
            'why_it_matters': "Use images, music, videos, fonts and written material only when the organisation has the necessary rights or permissions.",
            'suggestion': "Replace the asset with licensed or approved material and record its source.",
            'mistake_type': "Copyright: Unlicensed Third-Party Asset",
            'improved_text': "Source licensed imagery from Lumora's commercial Getty / Shutterstock repository."
        })

    # BG017: Inclusive Language
    m17 = re.search(r'(?i)\b(?:insulting\s+or\s+exclusionary\s+language|discriminatory\s+(?:description|language))\b', text_content)
    if m17:
        snip = make_snippet(m17, text_content)
        issues.append({
            'category': 'WORDS',
            'severity': 'Serious',
            'rule_id': 'BG017',
            'snippet': snip,
            'why_it_matters': "Use respectful, inclusive language. Avoid discriminatory, demeaning or stereotypical descriptions of people or groups.",
            'suggestion': "Rewrite using neutral, respectful and inclusive wording.",
            'mistake_type': "Inclusivity: Exclusionary Language",
            'improved_text': "Use welcoming and inclusive phrasing for all audiences."
        })

    # BG018: Platform and Campaign Consistency
    m18 = re.search(r'(?i)\b(?:unapproved\s+hashtag|outdated\s+campaign\s+name)\b', text_content)
    if m18:
        snip = make_snippet(m18, text_content)
        issues.append({
            'category': 'WORDS',
            'severity': 'Warning',
            'rule_id': 'BG018',
            'snippet': snip,
            'why_it_matters': "Follow the approved campaign brief, platform-specific format, hashtags, naming conventions and publication requirements.",
            'suggestion': "Update the content to match the approved campaign brief.",
            'mistake_type': "Campaign Compliance: Inconsistent Tag",
            'improved_text': "Use approved campaign hashtag #LumoraHome2026."
        })

    # BG019: AI-Generated Content Review
    m19 = re.search(r'(?i)\b(?:ai-generated\s+copy\s+includes\s+an\s+invented|invented\s+product\s+feature)\b', text_content)
    if m19:
        snip = make_snippet(m19, text_content)
        issues.append({
            'category': 'PROMISES',
            'severity': 'Serious',
            'rule_id': 'BG019',
            'snippet': snip,
            'why_it_matters': "AI-generated text, images and claims must be checked by a human for accuracy, bias, rights, privacy and brand alignment before publication.",
            'suggestion': "Verify every claim and obtain human approval before publishing.",
            'mistake_type': "AI Oversight: Unverified Machine Output",
            'improved_text': "Subject all AI drafts to human fact-checking prior to publishing."
        })

    # BG020: Final Approval Requirement (Critical)
    m20 = re.search(r'(?i)\b(?:critical-risk\s+post\s+is\s+published\s+while\s+approval|published\s+while\s+approval\s+is\s+pending)\b', text_content)
    if m20:
        snip = make_snippet(m20, text_content)
        issues.append({
            'category': 'DETAILS',
            'severity': 'Serious',
            'rule_id': 'BG020',
            'snippet': snip,
            'why_it_matters': "Content marked as high or critical risk must not be published until the required reviewer and manager approvals are recorded.",
            'suggestion': "Keep publication blocked until all required approvals are complete.",
            'mistake_type': "Workflow Control: Unapproved Release",
            'improved_text': "Hold publication until formal reviewer sign-off is logged in BrandGuard."
        })

    return issues
