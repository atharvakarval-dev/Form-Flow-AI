import asyncio
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to sys.path
sys.path.append('d:\\Form-Flow-AI\\form-flow-backend')

from services.ai.profile.suggestions import ProfileSuggestionEngine, SuggestionTier, IntelligentSuggestion
from services.ai.form_intent import FormIntent

class TestContextAwareSuggestions(unittest.IsolatedAsyncioTestCase):
    async def test_llm_prompt_includes_context(self):
        # Mock dependencies
        mock_gemini = MagicMock()
        mock_gemini.llm = MagicMock()
        
        # Mock the chain execution
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = {
            "suggestions": ["France"],
            "reasoning": "Context implies location."
        }
        
        # Patch get_gemini_service to return our mock
        with patch('services.ai.gemini.get_gemini_service', return_value=mock_gemini), \
             patch('services.ai.profile.suggestions.ChatPromptTemplate') as MockPrompt, \
             patch('services.ai.profile.suggestions.JsonOutputParser'):
            
            # Setup the mock prompt chain
            mock_prompt_instance = MagicMock()
            MockPrompt.from_messages.return_value = mock_prompt_instance
            # Chain: prompt | llm | parser
            mock_prompt_instance.__or__.return_value = MagicMock(__or__=MagicMock(return_value=mock_chain))

            engine = ProfileSuggestionEngine()
            
            # Test Input
            profile = "User lives in Europe."
            field_context = {"name": "country", "label": "Country"}
            form_context = {"purpose": "Travel"}
            form_intent = FormIntent(intent="Travel", persona="Traveler", form_type="public_facing")
            previous_answers = {"City": "Paris"}

            # Execute
            suggestions = await engine._generate_llm_suggestions(
                profile=profile,
                field_context=field_context,
                form_context=form_context,
                form_intent=form_intent,
                previous_answers=previous_answers
            )

            # Verification
            # Check if ain voke was called with the correct context
            call_args = mock_chain.ainvoke.call_args[0][0]
            self.assertIn("previous_answers_context", call_args)
            self.assertIn("- City: Paris", call_args["previous_answers_context"])
            print("\\nSUCCESS: 'previous_answers_context' was passed to LLM prompt!")
            print(f"Context Value: {call_args['previous_answers_context']}")

if __name__ == '__main__':
    unittest.main()
