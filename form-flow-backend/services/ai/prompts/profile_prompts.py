"""
Profile Generation Prompts

LLM prompt templates for generating and updating user behavioral profiles
from form interactions. Uses Gemini/OpenRouter for profile generation.

Output is strict JSON for structured frontend rendering.
"""

import json

# =============================================================================
# Profile Creation Prompt (JSON)
# =============================================================================

PROFILE_CREATE_PROMPT = """# ROLE
You are an expert behavioral analyst and psychologist. You assume the persona of a lead researcher writing a psychological case study on a subject.

# TASK
Analyze the provided form responses to create a "Personal Case Study" of the user.
Do NOT use generic AI language ("As an AI", "Based on the data"). Write with authority and depth.

# OUTPUT FORMAT
You must return VALID JSON with the following schema:

{{
    "executive_summary": "A 2-3 sentence high-level overview of who this person is.",
    "psychological_profile": {{
        "personality_archetype": "A specific 2-3 word archetype (e.g., 'The Strategic Optimizer', 'The Empathetic Realist')",
        "core_traits": ["Trait 1", "Trait 2", "Trait 3", "Trait 4"],
        "mindset_analysis": "A deep-dive paragraph (4-5 sentences) analyzing their cognitive framework and how they process the world."
    }},
    "behavioral_patterns": {{
        "decision_making": "Analysis of how they make choices.",
        "risk_tolerance": "Analysis of their relationship with risk and certainty.",
        "communication_style": "How they prefer to convey and receive information."
    }},
    "motivation_matrix": {{
        "underlying_drivers": ["Driver 1", "Driver 2"],
        "success_metrics": "What they seem to implicitly value as 'success'."
    }},
    "growth_trajectory": {{
        "current_focus": "What they are currently prioritizing.",
        "potential_blind_spots": ["Blind Spot 1", "Blind Spot 2"],
        "development_areas": "Where they could benefit from growth."
    }}
}}

---

## INPUT DATA

### Form Context:
- Form Type: {form_type}
- Form Purpose: {form_purpose}
- Number of Questions: {question_count}

### User Responses:
{questions_and_answers}
"""


# =============================================================================
# Profile Update Prompt (JSON)
# =============================================================================

PROFILE_UPDATE_PROMPT = """# ROLE
You are an expert behavioral analyst updating a "Personal Case Study".

# TASK
Integrate new form data into the existing psychological profile.
Maintain the structured JSON format.

# HISTORY
Forms previously filled by this user: {forms_history}

# INPUT DATA

### Existing Profile (JSON):
{existing_profile}

### New Form Data:
- Form Type: {form_type}
- Form Purpose: {form_purpose}
- Responses:
{questions_and_answers}

# UPDATE INSTRUCTIONS
1. **Refine Archetype**: Does the new data support or contradict the current archetype? Adjust if needed.
2. **Track Evolution**: In the 'interaction_history' section, note any shifts.
3. **Deepen Insight**: Use the new data to make the 'mindset_analysis' more specific.

# OUTPUT FORMAT
Return VALID JSON updating the schema. You MUST include a new field "interaction_history":

{{
    "executive_summary": "Updated summary...",
    "psychological_profile": {{
        "personality_archetype": "...",
        "core_traits": [...],
        "mindset_analysis": "..."
    }},
    "behavioral_patterns": {{ ... }},
    "motivation_matrix": {{ ... }},
    "growth_trajectory": {{ ... }},
    "interaction_history": {{
        "observation_log": "A brief note on how this specific form '{form_type}' added to your understanding.",
        "behavioral_evolution": "Describe any changes in the user's style over time (e.g., 'Becoming more decisive')."
    }}
}}
"""


# =============================================================================
# Condense Prompt (JSON preservation)
# =============================================================================

PROFILE_CONDENSE_PROMPT = """The following JSON profile is too large.
Condense the text values within the JSON fields to be more concise, but maintain the EXACT JSON structure and all keys.
Do not remove keys. Just summarize the string values.

JSON PROFILE:
{profile_text}
"""


# =============================================================================
# Helper Functions
# =============================================================================

def format_questions_and_answers(form_data: dict) -> str:
    """Format form responses for prompt injection."""
    lines = []
    for idx, (field, value) in enumerate(form_data.items(), 1):
        if value and str(value).strip():
            lines.append(f"{idx}. **{field}**: {value}")
    
    return "\n".join(lines) if lines else "No responses provided."


def build_create_prompt(
    form_data: dict,
    form_type: str = "General",
    form_purpose: str = "Data collection"
) -> str:
    """Build a complete profile creation prompt."""
    question_count = len(form_data)
    
    return PROFILE_CREATE_PROMPT.format(
        form_type=form_type,
        form_purpose=form_purpose,
        question_count=question_count,
        questions_and_answers=format_questions_and_answers(form_data)
    )


def build_update_prompt(
    existing_profile: str,
    form_data: dict,
    previous_form_count: int,
    form_type: str = "General",
    form_purpose: str = "Data collection",
    forms_history: list = None
) -> str:
    """Build a complete profile update prompt."""
    question_count = len(form_data)
    
    if forms_history is None:
        forms_history = []
        
    # Format history as string
    history_str = ", ".join(forms_history) if forms_history else "None"
    
    return PROFILE_UPDATE_PROMPT.format(
        existing_profile=existing_profile,
        form_type=form_type,
        form_purpose=form_purpose,
        question_count=question_count,
        previous_form_count=previous_form_count,
        questions_and_answers=format_questions_and_answers(form_data),
        forms_history=history_str
    )


def build_condense_prompt(profile_text: str) -> str:
    """Build a prompt to condense profile."""
    return PROFILE_CONDENSE_PROMPT.format(profile_text=profile_text)
