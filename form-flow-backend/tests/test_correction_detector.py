"""Test the correction detector with various patterns."""

from services.ai.voice.correction_detector import CorrectionDetector, FieldContext
from services.ai.voice.processor import VoiceProcessor

detector = CorrectionDetector()

test_cases = [
    # Explicit strong
    ('my name is John actually James', 'text'),
    ('email john@gmail let me correct that james@gmail', 'email'),
    ('scratch that, my name is Sarah', 'text'),
    # Medium
    ('phone 5551234 I mean 5554321', 'tel'),
    ('John no wait Jake', 'text'),
    ('sorry, it should be Smith', 'text'),
    # Negation
    ('not John, it is James', 'text'),
    ('no, it is alex@gmail.com', 'email'),
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

print('\n=== VoiceProcessor Integration Test ===\n')
processor = VoiceProcessor()

# Test that corrections flow through the full pipeline
voice_tests = [
    ('my email is john at gmail actually james at gmail', 'email', 'email'),
    ('my name is J... James', 'text', 'name'),
    ('phone 555 1234 no wait 555 4321', 'tel', 'phone'),
]

for text, field_type, field_name in voice_tests:
    result = processor.normalize_input(text, field_type=field_type, field_name=field_name)
    print(f'Input: "{text}"')
    print(f'   → Output: "{result}"')
    print()

print('\n=== All tests completed ===')

