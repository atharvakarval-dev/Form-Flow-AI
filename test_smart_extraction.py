
import os
import sys

# Add project root to path
# Add project root to path
sys.path.append(os.path.join(os.getcwd(), 'form-flow-backend'))

from services.ai.local_llm import get_local_llm_service
from utils.logging import setup_logging

def test_smart_extraction():
    # Setup logging to see GPU status
    setup_logging(level="INFO")
    
    print("🚀 Initializing Local LLM Service...")
    # Mock settings if needed, or rely on env
    service = get_local_llm_service()
    
    if not service:
        print("❌ Failed to initialize service (check logs)")
        return

    # User's example schema
    fields = [
        {"name": "full_name", "label": "Full Name", "type": "text"},
        {"name": "email", "label": "Email Address", "type": "email"},
        {"name": "phone", "label": "Phone", "type": "tel"},
        {"name": "country", "label": "Country", "type": "text"},
        {"name": "contact_reason", "label": "Contact Reason", "type": "select", "options": [
            {"label": "Project Enquiry", "value": "project_enquiry"},
            {"label": "Job Application", "value": "job_application"},
            {"label": "Other", "value": "other"}
        ]},
        {"name": "message", "label": "Message", "type": "textarea"}
    ]
    
    # User's example speech
    user_input = "Patil my email id has email id as test@gmail.com country India the reason for contact is a project enquiry the message saying I want to get more information about the"
    
    print(f"\n🗣️ User Input: \"{user_input}\"")
    print(f"📋 Fields: {[f['label'] for f in fields]}")
    
    print("\n🔮 Running extraction...")
    try:
        result = service.extract_all_fields(user_input, fields)
        print("\n✅ Extraction Result:")
        for key, value in result['extracted'].items():
            print(f"  - {key}: {value}")
            
    except Exception as e:
        print(f"❌ Error during extraction: {e}")

if __name__ == "__main__":
    test_smart_extraction()
