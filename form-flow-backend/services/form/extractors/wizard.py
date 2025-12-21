"""
Wizard/Multi-step form extractor module.
Handles navigation through multi-step forms to collect all fields.
"""

import asyncio
import json
from typing import List, Dict, Any
from ..utils.constants import WIZARD_INDICATORS, WIZARD_NEXT_BUTTON_SELECTORS
from ..utils.page_helpers import wait_for_dom_stability


async def detect_wizard_form(page) -> bool:
    """
    Check if the page contains a wizard/multi-step form.
    """
    indicators_js = json.dumps(WIZARD_INDICATORS)
    
    return await page.evaluate(f"""
        () => {{
            const wizardIndicators = {indicators_js};
            return wizardIndicators.some(sel => {{
                try {{
                    return document.querySelector(sel) !== null;
                }} catch(e) {{ return false; }}
            }});
        }}
    """)


async def get_current_step_info(page) -> Dict[str, Any]:
    """
    Get information about the current wizard step.
    """
    return await page.evaluate("""
        () => {
            // Try to find step indicators
            const stepIndicators = document.querySelectorAll(
                '.ant-steps-item, .MuiStep-root, .v-stepper__step, ' +
                '[class*="step"], [role="tab"]'
            );
            
            let currentStep = 0;
            let totalSteps = stepIndicators.length;
            
            stepIndicators.forEach((step, idx) => {
                if (step.classList.contains('ant-steps-item-active') ||
                    step.classList.contains('ant-steps-item-process') ||
                    step.classList.contains('Mui-active') ||
                    step.classList.contains('v-stepper__step--active') ||
                    step.getAttribute('aria-current') === 'step' ||
                    step.getAttribute('aria-selected') === 'true') {
                    currentStep = idx + 1;
                }
            });
            
            // Try to extract step title
            const activeStep = document.querySelector(
                '.ant-steps-item-active .ant-steps-item-title, ' +
                '.Mui-active .MuiStepLabel-label, ' +
                '[aria-current="step"]'
            );
            
            return {
                currentStep: currentStep || 1,
                totalSteps: totalSteps || 1,
                stepTitle: activeStep?.textContent?.trim() || null
            };
        }
    """)


async def click_next_button(page) -> bool:
    """
    Try to click the "Next" button to advance the wizard.
    Returns True if successful, False otherwise.
    """
    # Common next button texts
    next_texts = ['Next', 'Continue', 'Proceed', 'Forward', '→', 'Next Step', 'Siguiente']
    
    for text in next_texts:
        try:
            # Try to find and click button with this text
            button = await page.query_selector(f'button:has-text("{text}"), a:has-text("{text}")')
            if button:
                # Check if button is visible and enabled
                is_clickable = await button.evaluate("""
                    el => el.offsetParent !== null && 
                          !el.disabled && 
                          !el.classList.contains('disabled')
                """)
                if is_clickable:
                    await button.click()
                    return True
        except:
            continue
    
    # Try generic next button selectors
    selectors_js = json.dumps(WIZARD_NEXT_BUTTON_SELECTORS)
    
    clicked = await page.evaluate(f"""
        () => {{
            const nextSelectors = {selectors_js};
            const nextTexts = ['next', 'continue', 'proceed', 'forward', 'siguiente'];
            
            for (const selector of nextSelectors) {{
                try {{
                    const elements = document.querySelectorAll(selector);
                    for (const el of elements) {{
                        const text = (el.textContent || '').toLowerCase();
                        if (nextTexts.some(t => text.includes(t))) {{
                            if (el.offsetParent !== null && !el.disabled) {{
                                el.click();
                                return true;
                            }}
                        }}
                    }}
                }} catch(e) {{}}
            }}
            return false;
        }}
    """)
    
    return clicked


async def click_previous_button(page) -> bool:
    """
    Try to click the "Previous" button to go back in the wizard.
    """
    prev_texts = ['Previous', 'Back', 'Go Back', '←', 'Prev', 'Anterior']
    
    for text in prev_texts:
        try:
            button = await page.query_selector(f'button:has-text("{text}"), a:has-text("{text}")')
            if button:
                is_clickable = await button.evaluate("""
                    el => el.offsetParent !== null && 
                          !el.disabled && 
                          !el.classList.contains('disabled')
                """)
                if is_clickable:
                    await button.click()
                    return True
        except:
            continue
    
    return False


async def navigate_wizard_and_extract(page, extract_fn) -> List[Dict]:
    """
    Navigate through all wizard steps and extract fields from each.
    
    Args:
        page: Playwright page object
        extract_fn: Function to call for extracting fields from current step
        
    Returns:
        List of all forms/fields extracted from all steps
    """
    is_wizard = await detect_wizard_form(page)
    
    if not is_wizard:
        return []
    
    print("🔄 Detected wizard form, navigating through steps...")
    
    all_forms = []
    visited_steps = set()
    max_steps = 15
    step_count = 0
    
    while step_count < max_steps:
        # Get current step info
        step_info = await get_current_step_info(page)
        step_key = f"{step_info['currentStep']}_{step_info.get('stepTitle', '')}"
        
        # Skip if already visited this step
        if step_key in visited_steps:
            break
        visited_steps.add(step_key)
        
        print(f"  📋 Step {step_info['currentStep']}/{step_info['totalSteps']}: {step_info.get('stepTitle', 'Untitled')}")
        
        # Extract fields from current step
        try:
            step_forms = await extract_fn(page.main_frame)
            
            # Mark fields with step info
            for form in step_forms:
                form['wizardStep'] = step_info['currentStep']
                form['wizardTotalSteps'] = step_info['totalSteps']
                form['stepTitle'] = step_info.get('stepTitle')
                
            all_forms.extend(step_forms)
        except Exception as e:
            print(f"    ⚠️ Error extracting step: {e}")
        
        # Try to click "Next"
        next_clicked = await click_next_button(page)
        
        if not next_clicked:
            # No more steps
            break
        
        # Wait for step transition
        await asyncio.sleep(0.5)
        await wait_for_dom_stability(page, timeout_ms=5000, stability_ms=300)
        
        step_count += 1
    
    # Navigate back to first step
    for _ in range(step_count):
        if not await click_previous_button(page):
            break
        await asyncio.sleep(0.3)
    
    print(f"✓ Collected fields from {len(visited_steps)} wizard steps")
    
    return all_forms
