"""Test the correction detector with various patterns including edge cases."""

from services.ai.voice.correction_detector import CorrectionDetector, FieldContext
from services.ai.voice.processor import VoiceProcessor

detector = CorrectionDetector()

# =============================================================================
# Standard Correction Tests
# =============================================================================
test_cases = [
    # Explicit strong
    ('my name is John actually James', 'text'),
    ('email john@gmail let me correct that james@gmail', 'email'),
    ('scratch that, my name is Sarah', 'text'),
    # Medium - "oh sorry" patterns
    ('Hi my name is Atharva oh sorry its Shashikant', 'text'),
    ('my name is John sorry its James', 'text'),
    ('the email is john oops, james@gmail', 'email'),
    # No its patterns
    ('no its Shashikant Karve', 'text'),
    ('no it is alex@gmail.com', 'email'),
    # Standard patterns
    ('phone 5551234 I mean 5554321', 'tel'),
    ('John no wait Jake', 'text'),
    # Restart
    ('j... james', 'text'),
    # Nested
    ('John James actually Jake', 'text'),
]

print('=== Correction Detection Tests ===\n')
for text, field_type in test_cases:
    ctx = FieldContext(field_type=field_type)
    result = detector.detect(text, ctx)
    status = '✓' if result.has_correction else '✗'
    print(f'{status} "{text}"')
    if result.has_correction:
        print(f'   → Corrected: "{result.corrected_value}" (pattern: {result.pattern_matched}, conf: {result.confidence})')
    print()

# =============================================================================
# EDGE CASE TESTS (Sentence Preservation)
# =============================================================================
print('\n=== Edge Case Tests (Sentence Preservation) ===\n')

edge_cases = [
    # Full sentence preservation
    {
        'input': 'Hi my number is 9518 oh sorry its 9618377949',
        'field_type': 'tel',
        'expected_value': '9618377949',
        'description': 'Full sentence with correction in middle'
    },
    # Multi-field preservation
    {
        'input': 'My name is Atharva and my number is 9518 sorry 9618377949',
        'field_type': 'text',
        'expected_value': '9618377949',
        'description': 'Multi-field input - name should be preserved'
    },
    # Partial word (cut-off before correction)
    {
        'input': 'It is Janu- no February 2nd',
        'field_type': 'date',
        'expected_value': 'February 2nd',
        'description': 'Partial word cut-off'
    },
    # Total restart (user abandons structure)
    {
        'input': 'I need a.. actually forget it I want a refund',
        'field_type': 'text',
        'expected_value': 'I want a refund',
        'description': 'Total restart - abandon previous structure'
    },
    # Repeated value (incomplete → complete)
    {
        'input': 'Call 555. No, call 555-0199',
        'field_type': 'tel',
        'expected_value': '555-0199',
        'description': 'Repeated value completion'
    },
    # "Instead" pattern
    {
        'input': 'my email is john@gmail instead sarah@gmail',
        'field_type': 'email',
        'expected_value': 'sarah@gmail',
        'description': 'Instead correction pattern'
    },
]

for case in edge_cases:
    ctx = FieldContext(field_type=case['field_type'])
    result = detector.detect(case['input'], ctx)
    
    status = '✓' if result.has_correction else '✗'
    match = '✓' if case['expected_value'] in result.corrected_value else '✗'
    
    print(f'{status} {case["description"]}')
    print(f'   Input: "{case["input"]}"')
    print(f'   Expected: "{case["expected_value"]}"')
    print(f'   Got: "{result.corrected_value}" {match}')
    print()

# =============================================================================
# VoiceProcessor Integration Test
# =============================================================================
print('\n=== VoiceProcessor Integration Test ===\n')
processor = VoiceProcessor()

voice_tests = [
    ('my email is john at gmail actually james at gmail', 'email', 'email'),
    ('my name is J... James', 'text', 'name'),
    ('phone 555 1234 no wait 555 4321', 'tel', 'phone'),
    ('Hi my number is 9518 oh sorry its 9618377949', 'tel', 'phone'),
]

for text, field_type, field_name in voice_tests:
    result = processor.normalize_input(text, field_type=field_type, field_name=field_name)
    print(f'Input: "{text}"')
    print(f'   → Output: "{result}"')
    print()

print('\n=== All tests completed ===')
