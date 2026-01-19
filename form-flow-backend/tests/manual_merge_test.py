
import asyncio
from typing import List, Dict
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

from services.form.parser import _merge_manual_fields

def test_manual_merge():
    print("🧪 Testing Manual Field Merging...")
    
    # Scene 1: Merge into existing form
    extracted = [{
        'formIndex': 0, 
        'name': 'Contact Form',
        'fields': [
            {'name': 'email', 'type': 'email', 'label': 'Email Address'},
            {'name': 'message', 'type': 'textarea', 'label': 'Your Message'}
        ]
    }]
    
    manual = [
        {'field_name': 'phone', 'field_type': 'tel', 'label': 'Phone Number'},
        {'field_name': 'email', 'field_type': 'email', 'label': 'Official Email'} # Override
    ]
    
    merged = _merge_manual_fields(extracted, manual)
    fields = merged[0]['fields']
    
    # Checks
    field_names = [f['name'] for f in fields]
    print(f"   Fields: {field_names}")
    
    assert 'phone' in field_names, "New field 'phone' should be added"
    assert 'email' in field_names, "Field 'email' should exist"
    
    email_field = next(f for f in fields if f['name'] == 'email')
    assert email_field['label'] == 'Official Email', "Email label should be overridden"
    assert email_field.get('manual_override'), "Email should be marked as manual override"
    
    phone_field = next(f for f in fields if f['name'] == 'phone')
    assert phone_field['display_name'] == 'Phone Number', "Phone display name should be generated"
    
    print("   ✅ Scene 1 Passed: Merge and Override")
    
    # Scene 2: Merge into empty result (fallback)
    extracted_empty = []
    
    merged_empty = _merge_manual_fields(extracted_empty, manual)
    
    assert len(merged_empty) == 1, "Should create synthetic form"
    assert merged_empty[0]['is_manual'], "Should be marked as manual form"
    assert len(merged_empty[0]['fields']) == 2, "Should have 2 fields"
    
    print("   ✅ Scene 2 Passed: Fallback Creation")

if __name__ == "__main__":
    try:
        test_manual_merge()
        print("\n🎉 All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test Failed: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
