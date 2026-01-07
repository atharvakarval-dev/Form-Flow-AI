"""
Profile Generation Prompts

LLM prompt templates for generating and updating user behavioral profiles
from form interactions. Uses Gemini for profile generation.

Templates:
    - PROFILE_CREATE_PROMPT: Initial profile creation
    - PROFILE_UPDATE_PROMPT: Update existing profile with new data
    - PROFILE_CONDENSE_PROMPT: Enforce 500-word limit
"""


# =============================================================================
# Profile Creation Prompt
# =============================================================================

PROFILE_CREATE_PROMPT = """# ROLE
You are a behavioral insight analyst specializing in building deep psychological profiles from user interactions. Your goal is to understand WHO the user is, not just WHAT they answered.

# TASK
Analyze the provided form responses and CREATE a comprehensive user profile that captures:
- Personality traits and behavioral patterns
- Decision-making style and priorities
- Goals, motivations, and underlying needs
- Communication preferences and cognitive style
- Risk tolerance and change orientation
- Values and belief systems

# CONSTRAINTS
- Maximum 500 words
- Focus on INFERENCE not REPETITION (analyze WHY they chose, not WHAT they chose)
- Be specific and actionable for suggestion generation
- Avoid demographic data storage unless behaviorally relevant

---

## INPUT DATA

### Form Context:
- Form Type: {form_type}
- Form Purpose: {form_purpose}
- Number of Questions: {question_count}

### User Responses:
{questions_and_answers}

---

## ANALYSIS FRAMEWORK

For each response, consider:

1. **Decision Pattern**: Did they choose safe/risky, detailed/broad, traditional/innovative?
2. **Language Style**: Formal/casual, brief/elaborate, emotional/logical?
3. **Priority Signals**: What did they emphasize? What did they skip or minimize?
4. **Confidence Level**: Decisive or uncertain in their selections?
5. **Time Orientation**: Past-focused, present-focused, or future-focused?

---

## OUTPUT FORMAT

Generate a profile structured EXACTLY as follows:

### Core Personality Profile
[2-3 sentences capturing essence]

### Decision-Making Style
- Primary approach: [analytical/intuitive/collaborative/decisive]
- Key priorities: [what drives their choices]
- Pattern observed: [specific behavioral tendency]

### Communication & Cognitive Style
- Preference: [how they process and share information]
- Detail orientation: [high-level vs. granular]
- Emotional vs. rational balance: [tendency]

### Goals & Motivations
- Underlying needs: [what they're truly seeking]
- Success indicators: [how they measure outcomes]
- Growth areas: [where they're developing]

### Behavioral Insights for Suggestions
- Response sweet spot: [length, tone, format they prefer]
- Triggers: [what engages or disengages them]
- Blind spots: [what they might overlook]

### Confidence Score
{expected_confidence} - Based on data sufficiency

---

## CRITICAL REMINDERS

❌ DON'T: Simply list what they answered
✅ DO: Explain what their answers reveal about them

❌ DON'T: "User selected option A"
✅ DO: "User prioritizes efficiency over comprehensiveness, suggesting time-conscious decision-making"

❌ DON'T: Store PII or demographic data unless behaviorally significant
✅ DO: Store cognitive and behavioral patterns that inform suggestions
"""


# =============================================================================
# Profile Update Prompt
# =============================================================================

PROFILE_UPDATE_PROMPT = """# ROLE
You are a behavioral insight analyst updating an existing user profile with new data from a recent form interaction.

# TASK
Analyze the NEW form responses and UPDATE the existing profile. Apply the 70/30 rule:
- 70% weight: Preserve existing profile patterns
- 30% weight: Incorporate new insights

# CONSTRAINTS
- Maximum 500 words
- Focus on INFERENCE not REPETITION
- Maintain continuity with existing profile
- Note significant behavioral shifts

---

## EXISTING PROFILE

{existing_profile}

---

## NEW FORM DATA

### Form Context:
- Form Type: {form_type}
- Form Purpose: {form_purpose}
- Number of Questions: {question_count}
- Forms Analyzed Previously: {previous_form_count}

### New User Responses:
{questions_and_answers}

---

## UPDATE RULES

1. **Reinforce**: Patterns appearing 2+ times across forms
2. **Refine**: Adjust confidence levels and specifics
3. **Add**: New dimensions not previously observed
4. **Flag Changes**: Note significant shifts in behavior
5. **Preserve Core**: Don't overwrite fundamental traits based on single form

---

## OUTPUT FORMAT

Generate an UPDATED profile with the same structure:

### Core Personality Profile
[2-3 sentences - update if new evidence warrants]

### Decision-Making Style
- Primary approach: [update if pattern confirmed or changed]
- Key priorities: [refine with new evidence]
- Pattern observed: [merge old/new patterns]

### Communication & Cognitive Style
- Preference: [update if new evidence]
- Detail orientation: [refine]
- Emotional vs. rational balance: [refine]

### Goals & Motivations
- Underlying needs: [update with new context]
- Success indicators: [refine]
- Growth areas: [update]

### Behavioral Insights for Suggestions
- Response sweet spot: [refine with new data]
- Triggers: [add new/confirm existing]
- Blind spots: [update]
- Evolution: [NEW - note how user is changing]

### Confidence Score
{expected_confidence} - Based on {total_form_count} forms analyzed

---

## CRITICAL: EVOLUTION TRACKING

If you notice the user's patterns are CHANGING from their previous profile, note this explicitly:

**Evolution Markers:**
- [List any behavioral shifts observed]
- [Note direction of change: e.g., "becoming more decisive" or "shifting toward detail-orientation"]
"""


# =============================================================================
# Condense Prompt (for 500-word limit enforcement)
# =============================================================================

PROFILE_CONDENSE_PROMPT = """The following behavioral profile is {word_count} words but must be exactly 500 words or fewer.

Condense it while preserving ALL key behavioral insights. Do not lose any actionable information.

Prioritize:
1. Core personality traits
2. Decision-making patterns
3. Communication preferences
4. Actionable insights for suggestions

Remove:
1. Redundant phrases
2. Excessive qualifiers
3. Non-essential examples

CURRENT PROFILE:
{profile_text}

OUTPUT: Condensed profile (max 500 words) with same structure.
"""


# =============================================================================
# Helper Functions
# =============================================================================

def format_questions_and_answers(form_data: dict) -> str:
    """
    Format form responses for prompt injection.
    
    Args:
        form_data: Dictionary with field_name: value pairs
        
    Returns:
        Formatted string for LLM prompt
    """
    lines = []
    for idx, (field, value) in enumerate(form_data.items(), 1):
        if value and str(value).strip():
            lines.append(f"{idx}. **{field}**: {value}")
    
    return "\n".join(lines) if lines else "No responses provided."


def calculate_expected_confidence(form_count: int, question_count: int) -> str:
    """
    Calculate expected confidence level description.
    
    Args:
        form_count: Number of forms analyzed
        question_count: Questions in current form
        
    Returns:
        Confidence level string for prompt
    """
    if form_count >= 5 and question_count >= 10:
        return "High (0.8+)"
    elif form_count >= 2 or question_count >= 8:
        return "Medium (0.5-0.7)"
    else:
        return "Low (0.3-0.5)"


def build_create_prompt(
    form_data: dict,
    form_type: str = "General",
    form_purpose: str = "Data collection"
) -> str:
    """
    Build a complete profile creation prompt.
    
    Args:
        form_data: User's form responses
        form_type: Type of form (e.g., "Application", "Survey")
        form_purpose: Purpose of the form
        
    Returns:
        Complete prompt string for LLM
    """
    question_count = len(form_data)
    
    return PROFILE_CREATE_PROMPT.format(
        form_type=form_type,
        form_purpose=form_purpose,
        question_count=question_count,
        questions_and_answers=format_questions_and_answers(form_data),
        expected_confidence=calculate_expected_confidence(1, question_count)
    )


def build_update_prompt(
    existing_profile: str,
    form_data: dict,
    previous_form_count: int,
    form_type: str = "General",
    form_purpose: str = "Data collection"
) -> str:
    """
    Build a complete profile update prompt.
    
    Args:
        existing_profile: Current profile text
        form_data: New form responses
        previous_form_count: Forms previously analyzed
        form_type: Type of new form
        form_purpose: Purpose of new form
        
    Returns:
        Complete prompt string for LLM
    """
    question_count = len(form_data)
    total_form_count = previous_form_count + 1
    
    return PROFILE_UPDATE_PROMPT.format(
        existing_profile=existing_profile,
        form_type=form_type,
        form_purpose=form_purpose,
        question_count=question_count,
        previous_form_count=previous_form_count,
        questions_and_answers=format_questions_and_answers(form_data),
        expected_confidence=calculate_expected_confidence(total_form_count, question_count),
        total_form_count=total_form_count
    )


def build_condense_prompt(profile_text: str) -> str:
    """
    Build a prompt to condense profile to 500 words.
    
    Args:
        profile_text: Current (too long) profile text
        
    Returns:
        Prompt for condensation
    """
    word_count = len(profile_text.split())
    return PROFILE_CONDENSE_PROMPT.format(
        word_count=word_count,
        profile_text=profile_text
    )
