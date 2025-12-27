"""
Voice Config Package

Configuration files for voice processing.
"""

from services.ai.voice.config.stt_patterns import (
    STT_EMAIL_PATTERNS,
    STT_PUNCTUATION,
    NUMBER_WORDS,
    COMPOUND_NUMBERS,
    get_all_stt_patterns,
)

from services.ai.voice.config.domain_patterns import (
    DOMAIN_CORRECTIONS,
    TLD_CORRECTIONS,
    COMMON_DOMAINS,
    COMMON_TLDS,
    apply_domain_corrections,
    apply_tld_corrections,
    is_common_domain,
)

from services.ai.voice.config.field_importance import (
    FieldImportance,
    FIELD_IMPORTANCE_MAP,
    BASE_THRESHOLDS,
    DIFFICULT_VOICE_FIELDS,
    get_field_importance,
    get_threshold,
    is_difficult_voice_field,
)

__all__ = [
    'STT_EMAIL_PATTERNS',
    'STT_PUNCTUATION', 
    'NUMBER_WORDS',
    'COMPOUND_NUMBERS',
    'get_all_stt_patterns',
    'DOMAIN_CORRECTIONS',
    'TLD_CORRECTIONS',
    'COMMON_DOMAINS',
    'COMMON_TLDS',
    'apply_domain_corrections',
    'apply_tld_corrections',
    'is_common_domain',
    'FieldImportance',
    'FIELD_IMPORTANCE_MAP',
    'BASE_THRESHOLDS',
    'DIFFICULT_VOICE_FIELDS',
    'get_field_importance',
    'get_threshold',
    'is_difficult_voice_field',
]
