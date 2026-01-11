"""
Smart Text Normalizers

Centralized, context-aware normalizers for voice input processing.
These normalizers are used across the entire codebase to ensure consistent behavior.

Key Features:
- Email normalization that doesn't corrupt names like "Atharva" to "@harva"
- Phone normalization that strips conversational prefixes
- Name normalization that extracts just the name value

Usage:
    from services.ai.normalizers import normalize_email_smart, normalize_phone_smart
    
    email = normalize_email_smart("Atharva Karwal @ gmail dot com")
    # Returns: "atharvakarwal@gmail.com"
"""

import re
from typing import Optional


# Known email domains for context-aware "at" → "@" conversion
KNOWN_DOMAINS = [
    'gmail', 'yahoo', 'hotmail', 'outlook', 'aol', 'icloud', 
    'protonmail', 'mail', 'live', 'msn', 'ymail', 'zoho',
    'fastmail', 'pm', 'tutanota', 'hey', 'proton'
]


def normalize_email_smart(text: str) -> str:
    """
    Smart email normalization that avoids corrupting names like "Atharva" to "@harva".
    
    This is the SINGLE SOURCE OF TRUTH for email normalization across the codebase.
    
    Strategy:
    1. First normalize spaces around existing @ symbols
    2. Only convert " at " to "@" when followed by known domains
    3. Clean up the result and auto-complete domains
    
    Args:
        text: Raw input text (voice transcription or typed)
        
    Returns:
        Normalized email address
        
    Examples:
        "atharva at gmail dot com" → "atharva@gmail.com"  ✓
        "Atharva Karwal @ gmail.com" → "atharvakarwal@gmail.com"  ✓
        "my name is Atharva" → "my name is atharva"  ✓ (no corruption)
    """
    if not text:
        return text
        
    text = text.lower().strip()
    
    # Step 1: Remove conversational prefixes (NEW)
    prefixes = [
        r"^(?:my\s+)?(?:email\s+)?(?:address|addresses)?\s+(?:is\s+)?",
        r"^(?:it'?s?\s+)",
        r"^(?:my\s+)?email\s+(?:is\s+)?",
    ]
    for prefix in prefixes:
        text = re.sub(prefix, '', text, flags=re.IGNORECASE)
    
    text = text.strip()

    # Step 2: Replace voice keywords for punctuation
    text = text.replace(' dot ', '.')
    text = text.replace(' underscore ', '_')
    text = text.replace(' dash ', '-')
    text = text.replace(' hyphen ', '-')
    
    # Handle edge cases: "dot" at end
    text = text.replace(' dot', '.')
    
    # Step 3: Normalize spaces around existing @ symbol
    text = re.sub(r'\s*@\s*', '@', text)
    
    # Step 4: Context-aware "at" → "@" conversion
    domain_pattern = '|'.join(KNOWN_DOMAINS)
    text = re.sub(rf'\s+at\s+({domain_pattern})(\.\w+)?', r'@\1\2', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+at\s+(\w+\.(com|org|net|edu|gov|io|co|in|info|biz|me))', r'@\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+at\s*the\s*rate\s*(of\s*)?', '@', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+at\s*sign\s*', '@', text, flags=re.IGNORECASE)
    
    # Step 5: Clean up spaces around @ and before TLD dots
    text = re.sub(r'\s*@\s*', '@', text)
    text = re.sub(r'\s*\.\s*(com|org|net|edu|gov|io|co|in)\b', r'.\1', text)
    
    # Step 6: Extract and clean email
    if '@' in text:
        # 1. Try Look-back extraction first (handles spaces: "Atharva karwal@gmail.com")
        at_index = text.find('@')
        if at_index > 0:
            before_at = text[:at_index]
            after_at = text[at_index+1:]
             
            # Split before_at by spaces
            candidates = before_at.split()
            valid_parts = []
            for part in reversed(candidates):
                # Stop if we hit a keyword or invalid char
                # Allow dots, underscores, dashes, plus in local part
                if re.match(r'^[a-zA-Z0-9._\-+]+$', part) and part.lower() not in ['is', 'at', 'my', 'the', 'email', 'address']:
                    valid_parts.insert(0, part)
                else:
                    break
             
            if valid_parts:
                local = "".join(valid_parts)
                # Get domain (first word after @)
                domain_match = re.search(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', after_at)
                if domain_match:
                    domain = domain_match.group(0)
                    return f"{local}@{domain}"

        # 2. Fallback to strict extraction (non-whitespace around @)
        strict_match = re.search(r'(\S+@\S+\.\w+)', text)
        if strict_match:
             parts = strict_match.group(1).split('@')
             if len(parts) == 2:
                 return f"{parts[0]}@{parts[1]}"

        # 3. Relaxed extraction (allow spaces in local part if it was split)
        parts = text.split('@')
        if len(parts) >= 2:
            local_part = parts[0]
            domain = parts[1].strip()
            
            # Clean local part
            local_cleaned = re.sub(r'[^\w.\-+]', '', local_part)
            domain = domain.replace(' ', '').strip()
            
            # Auto-complete common domains
            domain_completions = {
                'gmail': 'gmail.com', 'geemail': 'gmail.com', 'gmal': 'gmail.com',
                'yahoo': 'yahoo.com', 'yaho': 'yahoo.com',
                'hotmail': 'hotmail.com', 'outlook': 'outlook.com',
                'icloud': 'icloud.com', 'protonmail': 'protonmail.com',
            }
            if domain in domain_completions:
                domain = domain_completions[domain]
            
            return f"{local_cleaned}@{domain}"

    return text


def normalize_phone_smart(text: str) -> str:
    """
    Smart phone normalization that strips conversational context.
    
    Args:
        text: Raw input text
        
    Returns:
        Clean phone number (digits and + only)
        
    Examples:
        "my phone is 9876543210" → "9876543210"
        "it's +91 98765 43210" → "+919876543210"
        "call me at 555-123-4567" → "5551234567"
    """
    if not text:
        return text
        
    text = text.lower().strip()
    
    # Remove conversational prefixes
    prefixes = [
        r"^(?:my\s+)?(?:phone|mobile|cell|contact|number)\s+(?:number\s+)?(?:is\s+)?",
        r"^(?:it'?s?\s+)?",
        r"^(?:call\s+me\s+(?:at|on)\s+)?",
        r"^(?:you\s+can\s+reach\s+me\s+(?:at|on)\s+)?",
        r"^(?:here'?s?\s+)?(?:my\s+)?(?:number\s+)?",
    ]
    
    for prefix in prefixes:
        text = re.sub(prefix, '', text, flags=re.IGNORECASE)
    
    # Extract just digits and + sign
    phone = re.sub(r'[^\d+]', '', text)
    
    return phone if phone else text.strip()


def normalize_name_smart(text: str) -> str:
    """
    Smart name normalization that strips conversational context.
    
    Args:
        text: Raw input text
        
    Returns:
        Clean name in Title Case
        
    Examples:
        "my name is John Doe" → "John Doe"
        "I'm Sarah Connor" → "Sarah Connor"
        "it's Michael" → "Michael"
    """
    if not text:
        return text
        
    text = text.strip()
    
    # Remove conversational prefixes
    prefixes = [
        r"^(?:hi\s+)?(?:my\s+)?(?:name\s+is\s+)",
        r"^(?:i'?m\s+)",
        r"^(?:this\s+is\s+)",
        r"^(?:it'?s?\s+)",
        r"^(?:call\s+me\s+)",
        r"^(?:you\s+can\s+call\s+me\s+)",
        r"^(?:hey\s+)?(?:i\s+am\s+)",
    ]
    
    for prefix in prefixes:
        text = re.sub(prefix, '', text, flags=re.IGNORECASE)
    
    return text.strip().title()


def normalize_text_smart(text: str) -> str:
    """
    Smart text normalization that strips common conversational filler.
    
    Args:
        text: Raw input text
        
    Returns:
        Clean text value
        
    Examples:
        "it's Google" → "Google"
        "I work at Microsoft" → "Microsoft"
        "my company is Apple" → "Apple"
    """
    if not text:
        return text
        
    text = text.strip()
    
    # Remove conversational prefixes
    prefixes = [
        r"^(?:it'?s?\s+)",
        r"^(?:i\s+(?:work|am)\s+(?:at|for|with)\s+)",
        r"^(?:my\s+\w+\s+is\s+)",
        r"^(?:the\s+\w+\s+is\s+)",
        r"^(?:we\s+are\s+)",
    ]
    
    for prefix in prefixes:
        text = re.sub(prefix, '', text, flags=re.IGNORECASE)
    
    return text.strip()


def normalize_number_smart(text: str) -> str:
    """
    Smart number normalization that strips conversational context.
    
    Args:
        text: Raw input text
        
    Returns:
        Extracted number
        
    Examples:
        "it's 25" → "25"
        "I have 3 years of experience" → "3"
        "my age is 30" → "30"
    """
    if not text:
        return text
        
    text = text.lower().strip()
    
    # Remove conversational prefixes
    prefixes = [
        r"^(?:it'?s?\s+)?",
        r"^(?:i\s+have\s+)?",
        r"^(?:my\s+\w+\s+is\s+)?",
        r"^(?:about\s+)?",
        r"^(?:around\s+)?",
    ]
    
    for prefix in prefixes:
        text = re.sub(prefix, '', text, flags=re.IGNORECASE)
    
    # Extract the first number found
    match = re.search(r'\d+(?:\.\d+)?', text)
    if match:
        return match.group()
    
    return text.strip()


def split_full_name_smart(full_name: str) -> dict:
    """
    Split a full name into first, middle, and last components.
    
    Args:
        full_name: Full name string like "John Michael Doe"
        
    Returns:
        Dict with 'first', 'middle', 'last' keys (values may be empty strings)
        
    Examples:
        "John Michael Doe" → {"first": "John", "middle": "Michael", "last": "Doe"}
        "John Doe" → {"first": "John", "middle": "", "last": "Doe"}
        "John" → {"first": "John", "middle": "", "last": ""}
        "John Michael Paul Doe" → {"first": "John", "middle": "Michael Paul", "last": "Doe"}
    """
    result = {'first': '', 'middle': '', 'last': ''}
    
    if not full_name:
        return result
    
    # First normalize the name (strip conversational prefixes, title case)
    cleaned = normalize_name_smart(full_name)
    
    if not cleaned:
        return result
    
    # Split by whitespace
    parts = cleaned.split()
    
    if len(parts) == 1:
        # Single word: just first name
        result['first'] = parts[0]
    elif len(parts) == 2:
        # Two words: first and last
        result['first'] = parts[0]
        result['last'] = parts[1]
    else:
        # Three or more words: first, middle (everything in between), last
        result['first'] = parts[0]
        result['last'] = parts[-1]
        result['middle'] = ' '.join(parts[1:-1])
    
    return result
