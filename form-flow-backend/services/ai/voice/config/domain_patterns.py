"""
Domain Patterns Configuration

Email domain corrections and validations.
"""

import re

# Domain typo corrections (regex patterns)
DOMAIN_CORRECTIONS = {
    r'\bg[\s\-]*mail\b': 'gmail',
    r'\bgee[\s\-]*mail\b': 'gmail',
    r'\bgmale\b': 'gmail',
    r'\bgmal\b': 'gmail',
    r'\bjee[\s\-]*mail\b': 'gmail',
    r'\byaho+\b': 'yahoo',
    r'\byellow\b': 'yahoo',
    r'\bhot[\s\-]*mail\b': 'hotmail',
    r'\bhought[\s\-]*mail\b': 'hotmail',
    r'\bout[\s\-]*look\b': 'outlook',
    r'\baol\b': 'aol',
    r'\ba[\s\-]*o[\s\-]*l\b': 'aol',
    r'\bicloud\b': 'icloud',
    r'\bproton\b': 'proton',
    r'\bproton[\s\-]*mail\b': 'protonmail',
}

# TLD (Top Level Domain) corrections
TLD_CORRECTIONS = {
    'calm': 'com',
    'cam': 'com',
    'come': 'com',
    'con': 'com',
    'comb': 'com',
    'org': 'org',
    'net': 'net',
    'edu': 'edu',
    'gov': 'gov',
}

# Common email domains for validation
COMMON_DOMAINS = [
    'gmail.com',
    'yahoo.com',
    'hotmail.com',
    'outlook.com',
    'aol.com',
    'icloud.com',
    'protonmail.com',
    'live.com',
    'msn.com',
]

# Common TLDs
COMMON_TLDS = ['com', 'org', 'net', 'edu', 'gov', 'io', 'co', 'ai']


def apply_domain_corrections(text: str) -> str:
    """Apply all domain corrections to text."""
    result = text
    for pattern, replacement in DOMAIN_CORRECTIONS.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def apply_tld_corrections(text: str) -> str:
    """Apply TLD corrections to text."""
    result = text
    for wrong, correct in TLD_CORRECTIONS.items():
        # Only replace at word boundaries
        pattern = rf'\b{wrong}\b'
        result = re.sub(pattern, correct, result, flags=re.IGNORECASE)
    return result


def is_common_domain(domain: str) -> bool:
    """Check if domain is a common email provider."""
    return domain.lower() in COMMON_DOMAINS
