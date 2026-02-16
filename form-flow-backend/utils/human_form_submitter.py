"""
human_form_submitter.py - Advanced form submission with human-like behavior

Features:
- Realistic typing speeds with variation
- Mouse movements and hover effects
- Random delays between actions
- Field validation before submission
- Anti-detection techniques
- Error recovery
"""

import asyncio
import random
import logging
from typing import Dict, List, Optional, Tuple
from playwright.async_api import Page, ElementHandle
from playwright.sync_api import Page as SyncPage, ElementHandle as SyncElementHandle
import string
import time

logger = logging.getLogger(__name__)


class HumanFormSubmitter:
    """
    Form submitter that mimics human behavior to avoid detection.
    
    Anti-detection techniques:
    - Variable typing speed (50-200ms per character)
    - Random pauses between fields (500ms-2s)
    - Mouse movements and hovers
    - Realistic focus/blur events
    - Scroll into view before interaction
    - Human-like mistakes and corrections
    """
    
    def __init__(self, page: Page):
        self.page = page
        
        # Human behavior parameters (randomized per session)
        self.typing_speed_base = random.randint(50, 120)  # ms per char
        self.typing_speed_variation = 40  # +/- variation
        self.pause_between_fields = (500, 2000)  # ms range
        self.mistake_probability = 0.05  # 5% chance of typo
        
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # HUMAN BEHAVIOR SIMULATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _human_type(self, element: ElementHandle, text: str, field_name: str = ""):
        """
        Type text with human-like characteristics.
        
        Features:
        - Variable speed per character
        - Occasional typos and corrections
        - Realistic pauses (thinking time)
        """
        await element.click()  # Focus
        await asyncio.sleep(random.uniform(0.1, 0.3))  # Think before typing
        
        for i, char in enumerate(text):
            # Occasional typo (then correct it)
            if random.random() < self.mistake_probability and i > 0:
                # Type wrong character
                wrong_char = random.choice(string.ascii_lowercase)
                await element.press(wrong_char)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                
                # Realize mistake, delete
                await element.press('Backspace')
                await asyncio.sleep(random.uniform(0.05, 0.15))
            
            # Type actual character
            await element.press(char)
            
            # Variable delay per character
            delay = self.typing_speed_base + random.randint(
                -self.typing_speed_variation, 
                self.typing_speed_variation
            )
            await asyncio.sleep(delay / 1000)
            
            # Longer pause at word boundaries (space or punctuation)
            if char in [' ', '.', ',', '!', '?']:
                await asyncio.sleep(random.uniform(0.05, 0.2))
        
        # Brief pause after typing (reading what was typed)
        await asyncio.sleep(random.uniform(0.2, 0.5))
        
        logger.debug(f"✍️  Human-typed '{field_name}': {len(text)} chars")
    
    async def _human_click(self, element: ElementHandle, field_name: str = ""):
        """
        Click with human-like mouse movement.
        
        Features:
        - Hover before click
        - Random click position within element
        - Post-click pause
        """
        # Hover first (humans don't instantly click)
        await element.hover()
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Click (could add random offset within element bounds)
        await element.click()
        await asyncio.sleep(random.uniform(0.05, 0.15))
        
        logger.debug(f"🖱️  Human-clicked '{field_name}'")
    
    async def _scroll_into_view_naturally(self, element: ElementHandle):
        """
        Scroll element into view with human-like smoothness.
        """
        # Get element position
        box = await element.bounding_box()
        if not box:
            return
        
        # Scroll with smooth behavior
        await self.page.evaluate(
            f'window.scrollTo({{top: {box["y"] - 100}, behavior: "smooth"}})'
        )
        
        # Wait for scroll to complete
        await asyncio.sleep(random.uniform(0.3, 0.7))
    
    async def _random_pause(self):
        """Random pause between field interactions (thinking time)"""
        delay = random.uniform(
            self.pause_between_fields[0] / 1000,
            self.pause_between_fields[1] / 1000
        )
        await asyncio.sleep(delay)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FIELD FILLING WITH VALIDATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def fill_field(self, field: Dict, value: str) -> bool:
        """
        Fill a single field with validation and human behavior.
        
        Returns True if successful, False otherwise.
        """
        field_name = field.get('name') or field.get('label', 'unknown')
        field_type = field.get('type', 'text')
        
        try:
            # Find element
            element = await self._find_element(field)
            if not element:
                logger.warning(f"⚠️  Field not found: {field_name}")
                return False
            
            # Scroll into view naturally
            await self._scroll_into_view_naturally(element)
            
            # Random pause before interaction
            await self._random_pause()
            
            # Fill based on type
            success = False
            if field_type in ['text', 'email', 'tel', 'number', 'url']:
                success = await self._fill_text_field(element, value, field_name)
            
            elif field_type == 'textarea':
                success = await self._fill_textarea(element, value, field_name)
            
            elif field_type in ['radio', 'checkbox']:
                success = await self._fill_choice_field(element, value, field_name, field_type)
            
            elif field_type == 'select':
                success = await self._fill_select(element, value, field_name)
            
            elif field_type == 'date':
                success = await self._fill_date_field(element, value, field_name)
            
            else:
                logger.warning(f"⚠️  Unsupported field type: {field_type} for field '{field_name}', attempting generic fill")
                success = await self._fill_text_field(element, value, field_name)
            
            # Validate after filling
            if success:
                actual_value = await self._get_field_value(element, field_type)
                if self._validate_value(value, actual_value, field_type):
                    logger.info(f"✅ {field_name}: '{value}' → '{actual_value}'")
                    return True
                else:
                    logger.error(f"❌ {field_name}: Validation failed! Expected '{value}', got '{actual_value}'")
                    return False
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error filling {field_name}: {e}")
            return False
    
    async def _fill_text_field(self, element: ElementHandle, value: str, field_name: str) -> bool:
        """Fill text input with human typing"""
        try:
            # Clear existing value first
            await element.click(click_count=3)  # Triple-click to select all
            await asyncio.sleep(0.05)
            await element.press('Backspace')
            await asyncio.sleep(0.1)
            
            # Type new value
            await self._human_type(element, str(value), field_name)
            
            # Trigger blur event (like user clicking away)
            await self.page.evaluate('(el) => el.blur()', element)
            
            return True
        except Exception as e:
            logger.error(f"Error filling text field: {e}")
            return False
    
    async def _fill_textarea(self, element: ElementHandle, value: str, field_name: str) -> bool:
        """Fill textarea with human typing and line breaks"""
        try:
            await element.click()
            await asyncio.sleep(0.2)
            
            # Clear first
            await element.fill('')  # Fast clear for long text
            await asyncio.sleep(0.1)
            
            # For short text, type human-like
            if len(value) < 100:
                await self._human_type(element, value, field_name)
            else:
                # For long text, use fill but add pauses
                lines = value.split('\n')
                for i, line in enumerate(lines):
                    await element.type(line)
                    if i < len(lines) - 1:
                        await element.press('Enter')
                        await asyncio.sleep(random.uniform(0.1, 0.3))
            
            await self.page.evaluate('(el) => el.blur()', element)
            return True
        except Exception as e:
            logger.error(f"Error filling textarea: {e}")
            return False
    
    async def _fill_choice_field(self, element: ElementHandle, value: str, field_name: str, field_type: str) -> bool:
        """Fill radio/checkbox with human click"""
        try:
            # Check if already selected
            is_checked = await element.is_checked()
            should_check = str(value).lower() in ['true', 'yes', '1', 'on']
            
            if is_checked != should_check:
                await self._human_click(element, field_name)
            
            return True
        except Exception as e:
            logger.error(f"Error filling choice field: {e}")
            return False
    
    async def _fill_select(self, element: ElementHandle, value: str, field_name: str) -> bool:
        """Fill dropdown with human click and selection"""
        try:
            # Click to open dropdown
            await self._human_click(element, field_name)
            await asyncio.sleep(random.uniform(0.2, 0.5))
            
            # Select option (try by value first, then label)
            try:
                await element.select_option(value=value)
            except:
                await element.select_option(label=value)
            
            await asyncio.sleep(0.1)
            return True
        except Exception as e:
            logger.error(f"Error filling select: {e}")
            return False
    
    async def _fill_date_field(self, element: ElementHandle, value: str, field_name: str) -> bool:
        """Fill date field (format: YYYY-MM-DD)"""
        try:
            await element.click()
            await asyncio.sleep(0.2)
            
            # Use fill for date inputs (typing is complicated)
            await element.fill(value)
            await asyncio.sleep(0.1)
            
            return True
        except Exception as e:
            logger.error(f"Error filling date field: {e}")
            return False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # VALIDATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _get_field_value(self, element: ElementHandle, field_type: str) -> str:
        """Get current value of a field for validation"""
        try:
            if field_type in ['radio', 'checkbox']:
                checked = await element.is_checked()
                return str(checked).lower()
            else:
                return await element.input_value()
        except:
            return ""
    
    def _validate_value(self, expected: str, actual: str, field_type: str) -> bool:
        """Validate that field was filled correctly"""
        # Normalize values
        expected_norm = str(expected).strip().lower()
        actual_norm = str(actual).strip().lower()
        
        # For checkboxes/radios
        if field_type in ['radio', 'checkbox']:
            expected_bool = expected_norm in ['true', 'yes', '1', 'on']
            actual_bool = actual_norm in ['true', 'yes', '1', 'on']
            return expected_bool == actual_bool
        
        # Exact match for most fields
        if expected_norm == actual_norm:
            return True
        
        # Fuzzy match (90% similarity)
        if len(expected_norm) > 0:
            similarity = self._string_similarity(expected_norm, actual_norm)
            if similarity > 0.9:
                logger.warning(f"⚠️  Fuzzy match: '{expected}' ≈ '{actual}' ({similarity:.2%})")
                return True
        
        return False
    
    def _string_similarity(self, a: str, b: str) -> float:
        """Calculate string similarity (simple Levenshtein-based)"""
        if not a or not b:
            return 0.0
        
        # Simple character overlap ratio
        matches = sum(1 for c in a if c in b)
        return matches / max(len(a), len(b))
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ELEMENT FINDING WITH RETRIES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _find_element(self, field: Dict) -> Optional[ElementHandle]:
        """
        Find element using multiple strategies with retries.
        
        Strategies (in order):
        1. By name attribute
        2. By ID
        3. By label (for attribute)
        4. By placeholder
        5. By aria-label
        """
        selectors = []
        name = field.get('name')
        id_ = field.get('id')
        label = field.get('label')
        placeholder = field.get('placeholder')
        
        # Build selector list
        if name:
            selectors.append(f'[name="{name}"]')
        
        if id_:
            selectors.append(f'#{id_}')
        
        if label:
            # Try label association
            selectors.append(f'label:has-text("{label}") + input')
            selectors.append(f'label:has-text("{label}") input')
        
        if placeholder:
            selectors.append(f'[placeholder="{placeholder}"]')
        
        # Try each selector
        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    return element
            except:
                continue
        
        # Wait attempt
        if selectors:
            try:
                element = await self.page.wait_for_selector(selectors[0], state='visible', timeout=1000)
                if element:
                    return element
            except:
                pass
                
        return None
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FORM SUBMISSION WITH PRE-FLIGHT CHECKS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def submit_form(self, form_schema: List[Dict], form_data: Dict[str, str]) -> Tuple[bool, str]:
        """
        Fill and submit form with human-like behavior.
        
        Returns:
            (success: bool, message: str)
        """
        # Flatten form schema to list of fields
        fields = []
        for form_section in form_schema:
            fields.extend(form_section.get('fields', []))
            
        logger.info(f"🤖 Starting human-like form submission ({len(fields)} fields)")
        
        filled_count = 0
        failed_fields = []
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PHASE 1: Fill all fields
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        for field in fields:
            field_name = field.get('name') or field.get('label', 'unknown')
            value = form_data.get(field_name)
            
            if not value:
                logger.debug(f"⏭️  Skipping {field_name} (no value)")
                continue
            
            # Fill field
            success = await self.fill_field(field, value)
            
            if success:
                filled_count += 1
            else:
                failed_fields.append(field_name)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PHASE 2: Pre-submission validation
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if failed_fields:
            logger.warning(f"⚠️  {len(failed_fields)} fields failed: {failed_fields}")
        
        logger.info(f"✅ Filled {filled_count}/{len(fields)} fields")
        
        # Human pause before submitting (reviewing form)
        review_time = random.uniform(1.5, 3.5)
        logger.info(f"👀 Reviewing form for {review_time:.1f}s...")
        await asyncio.sleep(review_time)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PHASE 3: Find and click submit button
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        submit_button = await self._find_submit_button()
        
        if not submit_button:
            return False, "❌ Submit button not found"
        
        # Scroll submit button into view
        await self._scroll_into_view_naturally(submit_button)
        
        # Final pause before submission
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Click submit with human behavior
        logger.info("🚀 Submitting form...")
        await self._human_click(submit_button, "Submit")
        
        # Wait for navigation or confirmation
        try:
            # Wait for either URL change or SUCCESS_INDICATORS
            # This is a bit simplified; real robust checking would be like in submitter.py
            await self.page.wait_for_load_state('networkidle', timeout=10000)
            logger.info("✅ Form submitted successfully (network idle)")
            return True, f"✅ Submitted with {filled_count} fields filled"
        except:
            # Check for validation errors
            errors = await self._check_for_errors()
            if errors:
                return False, f"❌ Validation errors: {errors}"
            else:
                return True, "✅ Submitted (no confirmation detected)"
    
    async def _find_submit_button(self) -> Optional[ElementHandle]:
        """Find submit button using multiple strategies"""
        selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Send")',
            'button:has-text("Continue")',
            'button:has-text("Next")',
            '[role="button"]:has-text("Submit")',
        ]
        
        for selector in selectors:
            try:
                button = await self.page.query_selector(selector)
                if button and await button.is_visible():
                    # Verify it's not disabled
                    is_disabled = await button.is_disabled()
                    if not is_disabled:
                        return button
            except:
                continue
        
        return None
    
    async def _check_for_errors(self) -> List[str]:
        """Check for validation error messages on page"""
        error_selectors = [
            '.error',
            '.error-message',
            '[role="alert"]',
            '.validation-error',
            '.field-error'
        ]
        
        errors = []
        for selector in error_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                for el in elements:
                    if await el.is_visible():
                        text = await el.text_content()
                        if text and len(text.strip()) > 0:
                            errors.append(text.strip())
            except:
                continue
        
        return errors[:5]  # Max 5 errors


class SyncHumanFormSubmitter:
    """
    Synchronous version of HumanFormSubmitter for Windows compatibility.
    """
    
    def __init__(self, page: SyncPage):
        self.page = page
        
        # Human behavior parameters (randomized per session)
        self.typing_speed_base = random.randint(50, 120)  # ms per char
        self.typing_speed_variation = 40  # +/- variation
        self.pause_between_fields = (500, 2000)  # ms range
        self.mistake_probability = 0.05  # 5% chance of typo
        
    def _human_type(self, element: SyncElementHandle, text: str, field_name: str = ""):
        element.click()
        time.sleep(random.uniform(0.1, 0.3))
        
        for i, char in enumerate(text):
            if random.random() < self.mistake_probability and i > 0:
                wrong_char = random.choice(string.ascii_lowercase)
                element.press(wrong_char)
                time.sleep(random.uniform(0.1, 0.3))
                element.press('Backspace')
                time.sleep(random.uniform(0.05, 0.15))
            
            element.press(char)
            delay = self.typing_speed_base + random.randint(-self.typing_speed_variation, self.typing_speed_variation)
            time.sleep(delay / 1000)
            
            if char in [' ', '.', ',', '!', '?']:
                time.sleep(random.uniform(0.05, 0.2))
        
        time.sleep(random.uniform(0.2, 0.5))
        logger.debug(f"✍️  Human-typed '{field_name}': {len(text)} chars")
    
    def _human_click(self, element: SyncElementHandle, field_name: str = ""):
        element.hover()
        time.sleep(random.uniform(0.1, 0.3))
        element.click()
        time.sleep(random.uniform(0.05, 0.15))
        logger.debug(f"🖱️  Human-clicked '{field_name}'")
    
    def _scroll_into_view_naturally(self, element: SyncElementHandle):
        box = element.bounding_box()
        if not box: return
        self.page.evaluate(f'window.scrollTo({{top: {box["y"] - 100}, behavior: "smooth"}})')
        time.sleep(random.uniform(0.3, 0.7))
    
    def _random_pause(self):
        delay = random.uniform(self.pause_between_fields[0] / 1000, self.pause_between_fields[1] / 1000)
        time.sleep(delay)
    
    def fill_field(self, field: Dict, value: str) -> bool:
        field_name = field.get('name') or field.get('label', 'unknown')
        field_type = field.get('type', 'text')
        
        try:
            element = self._find_element(field)
            if not element:
                logger.warning(f"⚠️  Field not found: {field_name}")
                return False
            
            self._scroll_into_view_naturally(element)
            self._random_pause()
            
            success = False
            if field_type in ['text', 'email', 'tel', 'number', 'url']:
                success = self._fill_text_field(element, value, field_name)
            elif field_type == 'textarea':
                success = self._fill_textarea(element, value, field_name)
            elif field_type in ['radio', 'checkbox']:
                success = self._fill_choice_field(element, value, field_name, field_type)
            elif field_type == 'select':
                success = self._fill_select(element, value, field_name)
            elif field_type == 'date':  # Added missing date handler
                success = self._fill_date_field(element, value, field_name)
            else:
                success = self._fill_text_field(element, value, field_name)
            
            if success:
                actual_value = self._get_field_value(element, field_type)
                if self._validate_value(value, actual_value, field_type):
                    return True
                return False
            return success
        except Exception as e:
            logger.error(f"❌ Error filling {field_name}: {e}")
            return False

    def _fill_text_field(self, element: SyncElementHandle, value: str, field_name: str) -> bool:
        try:
            element.click(click_count=3)
            time.sleep(0.05)
            element.press('Backspace')
            time.sleep(0.1)
            self._human_type(element, str(value), field_name)
            self.page.evaluate('(el) => el.blur()', element)
            return True
        except: return False

    def _fill_textarea(self, element: SyncElementHandle, value: str, field_name: str) -> bool:
        try:
            element.click()
            time.sleep(0.2)
            element.fill('')
            time.sleep(0.1)
            if len(value) < 100:
                self._human_type(element, value, field_name)
            else:
                lines = value.split('\n')
                for i, line in enumerate(lines):
                    element.type(line)
                    if i < len(lines) - 1:
                        element.press('Enter')
                        time.sleep(random.uniform(0.1, 0.3))
            self.page.evaluate('(el) => el.blur()', element)
            return True
        except: return False

    def _fill_choice_field(self, element: SyncElementHandle, value: str, field_name: str, field_type: str) -> bool:
        try:
            is_checked = element.is_checked()
            should_check = str(value).lower() in ['true', 'yes', '1', 'on']
            if is_checked != should_check:
                self._human_click(element, field_name)
            return True
        except: return False

    def _fill_select(self, element: SyncElementHandle, value: str, field_name: str) -> bool:
        try:
            self._human_click(element, field_name)
            time.sleep(random.uniform(0.2, 0.5))
            try: element.select_option(value=value)
            except: element.select_option(label=value)
            time.sleep(0.1)
            return True
        except: return False
        
    def _fill_date_field(self, element: SyncElementHandle, value: str, field_name: str) -> bool:
        try:
            element.click()
            time.sleep(0.2)
            element.fill(value)
            time.sleep(0.1)
            return True
        except: return False

    def _get_field_value(self, element: SyncElementHandle, field_type: str) -> str:
        try:
            if field_type in ['radio', 'checkbox']:
                return str(element.is_checked()).lower()
            return element.input_value()
        except: return ""

    def _validate_value(self, expected: str, actual: str, field_type: str) -> bool:
        expected_norm = str(expected).strip().lower()
        actual_norm = str(actual).strip().lower()
        if field_type in ['radio', 'checkbox']:
            return (expected_norm in ['true', 'yes', '1', 'on']) == (actual_norm in ['true', 'yes', '1', 'on'])
        if expected_norm == actual_norm: return True
        if len(expected_norm) > 0 and self._string_similarity(expected_norm, actual_norm) > 0.9: return True
        return False

    def _string_similarity(self, a: str, b: str) -> float:
        if not a or not b: return 0.0
        matches = sum(1 for c in a if c in b)
        return matches / max(len(a), len(b))

    def _find_element(self, field: Dict) -> Optional[SyncElementHandle]:
        selectors = []
        name = field.get('name')
        if name: selectors.append(f'[name="{name}"]')
        id_ = field.get('id')
        if id_: selectors.append(f'#{id_}')
        label = field.get('label')
        if label:
            selectors.append(f'label:has-text("{label}") + input')
            selectors.append(f'label:has-text("{label}") input')
        placeholder = field.get('placeholder')
        if placeholder: selectors.append(f'[placeholder="{placeholder}"]')
        
        for selector in selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible(): return element
            except: continue
        
        if selectors:
            try:
                element = self.page.wait_for_selector(selectors[0], state='visible', timeout=1000)
                if element: return element
            except: pass
        return None

    def submit_form(self, form_schema: List[Dict], form_data: Dict[str, str]) -> Tuple[bool, str]:
        fields = []
        for form_section in form_schema:
            fields.extend(form_section.get('fields', []))
            
        logger.info(f"🤖 Starting SYNC human-like form submission ({len(fields)} fields)")
        filled_count = 0
        failed_fields = []
        
        for field in fields:
            field_name = field.get('name') or field.get('label', 'unknown')
            value = form_data.get(field_name)
            if not value: continue
            if self.fill_field(field, value): filled_count += 1
            else: failed_fields.append(field_name)
            
        logger.info(f"✅ Filled {filled_count}/{len(fields)} fields")
        review_time = random.uniform(1.5, 3.5)
        time.sleep(review_time)
        
        submit_button = self._find_submit_button()
        if not submit_button: return False, "❌ Submit button not found"
        
        self._scroll_into_view_naturally(submit_button)
        time.sleep(random.uniform(0.5, 1.5))
        
        logger.info("🚀 Submitting form...")
        self._human_click(submit_button, "Submit")
        
        try:
            self.page.wait_for_load_state('networkidle', timeout=10000)
            logger.info("✅ Form submitted successfully (network idle)")
            return True, f"✅ Submitted with {filled_count} fields filled"
        except:
            errors = self._check_for_errors()
            if errors: return False, f"❌ Validation errors: {errors}"
            return True, "✅ Submitted (no confirmation detected)"

    def _find_submit_button(self) -> Optional[SyncElementHandle]:
        selectors = ['button[type="submit"]', 'input[type="submit"]', 'button:has-text("Submit")', 'button:has-text("Send")', '[role="button"]:has-text("Submit")']
        for selector in selectors:
            try:
                button = self.page.query_selector(selector)
                if button and button.is_visible() and not button.is_disabled(): return button
            except: continue
        return None

    def _check_for_errors(self) -> List[str]:
        error_selectors = ['.error', '.error-message', '[role="alert"]', '.validation-error', '.field-error']
        errors = []
        for selector in error_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                for el in elements:
                    if el.is_visible():
                        text = el.text_content()
                        if text and len(text.strip()) > 0: errors.append(text.strip())
            except: continue
        return errors[:5]
