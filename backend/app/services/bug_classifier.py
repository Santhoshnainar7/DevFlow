"""
Bug classification service for DevFlow.

Categorizes incoming bug reports into standard domain categories and
determines severity based on failure scope, security implications, and keywords.
"""

import re
from typing import List, Tuple
from app.models.investigation import BugCategory, Severity


# Classification rules: maps category to regex patterns and indicator keywords
CATEGORY_PATTERNS = {
    BugCategory.AUTHENTICATION: [
        r"\blogin\b",
        r"\bpassword\b",
        r"\btoken\b",
        r"\bauth\b",
        r"\bauthenticated\b",
        r"\bunauthorized\b",
        r"\b401\b",
        r"\bjwt\b",
        r"\bbearer\b",
        r"\bcredential(s)?\b",
        r"\brole\b",
        r"\bpermission\b",
    ],
    BugCategory.VALIDATION_ERRORS: [
        r"\bvalidation\b",
        r"\b422\b",
        r"\bunprocessable\b",
        r"\bempty\b",
        r"\brequired field\b",
        r"\bfield_validator\b",
        r"\bmissing field\b",
        r"\binvalid format\b",
        r"\bpydantic\b",
    ],
    BugCategory.API_FAILURES: [
        r"\bendpoint\b",
        r"\bstatus code\b",
        r"\b500\b",
        r"\b502\b",
        r"\b503\b",
        r"\b404\b",
        r"\bnot found\b",
        r"\broute\b",
        r"\brouter\b",
        r"\brequest\b",
        r"\bresponse\b",
        r"\bhttp\b",
        r"\bapi\b",
        r"\bjson\b",
        r"\bpayload\b",
    ],
    BugCategory.DATABASE_ERRORS: [
        r"\bdatabase\b",
        r"\bsql\b",
        r"\bquery\b",
        r"\bpostgres\b",
        r"\bsqlite\b",
        r"\btable\b",
        r"\bforeign key\b",
        r"\bunique constraint\b",
        r"\bdeadlock\b",
        r"\bmigration\b",
    ],
    BugCategory.FRONTEND_ISSUES: [
        r"\bfrontend\b",
        r"\bui\b",
        r"\bcss\b",
        r"\bdom\b",
        r"\bbutton\b",
        r"\bcomponent\b",
        r"\bbrowser\b",
        r"\bjavascript\b",
        r"\brender(ing)?\b",
    ],
    BugCategory.PERFORMANCE_PROBLEMS: [
        r"\bslow\b",
        r"\blatency\b",
        r"\btimeout\b",
        r"\bmemory leak\b",
        r"\bcpu\b",
        r"\bbottleneck\b",
        r"\bperformance\b",
        r"\bhang(ing)?\b",
    ],
    BugCategory.DEPENDENCY_ISSUES: [
        r"\bimport\b",
        r"\bpackage\b",
        r"\bmodule not found\b",
        r"modulenotfounderror",
        r"importerror",
        r"no module named",
        r"\bpip\b",
        r"\bversion\b",
        r"\bdependency\b",
        r"\brequirements\b",
    ],
}

# Severity heuristics based on impact keywords
CRITICAL_INDICATORS = [
    r"\bsecurity\b",
    r"\bbypass\b",
    r"\bcrash\b",
    r"\bpanic\b",
    r"\bcorrupt\b",
    r"\bdata loss\b",
    r"\bvulnerability\b",
    r"\bexploit\b",
]

HIGH_INDICATORS = [
    r"\b500\b",
    r"\blogin.*broken\b",
    r"\bcannot login\b",
    r"\bwrong password.*returns 200\b",
    r"\b200 instead of 401\b",
    r"\bfails completely\b",
    r"\bunhandled exception\b",
    r"\bbroken\b",
    r"\bfailure\b",
]

LOW_INDICATORS = [
    r"\btypo\b",
    r"\bcosmetic\b",
    r"\bminor\b",
    r"\bdocs\b",
    r"\bformatting\b",
]


def classify_bug(text: str) -> BugCategory:
    """
    Classifies the bug text into one of the standardized BugCategory enums.
    Uses scoring based on regex pattern matches.
    """
    cleaned_text = text.lower()
    scores: dict[BugCategory, int] = {cat: 0 for cat in CATEGORY_PATTERNS}

    for cat, patterns in CATEGORY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, cleaned_text):
                scores[cat] += 1

    # Find highest scoring category
    best_cat = max(scores, key=lambda c: scores[c])
    if scores[best_cat] > 0:
        return best_cat
    return BugCategory.UNKNOWN


def assess_severity(text: str, category: BugCategory) -> Severity:
    """
    Evaluates severity level based on failure indicators and category risk profile.
    """
    cleaned = text.lower()

    for pat in CRITICAL_INDICATORS:
        if re.search(pat, cleaned):
            return Severity.CRITICAL

    for pat in HIGH_INDICATORS:
        if re.search(pat, cleaned):
            return Severity.HIGH

    # Authentication bugs with status mismatches or broken auth are high severity
    if category == BugCategory.AUTHENTICATION and ("200" in cleaned or "401" in cleaned or "error" in cleaned):
        return Severity.HIGH

    for pat in LOW_INDICATORS:
        if re.search(pat, cleaned):
            return Severity.LOW

    # Default baseline severity for general bugs
    if category in {BugCategory.AUTHENTICATION, BugCategory.DATABASE_ERRORS, BugCategory.API_FAILURES}:
        return Severity.MEDIUM
    return Severity.LOW


def extract_search_terms(text: str) -> List[str]:
    """
    Extracts high-signal search tokens (endpoints, function names, error names, keywords)
    from the bug description to guide repository inspection.
    """
    terms: set[str] = set()

    # Match paths like /api/v1/login or /login
    for path_match in re.findall(r"(/[a-zA-Z0-9_\-/]+)", text):
        clean_path = path_match.strip()
        if len(clean_path) > 1:
            terms.add(clean_path)
            for segment in clean_path.split("/"):
                if segment and len(segment) > 2:
                    terms.add(segment.lower())

    # Match CamelCase or PascalCase identifiers (e.g. InvalidPasswordException)
    for ident in re.findall(r"\b[A-Z][a-zA-Z0-9_]+\b", text):
        terms.add(ident)

    # Match snake_case identifiers (e.g. authenticate_user)
    for ident in re.findall(r"\b[a-z]+_[a-z0-9_]+\b", text):
        terms.add(ident)

    # Add core domain terms
    for word in ["login", "auth", "password", "username", "token", "status", "exception", "handler", "router"]:
        if word in text.lower():
            terms.add(word)

    return sorted(list(terms))
