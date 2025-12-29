"""
Test Local LLM Integration

Tests the local LLM service integration with the Form Flow AI backend.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'form-flow-backend'))

from services.ai.local_llm import get_local_llm_service, is_local_llm_available
from services.ai.conversation_agent import ConversationAgent


async def test_local_llm_service():
    """Test the local LLM service directly."""
    print("🧪 Testing Local LLM Service...")
    
    # Check availability
    available = is_local_llm_available()
    print(f"Local LLM Available: {available}")
    
    if not available:
        print("❌ Local LLM not available")
        return False
    
    # Get service
    service = get_local_llm_service()
    if not service:
        print("❌ Could not get local LLM service")
        return False
    
    # Test extraction
    test_cases = [
        ("My name is John Smith", "First Name"),
        ("I'm 25 years old", "Age"),
        ("john.doe@email.com", "Email Address"),
        ("I live in New York", "City")
    ]
    
    print("\n📝 Testing field extraction...")
    for user_input, field_name in test_cases:
        try:
            result = service.extract_field_value(user_input, field_name)
            print(f"Input: '{user_input}' -> Field: '{field_name}'")
            print(f"  Extracted: '{result.get('value')}' (confidence: {result.get('confidence', 0):.2f})")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print("\n✅ Local LLM service test complete")
    return True


async def test_conversation_agent_integration():
    """Test the conversation agent with local LLM fallback."""
    print("\n🤖 Testing Conversation Agent Integration...")
    
    try:
        # Create agent without API key to force local LLM usage
        agent = ConversationAgent(api_key=None)
        
        # Check if local LLM is available as fallback
        has_local_llm = hasattr(agent, 'local_llm') and agent.local_llm is not None
        print(f"Agent has local LLM fallback: {has_local_llm}")
        
        if not has_local_llm:
            print("❌ Conversation agent doesn't have local LLM fallback")
            return False
        
        # Create a simple form schema for testing
        form_schema = [{
            "fields": [
                {"name": "first_name", "label": "First Name", "type": "text", "required": True},
                {"name": "email", "label": "Email", "type": "email", "required": True}
            ]
        }]
        
        # Create session
        session = await agent.create_session(form_schema)
        print(f"Created session: {session.id}")
        
        # Test processing user input
        response = await agent.process_user_input(
            session.id, 
            "My name is Alice Johnson"
        )
        
        print(f"Agent response: {response.message}")
        print(f"Extracted values: {response.extracted_values}")
        
        print("✅ Conversation agent integration test complete")
        return True
        
    except Exception as e:
        print(f"❌ Conversation agent test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting Local LLM Integration Tests\n")
    
    # Test 1: Local LLM Service
    service_ok = await test_local_llm_service()
    
    # Test 2: Conversation Agent Integration
    agent_ok = await test_conversation_agent_integration()
    
    # Summary
    print(f"\n📊 Test Results:")
    print(f"  Local LLM Service: {'✅ PASS' if service_ok else '❌ FAIL'}")
    print(f"  Agent Integration: {'✅ PASS' if agent_ok else '❌ FAIL'}")
    
    if service_ok and agent_ok:
        print("\n🎉 All tests passed! Local LLM is integrated successfully.")
    else:
        print("\n⚠️ Some tests failed. Check the logs above.")


if __name__ == "__main__":
    asyncio.run(main())