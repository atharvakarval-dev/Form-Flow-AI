import asyncio
from typing import Dict, List, Any, Optional
import time
import os
import random
import sys
from urllib.parse import urlparse

# Import browser pool for memory-efficient browser reuse
from .browser_pool import get_browser_context

# Import CAPTCHA detection and solving
from .detectors.captcha import detect_captcha
from .utils.constants import CAPTCHA_SELECTORS
from services.captcha.solver import CaptchaSolverService, get_captcha_solver
from utils.logging import get_logger

logger = get_logger(__name__)





class FormSubmitter:
    """Optimized form submission handler with Playwright automation."""
    
    # Class constants for selector patterns
    TEXT_TYPES = {'text', 'email', 'tel', 'password', 'number', 'url', 'search', 'textarea'}
    DATE_TYPES = {'date', 'datetime-local', 'time', 'month', 'week'}
    
    SUBMIT_SELECTORS = [
        "button[type='submit']", "input[type='submit']",
        "button:has-text('Submit')", "button:has-text('Send')",
        "button:has-text('Submit Form')", "button:has-text('Send Form')",
        "input[value*='Submit']", "input[value*='Send']",
        "[role='button']:has-text('Submit')", "[role='button']:has-text('Send')",
        ".submit-btn", ".btn-submit", "#submit", "[data-submit]", "[onclick*='submit']"
    ]
    
    GOOGLE_SUBMIT_SELECTORS = [
        "[role='button']:has-text('Submit')", "div[role='button']:has-text('Submit')",
        ".freebirdFormviewerViewNavigationSubmitButton", "[jsname='M2UYVd']",
        "span:has-text('Submit')", "div:has-text('Submit')"
    ]
    
    SUCCESS_INDICATORS = [
        "thank you", "thankyou", "success", "submitted", "received", "confirmation",
        "complete", "your response has been recorded", "form submitted", "response recorded",
        "verify", "verification", "check your email", "email sent", "login", "sign in",
        "dashboard", "click here to login", "account created", "welcome"
    ]
    
    ERROR_INDICATORS = [
        "error", "invalid", "required field", "missing", "failed",
        "please fill", "this field is required", "must be", "correct the errors"
    ]
    
    # Field types that can trigger visibility of other fields
    TRIGGER_TYPES = {'radio', 'checkbox', 'select', 'dropdown'}

    def __init__(self):
        self.session_timeout = 30000
        self.debug_screenshots = []
        self._detected_dynamic_fields: List[Dict[str, Any]] = []  # Track newly appeared fields
    
    def _find_field_in_schema(self, name: str, field_map: Dict[str, Dict]) -> Optional[Dict]:
        """
        Find field with fuzzy matching on name/label/id.
        
        Handles cases where form_data keys don't exactly match schema field names,
        especially for Angular Material / React MUI forms with auto-generated IDs.
        """
        # 1. Exact match first
        if name in field_map:
            logger.debug(f"[MATCH] Exact match for '{name}'")
            return field_map[name]
        
        # 2. Match by field ID (critical for Angular Material / auto-generated IDs like mat-input-2)
        for field_name, field_info in field_map.items():
            field_id = field_info.get('id')
            if field_id == name:
                logger.debug(f"[MATCH] ID match: '{name}' == field.id for '{field_name}'")
                return field_info
        
        # 3. Normalize and try fuzzy match on name
        name_lower = name.lower().replace('_', '').replace('-', '').replace(' ', '')
        
        for field_name, field_info in field_map.items():
            field_normalized = field_name.lower().replace('_', '').replace('-', '').replace(' ', '')
            if field_normalized == name_lower:
                logger.debug(f"[MATCH] Normalized name match: '{name}' ~= '{field_name}'")
                return field_info
        
        # 4. Try match on label
        for field_name, field_info in field_map.items():
            label = (field_info.get('label') or field_info.get('display_name') or '').lower()
            label_normalized = label.replace('_', '').replace('-', '').replace(' ', '')
            if label_normalized == name_lower or name_lower in label_normalized or label_normalized in name_lower:
                logger.debug(f"[MATCH] Label match: '{name}' ~= label '{label}' for '{field_name}'")
                return field_info
        
        # 5. Partial match on name (for cases like "fullName" vs "full_name")
        for field_name, field_info in field_map.items():
            field_normalized = field_name.lower().replace('_', '').replace('-', '').replace(' ', '')
            if name_lower in field_normalized or field_normalized in name_lower:
                logger.debug(f"[MATCH] Partial name match: '{name}' partial '{field_name}'")
                return field_info
        
        # NO MATCH - log available fields for debugging
        logger.warning(f"[NO MATCH] Could not find field '{name}' in schema. Available: {list(field_map.keys())[:10]}")
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # DYNAMIC FIELD DETECTION
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _get_visible_fields_snapshot(self, page) -> Dict[str, Dict[str, Any]]:
        """
        Capture snapshot of all currently visible form fields.
        Returns dict: { "field_id_or_name": { name, id, type, label, visible } }
        """
        return await page.evaluate("""
            () => {
                const snapshot = {};
                const inputs = document.querySelectorAll('input, select, textarea');
                
                inputs.forEach(el => {
                    // Skip hidden/disabled inputs
                    if (el.type === 'hidden' || el.disabled) return;
                    
                    // Check visibility (offsetParent is null for hidden elements)
                    const isVisible = el.offsetParent !== null || 
                                      getComputedStyle(el).display !== 'none';
                    if (!isVisible) return;
                    
                    const name = el.name || el.id || '';
                    if (!name) return;
                    
                    // Find associated label
                    let label = '';
                    if (el.labels && el.labels.length > 0) {
                        label = el.labels[0].textContent.trim();
                    } else {
                        // Look for nearby label
                        const wrapper = el.closest('.form-group, .form-field, label, div');
                        if (wrapper) {
                            const labelEl = wrapper.querySelector('label');
                            if (labelEl) label = labelEl.textContent.trim();
                        }
                    }
                    
                    snapshot[name] = {
                        name: name,
                        id: el.id || '',
                        type: el.type || el.tagName.toLowerCase(),
                        label: label,
                        tagName: el.tagName.toLowerCase()
                    };
                });
                
                return snapshot;
            }
        """)

    async def _detect_new_fields(
        self, 
        before_snapshot: Dict[str, Any], 
        after_snapshot: Dict[str, Any],
        form_data_keys: set
    ) -> List[Dict[str, Any]]:
        """
        Compare snapshots and return list of newly visible fields
        that are NOT already in the form_data.
        """
        new_fields = []
        
        for name, info in after_snapshot.items():
            if name not in before_snapshot:
                # This field appeared after interaction
                if name not in form_data_keys:
                    # We don't have data for this field!
                    new_fields.append({
                        'name': name,
                        'id': info.get('id', ''),
                        'type': info.get('type', 'text'),
                        'label': info.get('label', name),
                        'is_dynamic': True
                    })
                    print(f"🆕 Dynamic field detected: {name} ({info.get('label', 'No label')})")
        
        return new_fields
    
    def _get_selectors(self, field_info: Dict) -> List[str]:
        """Build prioritized CSS selectors for a field."""
        selectors = []
        fid, fname, placeholder = field_info.get('id', ''), field_info.get('name', ''), field_info.get('placeholder', '')
        
        if fid:
            selectors.extend([f"#{fid}", f"input#{fid}", f"textarea#{fid}", f"select#{fid}"])
        if fname:
            selectors.extend([f"[name='{fname}']", f"input[name='{fname}']", f"select[name='{fname}']", f"textarea[name='{fname}']", f'[name="{fname}"]'])
        if placeholder:
            selectors.extend([f"input[placeholder*='{placeholder[:20]}']", f"textarea[placeholder*='{placeholder[:20]}']"])
        return selectors

    async def _find_element(self, page, selectors: List[str], visible_only: bool = True):
        """Find first matching visible element from selectors list."""
        for selector in selectors:
            try:
                el = await page.query_selector(selector)
                if el and (not visible_only or await el.is_visible()):
                    return el
            except:
                continue
        return None

    async def _find_by_label(self, page, label_text: str):
        """Find input associated with a label."""
        try:
            labels = await page.query_selector_all(f"label:has-text('{label_text}')")
            for label in labels:
                label_for = await label.get_attribute('for')
                if label_for:
                    el = await page.query_selector(f"#{label_for}")
                    if el and await el.is_visible():
                        return el
        except:
            logger.debug(f"Label search failed for '{label_text}'", exc_info=True)
            pass
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # CORE FIELD HANDLERS
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _fill_text(self, element, value: str) -> bool:
        """Universal handler for text-like inputs."""
        await element.click()
        await asyncio.sleep(0.1)
        # Disable browser autocomplete to prevent autofill interference
        try:
            await element.evaluate('(el) => el.setAttribute("autocomplete", "off")')
        except:
            pass  # Continue even if attribute setting fails
        await element.fill('')
        await element.fill(value)
        await asyncio.sleep(0.2)
        return True

    async def _fill_dropdown(self, page, element, value: str, field_info: Dict) -> bool:
        """Unified dropdown handler with multiple strategies."""
        
        # Strategy 1 & 2: Standard <select> element
        strategies = [
            lambda: element.select_option(value=value),
            lambda: element.select_option(label=value),
        ]
        
        for strategy in strategies:
            try:
                await strategy()
                await asyncio.sleep(0.2)
                return True
            except:
                continue
        
        # Strategy 3: Smart text match on standard <select> options
        # Priority: exact match > starts with > shortest partial match
        try:
            options = await element.query_selector_all('option')
            matches = []  # (priority, text, val_or_text)
            value_lower = value.lower().strip()
            
            for opt in options:
                text, val = await opt.inner_text(), await opt.get_attribute('value')
                text_lower = text.lower().strip()
                val_lower = (val or '').lower().strip()
                
                # Priority 1: Exact match (case-insensitive)
                if value_lower == text_lower or value_lower == val_lower:
                    matches.append((0, len(text), text, val or text))
                # Priority 2: Starts with
                elif text_lower.startswith(value_lower) or val_lower.startswith(value_lower):
                    matches.append((1, len(text), text, val or text))
                # Priority 3: Partial match (prefer shorter options - less ambiguous)
                elif value_lower in text_lower or value_lower in val_lower:
                    matches.append((2, len(text), text, val or text))
            
            if matches:
                # Sort by priority, then by length (shorter = better match)
                matches.sort(key=lambda x: (x[0], x[1]))
                best_match = matches[0]
                await element.select_option(value=best_match[3])
                return True
        except:
            logger.debug(f"Smart text match failed for '{value}'")
            pass
        
        # Strategy 4: Ant Design / React Select / Custom dropdowns
        # These require clicking to open, then clicking the option
        try:
            label = field_info.get('label', '') or field_info.get('display_name', '')
            
            # Find the Ant Design select container by label
            ant_select = None
            if label:
                ant_select = await page.query_selector(f'.ant-form-item:has-text("{label}") .ant-select')
            if not ant_select:
                ant_select = await page.query_selector(f'.ant-select:has(.ant-select-selection-placeholder:has-text("{label}"))')
            if not ant_select:
                # Try finding by field name or nearby the element
                ant_select = await element.query_selector('xpath=ancestor::*[contains(@class, "ant-form-item")]//div[contains(@class, "ant-select")]')
            
            if ant_select:
                # Click to open dropdown
                await ant_select.click()
                await asyncio.sleep(0.5)
                
                # Try to find and click the matching option
                option_selectors = [
                    f'.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option[title="{value}"]',
                    f'.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item:has-text("{value}")',
                    f'.ant-select-dropdown:not(.ant-select-dropdown-hidden) [role="option"]:has-text("{value}")',
                    f'.rc-virtual-list-holder-inner .ant-select-item:has-text("{value}")',
                ]
                
                for sel in option_selectors:
                    opt = await page.query_selector(sel)
                    if opt:
                        await opt.click()
                        await asyncio.sleep(0.3)
                        print(f"   ✓ Selected Ant Design dropdown option: {value}")
                        return True
                
                # Fallback: Smart match (prefer exact > starts with > shortest partial)
                options = await page.query_selector_all('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option')
                matches = []
                value_lower = value.lower().strip()
                
                for opt in options:
                    opt_text = await opt.inner_text()
                    opt_text_lower = opt_text.lower().strip()
                    
                    if value_lower == opt_text_lower:
                        matches.append((0, len(opt_text), opt, opt_text))
                    elif opt_text_lower.startswith(value_lower):
                        matches.append((1, len(opt_text), opt, opt_text))
                    elif value_lower in opt_text_lower:
                        matches.append((2, len(opt_text), opt, opt_text))
                
                if matches:
                    matches.sort(key=lambda x: (x[0], x[1]))
                    best = matches[0]
                    await best[2].click()
                    await asyncio.sleep(0.3)
                    print(f"   ✓ Selected Ant Design dropdown option: {best[3]}")
                    return True
                
                # Close dropdown if no option found
                await page.keyboard.press('Escape')
        except Exception as e:
            print(f"   ⚠️ Ant Design dropdown error: {e}")
        
        # Strategy 5: Generic click and select (other custom dropdowns)
        try:
            await element.click()
            await asyncio.sleep(0.3)
            for opt_sel in [f"option:has-text('{value[:30]}')", f"[role='option']:has-text('{value[:30]}')", f"li:has-text('{value[:30]}')'"]:
                opt = await page.query_selector(opt_sel)
                if opt:
                    await opt.click()
                    return True
        except:
            logger.warning(f"All dropdown strategies failed for '{value}'")
            pass
        
        return False

    async def _fill_radio(self, page, field_name: str, value: str) -> bool:
        """Handle radio button selection."""
        radios = await page.query_selector_all(f"input[name='{field_name}'][type='radio']")
        for radio in radios:
            radio_val = await radio.get_attribute('value') or ''
            if radio_val.lower() == value.lower() or value.lower() in radio_val.lower() or radio_val.lower() in value.lower():
                await radio.click()
                await asyncio.sleep(0.2)
                return True
        return False

    async def _fill_checkbox(self, element, value: str) -> bool:
        """Handle checkbox state."""
        should_check = str(value).lower() in ['true', 'yes', '1', 'checked', 'on']
        is_checked = await element.is_checked()
        if should_check and not is_checked:
            await element.check()
        elif not should_check and is_checked:
            await element.uncheck()
        await asyncio.sleep(0.2)
        return True

    async def _fill_file(self, element, value) -> bool:
        """Handle file upload."""
        files = value if isinstance(value, list) else [value]
        valid_files = [f for f in files if os.path.exists(f)]
        if valid_files:
            await element.set_input_files(valid_files)
            await asyncio.sleep(0.5)
            print(f"✅ Uploaded {len(valid_files)} file(s)")
            return True
        print(f"⚠️ No valid files found")
        return False

    async def _fill_range(self, page, element, value: str) -> bool:
        """Handle range/slider input."""
        try:
            min_v, max_v = float(await element.get_attribute('min') or 0), float(await element.get_attribute('max') or 100)
            target = max(min_v, min(max_v, float(value)))
            await page.evaluate(f"(el) => {{ el.value = {target}; el.dispatchEvent(new Event('input', {{bubbles: true}})); el.dispatchEvent(new Event('change', {{bubbles: true}})); }}", element)
            return True
        except:
            return False

    async def _fill_with_js(self, page, field_name: str, value: str) -> bool:
        """Fallback: Fill via JavaScript injection."""
        try:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")
            return await page.evaluate(f"""
                () => {{
                    const selectors = ['[name="{field_name}"]', '#{field_name}', '[id="{field_name}"]', 'input[name="{field_name}"]', 'textarea[name="{field_name}"]'];
                    for (const sel of selectors) {{
                        const el = document.querySelector(sel);
                        if (el) {{
                            el.value = "{escaped}";
                            el.dispatchEvent(new Event('input', {{bubbles: true}}));
                            el.dispatchEvent(new Event('change', {{bubbles: true}}));
                            return true;
                        }}
                    }}
                    return false;
                }}
            """)
        except:
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN FIELD FILLING LOGIC
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _fill_field(self, page, field_info: Dict, value: str, attempt: int = 0) -> bool:
        """Fill a form field based on its type."""
        fname, ftype = field_info.get('name', ''), field_info.get('type', 'text')
        
        # Build selectors and find element
        selectors = self._get_selectors(field_info)
        label = field_info.get('label') or field_info.get('display_name')
        
        element = await self._find_element(page, selectors)
        if not element and label:
            element = await self._find_by_label(page, label)
        
        # Special case: Custom dropdowns (Ant Design, React Select) may not have standard elements
        if not element and ftype in ('select', 'dropdown'):
            # Try to find and fill Ant Design dropdown directly
            return await self._fill_ant_design_dropdown(page, label or fname, value, field_info)
        
        if not element:
            return await self._fill_with_js(page, fname, value) if attempt >= 2 else False
        
        await element.scroll_into_view_if_needed()
        await asyncio.sleep(0.2)
        
        # Route to appropriate handler
        if ftype in self.TEXT_TYPES:
            return await self._fill_text(element, value)
        elif ftype in ('select', 'dropdown'):
            return await self._fill_dropdown(page, element, value, field_info)
        elif ftype == 'radio':
            return await self._fill_radio(page, fname, value)
        elif ftype in ('checkbox', 'checkbox-group'):
            return await self._fill_checkbox(element, value)
        elif ftype == 'file':
            return await self._fill_file(element, value)
        elif ftype in self.DATE_TYPES:
            return await self._fill_text(element, value)
        elif ftype == 'range':
            return await self._fill_range(page, element, value)
        elif ftype == 'scale':
            return await self._fill_radio(page, fname, str(value))
        elif ftype == 'color':
            await element.fill(value)
            return True
        
        return False
    
    async def _fill_ant_design_dropdown(self, page, label: str, value: str, field_info: Dict) -> bool:
        """Fill Ant Design dropdown directly by label."""
        try:
            # Try to find the dropdown container
            ant_select = None
            if label:
                # Look for Ant Design form item containing this label
                ant_select = await page.query_selector(f'.ant-form-item:has-text("{label}") .ant-select')
                
            if not ant_select:
                ant_select = await page.query_selector(f'.ant-select:has(.ant-select-selection-placeholder:has-text("{label}"))')
            
            if not ant_select:
                # Try any visible ant-select
                selects = await page.query_selector_all('.ant-select:visible')
                for sel in selects:
                    sel_text = await sel.inner_text()
                    if label.lower() in sel_text.lower() or "select" in sel_text.lower():
                        ant_select = sel
                        break
            
            if ant_select:
                # Scroll into view
                await ant_select.scroll_into_view_if_needed()
                await asyncio.sleep(0.2)
                
                # Click to open dropdown
                await ant_select.click()
                await asyncio.sleep(0.5)
                
                # Find and click the option
                option_selectors = [
                    f'.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option[title="{value}"]',
                    f'.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item:has-text("{value}")',
                    f'.ant-select-dropdown:not(.ant-select-dropdown-hidden) [role="option"]:has-text("{value}")',
                    f'.rc-virtual-list-holder-inner .ant-select-item:has-text("{value}")',
                ]
                
                for sel in option_selectors:
                    opt = await page.query_selector(sel)
                    if opt:
                        await opt.click()
                        await asyncio.sleep(0.3)
                        print(f"   ✓ Selected Ant Design dropdown: {label} = {value}")
                        return True
                
                # Fallback: Smart match (prefer exact > starts with > shortest partial)
                options = await page.query_selector_all('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option')
                matches = []
                value_lower = value.lower().strip()
                
                for opt in options:
                    opt_text = await opt.inner_text()
                    opt_text_lower = opt_text.lower().strip()
                    
                    if value_lower == opt_text_lower:
                        matches.append((0, len(opt_text), opt, opt_text))
                    elif opt_text_lower.startswith(value_lower):
                        matches.append((1, len(opt_text), opt, opt_text))
                    elif value_lower in opt_text_lower:
                        matches.append((2, len(opt_text), opt, opt_text))
                
                if matches:
                    matches.sort(key=lambda x: (x[0], x[1]))
                    best = matches[0]
                    await best[2].click()
                    await asyncio.sleep(0.3)
                    print(f"   ✓ Selected Ant Design dropdown: {label} = {best[3]}")
                    return True
                
                # Close dropdown
                await page.keyboard.press('Escape')
                
        except Exception as e:
            print(f"   ⚠️ Ant Design dropdown fill error: {e}")
        
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # GOOGLE FORMS HANDLING
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _find_google_question(self, page, display_name: str):
        """Find a Google Forms question by display name."""
        questions = await page.query_selector_all('[role="listitem"]')
        for q in questions:
            text = await q.inner_text()
            if display_name[:20].lower() in text.lower():
                return q
        return None

    async def _fill_google_form_field(self, page, field_info: Dict, value: str, attempt: int = 0) -> bool:
        """Fill Google Form field with specialized handling."""
        ftype, display_name = field_info.get('type', 'text'), field_info.get('display_name', '')
        
        try:
            if ftype in self.TEXT_TYPES:
                question = await self._find_google_question(page, display_name)
                if question:
                    inp = await question.query_selector('input, textarea')
                    if inp:
                        return await self._fill_text(inp, value)
                
                # Fallback to aria-label selectors
                for sel in [f"input[aria-label*='{display_name[:30]}']", f"textarea[aria-label*='{display_name[:30]}']"]:
                    el = await page.query_selector(sel)
                    if el:
                        return await self._fill_text(el, value)
            
            elif ftype in ('radio', 'mcq'):
                for opt in field_info.get('options', []):
                    opt_label = opt.get('label', opt.get('value', ''))
                    if value.lower() in opt_label.lower() or opt_label.lower() in value.lower():
                        radio = await page.query_selector(f"[role='radio'][aria-label*='{opt_label[:30]}']")
                        if radio:
                            await radio.scroll_into_view_if_needed()
                            await radio.click()
                            await asyncio.sleep(0.3)
                            return True
            
            elif ftype == 'dropdown':
                dropdown = await page.query_selector(f"[role='listbox'][aria-label*='{display_name[:30]}']") or \
                           await page.query_selector("[role='button'][aria-haspopup='listbox']")
                if dropdown:
                    await dropdown.click()
                    await asyncio.sleep(0.5)
                    for opt in field_info.get('options', []):
                        opt_label = opt.get('label', opt.get('value', ''))
                        if value.lower() in opt_label.lower():
                            opt_el = await page.query_selector(f"[role='option']:has-text('{opt_label[:30]}')")
                            if opt_el:
                                await opt_el.click()
                                return True
            
            elif ftype == 'checkbox-group':
                selected = value if isinstance(value, list) else [value]
                for opt in field_info.get('options', []):
                    opt_label = opt.get('label', opt.get('value', ''))
                    should_check = any(v.lower() in opt_label.lower() for v in selected)
                    cb = await page.query_selector(f"[role='checkbox'][aria-label*='{opt_label[:30]}']")
                    if cb:
                        is_checked = await cb.get_attribute('aria-checked') == 'true'
                        if should_check != is_checked:
                            await cb.scroll_into_view_if_needed()
                            await cb.click()
                            await asyncio.sleep(0.2)
                return True
            
            elif ftype == 'scale':
                question = await self._find_google_question(page, display_name)
                if question:
                    radios = await question.query_selector_all('[role="radio"]')
                    for radio in radios:
                        label = await radio.get_attribute('aria-label') or ''
                        if str(value) in label:
                            await radio.click()
                            return True
            
            elif ftype == 'grid' and isinstance(value, dict):
                question = await self._find_google_question(page, display_name)
                if question:
                    rows = await question.query_selector_all('[role="group"]')
                    for row in rows:
                        row_text = await row.inner_text()
                        for row_label, col_val in value.items():
                            if row_label.lower() in row_text.lower():
                                opts = await row.query_selector_all('[role="radio"], [role="checkbox"]')
                                for opt in opts:
                                    opt_label = await opt.get_attribute('aria-label') or ''
                                    if col_val.lower() in opt_label.lower():
                                        await opt.click()
                                        break
                    return True
            
            elif ftype in self.DATE_TYPES:
                question = await self._find_google_question(page, display_name)
                if question:
                    inp = await question.query_selector('input[type="date"], input[type="time"], input[type="text"]')
                    if inp:
                        return await self._fill_text(inp, value)
            
            elif ftype == 'file':
                print(f"⚠️ Google Forms file upload requires OAuth - skipping")
                return False
                
        except Exception as e:
            print(f"Error filling Google Form field: {e}")
        
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # FORM SUBMISSION
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _submit_form(self, page, form_schema: List[Dict]) -> bool:
        """Find and click submit button."""
        selectors = []
        
        # Priority: Schema-defined submit buttons
        for form in form_schema:
            for field in form.get('fields', []):
                if field.get('type') == 'submit':
                    if fid := field.get('id'):
                        selectors.append(f"#{fid}")
                    if fname := field.get('name'):
                        selectors.append(f"[name='{fname}']")
        
        selectors.extend(self.SUBMIT_SELECTORS)
        
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible() and await el.is_enabled():
                    await el.scroll_into_view_if_needed()
                    await asyncio.sleep(0.3)
                    await el.click()
                    try:
                        await page.wait_for_load_state('networkidle', timeout=15000)
                    except:
                        await asyncio.sleep(2)
                    return True
            except:
                continue
        
        # Fallback: Press Enter on form
        try:
            form = await page.query_selector('form')
            if form:
                await form.press('Enter')
                await asyncio.sleep(2)
                return True
        except:
            logger.warning("Form submit fallback (Enter key) failed", exc_info=True)
            pass
        return False

    async def _submit_google_form(self, page) -> bool:
        """Submit Google Form."""
        for sel in self.GOOGLE_SUBMIT_SELECTORS:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    await el.scroll_into_view_if_needed()
                    await el.click()
                    await asyncio.sleep(3)
                    return True
            except:
                continue
        
        # Fallback: aria-label
        try:
            buttons = await page.query_selector_all("[role='button']")
            for btn in buttons:
                aria = await btn.get_attribute('aria-label')
                if aria and 'submit' in aria.lower():
                    await btn.click()
                    await asyncio.sleep(3)
                    return True
        except:
            logger.warning("Google Form submit fallback failed", exc_info=True)
            pass
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # AUTO-CHECK TERMS CHECKBOXES
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _auto_check_terms(self, page) -> int:
        """
        Auto-check 'Terms/Privacy' checkboxes (required for submission).
        Explicitly skip 'Subscribe/Newsletter' checkboxes (optional).
        """
        return await page.evaluate("""
            () => {
                let count = 0;
                // Terms to positive check
                const consentKeywords = ['terms', 'privacy', 'agree', 'accept', 'consent', 'policy', 'tos', 'gdpr', 'conditions'];
                // Terms to avoid/skip
                const marketingKeywords = ['subscribe', 'newsletter', 'marketing', 'update', 'offer', 'promotion'];

                const isMarketing = (text) => marketingKeywords.some(k => text.includes(k));
                const isConsent = (text) => consentKeywords.some(k => text.includes(k));

                document.querySelectorAll('input[type="checkbox"]:not(:checked):not(:disabled)').forEach(cb => {
                    const text = (cb.name + cb.id + (cb.labels?.[0]?.textContent || '') + (cb.closest('label,div')?.textContent || '')).toLowerCase();
                    
                    // If it looks like marketing -> SKIP
                    if (isMarketing(text)) {
                         return; 
                    }

                    // If it looks like required consent -> CHECK
                    if (isConsent(text)) {
                        cb.checked = true;
                        cb.dispatchEvent(new Event('change', {bubbles: true}));
                        count++;
                    }
                });
                
                // Handle Angular/Material checkboxes
                document.querySelectorAll('mat-checkbox:not(.mat-checkbox-checked)').forEach(m => {
                    const text = (m.textContent || '').toLowerCase();
                    if (!isMarketing(text) && isConsent(text)) {
                        (m.querySelector('label') || m).click();
                        count++;
                    }
                });
                return count;
            }
        """)

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN FILL & SUBMIT WORKFLOW
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _fill_and_submit_form(self, page, form_data: Dict[str, str], form_schema: List[Dict], is_google_form: bool = False) -> Dict[str, Any]:
        """Fill form fields and submit. Detects dynamic fields that appear during filling."""
        filled, errors = [], []
        self._detected_dynamic_fields = []  # Reset for this run
        form_data_keys = set(form_data.keys())
        
        # Build field mapping
        field_map = {f.get('name', ''): f for form in form_schema for f in form.get('fields', [])}
        
        # --- DYNAMIC FIELD DETECTION: Initial Snapshot ---
        try:
            initial_snapshot = await self._get_visible_fields_snapshot(page)
            print(f"📸 Initial snapshot: {len(initial_snapshot)} visible fields")
        except Exception as e:
            print(f"⚠️ Snapshot failed: {e}")
            initial_snapshot = {}
        
        # Find password for confirmation fields
        password_val = next((v for k, v in form_data.items() 
                            if 'password' in k.lower() and not any(x in k.lower() for x in ['confirm', 'verify', 'retype', 'cpass'])), '')
        
        def is_confirm_field(name, label):
            combined = (name + (label or '')).lower()
            return any(k in combined for k in ['confirm', 'verify', 'retype', 'repeat', 'cpass', 'cpassword']) and 'password' in combined
        
        # Build fields to process
        fields_to_process, processed = [], set()
        for name, value in form_data.items():
            field_info = field_map.get(name, {})
            label = field_info.get('label') or field_info.get('display_name', '')
            final_val = password_val if is_confirm_field(name, label) and password_val else value
            fields_to_process.append((name, final_val))
            processed.add(name)
        
        # Add missing confirm fields from schema
        for name, info in field_map.items():
            if name not in processed:
                label = info.get('label', '')
                if is_confirm_field(name, label) and password_val:
                    fields_to_process.append((name, password_val))
        
        # Track current snapshot for delta detection
        current_snapshot = initial_snapshot.copy()
        
        # Fill each field with retry
        for name, value in fields_to_process:
            field_info = self._find_field_in_schema(name, field_map)
            if not field_info:
                logger.debug(f"Field not found in schema: {name}")
                continue
            ftype = field_info.get('type', 'text')
            success = False
            
            for attempt in range(3):
                try:
                    success = await (self._fill_google_form_field if is_google_form else self._fill_field)(page, field_info, value, attempt)
                    if success and await self._verify_field(page, field_info, value):
                        filled.append(name)
                        break
                except Exception as e:
                    if attempt == 2:
                        errors.append(f"Error filling {name}: {e}")
                await asyncio.sleep(0.5)
            
            if not success:
                errors.append(f"Failed to fill: {name}")
            
            # --- DYNAMIC FIELD DETECTION: Check after trigger fields ---
            if success and ftype in self.TRIGGER_TYPES:
                try:
                    await asyncio.sleep(0.3)  # Wait for DOM update
                    new_snapshot = await self._get_visible_fields_snapshot(page)
                    new_fields = await self._detect_new_fields(current_snapshot, new_snapshot, form_data_keys)
                    
                    if new_fields:
                        self._detected_dynamic_fields.extend(new_fields)
                        print(f"🔍 Detected {len(new_fields)} new field(s) after filling {name}")
                    
                    # Update current snapshot
                    current_snapshot = new_snapshot
                except Exception as e:
                    print(f"⚠️ Dynamic detection error after {name}: {e}")
        
        await asyncio.sleep(1)
        
        # Auto-check terms
        try:
            checked = await self._auto_check_terms(page)
            if checked:
                print(f"✅ Auto-checked {checked} Terms/Privacy checkbox(es)")
        except:
            logger.warning("Error auto-checking terms", exc_info=True)
            pass
        
        await asyncio.sleep(0.5)
        
        # --- DYNAMIC FIELD CHECK: Halt if unfilled dynamic fields exist ---
        if self._detected_dynamic_fields:
            print(f"⚠️ HALTING SUBMISSION: {len(self._detected_dynamic_fields)} unfilled dynamic field(s) detected")
            return {
                "status": "partial_success",
                "filled_fields": filled, 
                "errors": errors, 
                "submit_success": False,
                "total_fields": len(form_data), 
                "successful_fields": len(filled),
                "fill_rate": len(filled) / len(form_data) if form_data else 0,
                "dynamic_fields_detected": self._detected_dynamic_fields,
                "message": f"Form filling paused: {len(self._detected_dynamic_fields)} new field(s) appeared that need values."
            }
        
        # Submit
        submit_ok = False
        for _ in range(3):
            try:
                submit_ok = await (self._submit_google_form if is_google_form else self._submit_form)(page, form_schema)
                if submit_ok:
                    await asyncio.sleep(2)
                    break
            except Exception as e:
                errors.append(f"Submit error: {e}")
            await asyncio.sleep(0.5)
        
        return {
            "status": "complete" if submit_ok else "submit_failed",
            "filled_fields": filled, "errors": errors, "submit_success": submit_ok,
            "total_fields": len(form_data), "successful_fields": len(filled),
            "fill_rate": len(filled) / len(form_data) if form_data else 0,
            "dynamic_fields_detected": []
        }

    async def _verify_field(self, page, field_info: Dict, expected: str) -> bool:
        """Verify field was filled correctly."""
        try:
            fname, ftype = field_info.get('name', ''), field_info.get('type', 'text')
            el = await self._find_element(page, [f"[name='{fname}']", f"input[name='{fname}']", f"textarea[name='{fname}']"])
            if not el:
                return True
            
            if ftype in self.TEXT_TYPES:
                actual = await el.input_value()
                return expected.lower() in actual.lower() or actual.lower() in expected.lower()
            elif ftype == 'radio':
                return await page.query_selector(f"input[name='{fname}']:checked") is not None
            elif ftype == 'checkbox':
                is_checked = await el.is_checked()
                return is_checked == (str(expected).lower() in ['true', 'yes', '1', 'checked'])
        except:
            logger.debug("Verification error", exc_info=True)
            pass
        return True

    async def validate_form_submission(self, page, initial_url: str = "") -> Dict[str, Any]:
        """Validate if form submission was successful."""
        try:
            await asyncio.sleep(2)
            page_text = (await page.inner_text('body')).lower()
            current_url = page.url.lower()
            
            success_found = any(i in page_text for i in self.SUCCESS_INDICATORS)
            error_found = any(i in page_text for i in self.ERROR_INDICATORS)
            
            # Check for visible validation errors
            for sel in [".error", ".invalid-feedback", ".text-danger", ".mat-error", ".form-error"]:
                try:
                    errs = await page.query_selector_all(f"{sel}:visible")
                    for e in errs:
                        if len(await e.inner_text()) > 2:
                            error_found, success_found = True, False
                            break
                except:
                    logger.debug("Error checking validation UI", exc_info=True)
                    pass
            
            # URL change detection
            url_changed = False
            if initial_url:
                try:
                    url_changed = urlparse(initial_url).path != urlparse(current_url).path
                except:
                    logger.debug("Error checking URL change", exc_info=True)
                    url_changed = initial_url != current_url
            
            url_success = any(w in current_url for w in ['thank', 'success', 'confirmation', 'complete', 'submitted', 'login', 'dashboard', 'verify'])
            
            # Google Forms success
            google_success = False
            if 'docs.google.com/forms' in page.url:
                for sel in ["[role='alert']:has-text('Your response has been recorded')", ".freebirdFormviewerViewResponseConfirmationMessage"]:
                    try:
                        el = await page.query_selector(sel)
                        if el and await el.is_visible():
                            google_success = True
                            break
                    except:
                        pass
            
            likely_success = (google_success or (success_found and not error_found) or (url_changed and not error_found) or url_success) and not error_found
            
            return {
                "likely_success": likely_success, "likely_error": error_found,
                "current_url": page.url, "success_indicators_found": success_found or google_success or url_success,
                "error_indicators_found": error_found, "url_changed": url_changed,
                "google_form_success": google_success if 'docs.google.com/forms' in page.url else None
            }
        except Exception as e:
            return {"likely_success": False, "likely_error": True, "error": str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────────────
    
    async def submit_form_data(self, url: str, form_data: Dict[str, str], form_schema: List[Dict], use_cdp: bool = False) -> Dict[str, Any]:
        """Submit form data to target website with CAPTCHA detection.
        
        On Windows, uses sync Playwright via asyncio.to_thread() to bypass
        asyncio subprocess limitations in Python 3.14.
        
        Flow:
            1. Open form in visible browser
            2. Fill all fields
            3. Detect CAPTCHA
            4. If CAPTCHA found: DON'T submit, leave browser open for user
            5. If no CAPTCHA: Submit form normally
        """
        if sys.platform == 'win32':
            return await asyncio.to_thread(self._sync_submit_form_data, url, form_data, form_schema, use_cdp)
        else:
            return await self._async_submit_form_data(url, form_data, form_schema, use_cdp)
    
    def _detect_captcha_sync(self, page) -> Dict[str, Any]:
        """Detect CAPTCHA using sync Playwright API."""
        import json
        selectors_js = json.dumps(CAPTCHA_SELECTORS)
        
        result = page.evaluate(f"""
            () => {{
                const captchaIndicators = {selectors_js};
                
                // Helper function to check if element is visible
                const isVisible = (el) => {{
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && 
                           style.visibility !== 'hidden' && 
                           rect.width > 0 && 
                           rect.height > 0;
                }};
                
                for (const selector of captchaIndicators) {{
                    try {{
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {{
                            if (isVisible(el)) {{
                                return {{
                                    hasCaptcha: true,
                                    type: 'captcha',
                                    selector: selector,
                                    message: 'CAPTCHA detected'
                                }};
                            }}
                        }}
                    }} catch(e) {{}}
                }}
                
                // Iframe check
                const iframes = document.querySelectorAll('iframe');
                for (const iframe of iframes) {{
                    const src = (iframe.src || '').toLowerCase();
                    const title = (iframe.title || '').toLowerCase();
                    if (src.includes('captcha') || src.includes('recaptcha') || src.includes('hcaptcha') || src.includes('turnstile') ||
                        title.includes('captcha') || title.includes('recaptcha') || title.includes('challenge')) {{
                        return {{
                            hasCaptcha: true,
                            type: 'iframe_captcha',
                            selector: 'iframe',
                            message: 'CAPTCHA iframe detected'
                        }};
                    }}
                }}
                
                return {{ hasCaptcha: false }};
            }}
        """)
        return result

    def _sync_fill_form(self, page, form_data: Dict[str, str], form_schema: List[Dict], is_google: bool) -> Dict[str, Any]:
        """Sync form filling for Windows."""
        filled, errors = [], []
        field_map = {f.get('name', ''): f for form in form_schema for f in form.get('fields', [])}
        
        for name, value in form_data.items():
            field_info = self._find_field_in_schema(name, field_map)
            if not field_info:
                # Fallback: use name directly as ID for Angular Material/dynamic ID forms
                logger.debug(f"Field not found in schema (sync), trying direct ID: {name}")
                field_info = {'id': name, 'name': name, 'type': 'text'}
            
            try:
                element = None
                if fid := field_info.get('id'):
                    element = page.query_selector(f"#{fid}")
                if not element and (fname := field_info.get('name')):
                    element = page.query_selector(f"[name='{fname}']")
                
                if element and element.is_visible():
                    ftype = field_info.get('type', 'text')
                    if ftype in {'text', 'email', 'tel', 'password', 'number', 'url', 'search', 'textarea'}:
                        element.fill(str(value))
                        filled.append(name)
                    elif ftype in {'select', 'dropdown'}:
                        try:
                            element.select_option(value=str(value))
                        except:
                            element.select_option(label=str(value))
                        filled.append(name)
                    elif ftype == 'checkbox':
                        if str(value).lower() in ['true', 'yes', '1', 'checked']:
                            element.check()
                        filled.append(name)
                    elif ftype == 'radio':
                        radios = page.query_selector_all(f"input[name='{name}'][type='radio']")
                        for radio in radios:
                            radio_val = radio.get_attribute('value') or ''
                            if radio_val.lower() == str(value).lower():
                                radio.click()
                                filled.append(name)
                                break
                    else:
                        element.fill(str(value))
                        filled.append(name)
                else:
                    errors.append(f"Element not found: {name}")
            except Exception as e:
                errors.append(f"Error filling {name}: {e}")
            
            time.sleep(0.3)
        
        return {
            "filled_fields": filled,
            "errors": errors,
            "total_fields": len(form_data),
            "successful_fields": len(filled),
            "fill_rate": len(filled) / len(form_data) if form_data else 0
        }
    
    def _sync_submit_form(self, page, form_schema: List[Dict], is_google: bool) -> bool:
        """Sync form submission for Windows."""
        selectors = self.GOOGLE_SUBMIT_SELECTORS if is_google else self.SUBMIT_SELECTORS
        
        for sel in selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    time.sleep(3)
                    return True
            except:
                continue
        
        return False
    
    def _sync_submit_form_data(self, url: str, form_data: Dict[str, str], form_schema: List[Dict], use_cdp: bool = False) -> Dict[str, Any]:
        """Sync Playwright implementation for Windows."""
        from playwright.sync_api import sync_playwright
        import json
        
        is_google = 'docs.google.com/forms' in url
        
        try:
            playwright = sync_playwright().start()
            
            browser = playwright.chromium.launch(
                headless=False,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            print(f"🌐 Navigating to form: {url}")
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            if is_google:
                try:
                    page.wait_for_selector('[role="listitem"], .freebirdFormviewerViewItemsItemItem', timeout=20000)
                    time.sleep(2)
                except:
                    pass
            else:
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except:
                    pass
                time.sleep(1)
            
            initial_url = page.url
            
            # Fill form
            fill_result = self._sync_fill_form(page, form_data, form_schema, is_google)
            
            # Check for CAPTCHA
            captcha_info = self._detect_captcha_sync(page)
            
            if captcha_info.get('hasCaptcha'):
                print(f"🔐 CAPTCHA detected: {captcha_info.get('type')}")
                print("🛑 CAPTCHA requires manual solving. Browser left open.")
                return {
                    "success": False,
                    "captcha_detected": True,
                    "captcha_type": captcha_info.get('type', 'unknown'),
                    "message": "Please solve the CAPTCHA in the browser window, then click Submit.",
                    "browser_left_open": True,
                    "fields_filled": fill_result.get("filled_fields", []),
                    "fill_rate": fill_result.get("fill_rate", 0)
                }
            
            # No CAPTCHA - submit
            submit_ok = self._sync_submit_form(page, form_schema, is_google)
            time.sleep(2)
            
            # Cleanup
            context.close()
            browser.close()
            playwright.stop()
            
            success = submit_ok and not fill_result.get("errors")
            
            return {
                "success": success,
                "captcha_detected": False,
                "message": "Form submitted successfully" if success else "Form submission completed with issues",
                "submission_result": fill_result
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e), "message": f"Form submission failed: {e}"}
    
    async def _async_submit_form_data(self, url: str, form_data: Dict[str, str], form_schema: List[Dict], use_cdp: bool = False) -> Dict[str, Any]:
        """Original async Playwright implementation for non-Windows platforms."""
        is_google = 'docs.google.com/forms' in url
        
        try:
            from playwright.async_api import async_playwright
            
            playwright = await async_playwright().start()
            
            # Create visible browser for form submission
            browser = await playwright.chromium.launch(
                headless=False,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            print(f"🌐 Navigating to form: {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            # Wait for form load
            if is_google:
                try:
                    await page.wait_for_selector('[role="listitem"], .freebirdFormviewerViewItemsItemItem', timeout=20000)
                    await asyncio.sleep(2)
                except:
                    logger.debug("Google form selector wait timeout/error")
                    pass
            else:
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except:
                    logger.debug("Network idle wait error")
                    pass
                await asyncio.sleep(1)
            
            initial_url = page.url
            
            # ================================================================
            # STEP 1: FILL FORM FIELDS
            # ================================================================
            fill_result = await self._fill_form_only(page, form_data, form_schema, is_google)
            
            # ================================================================
            # STEP 2: CHECK FOR CAPTCHA AND ATTEMPT AUTO-SOLVE
            # ================================================================
            captcha_info = await detect_captcha(page)
            
            if captcha_info.get('hasCaptcha'):
                print(f"🔐 CAPTCHA detected: {captcha_info.get('type')}")
                
                # Attempt to solve using CaptchaSolverService
                solver = get_captcha_solver()
                solve_result = await solver.solve(page, captcha_info, initial_url)
                
                if solve_result.success:
                    print(f"✅ CAPTCHA solved via {solve_result.strategy_used.value}")
                    # Continue to submission
                elif solve_result.requires_user_action:
                    # Manual fallback - leave browser open
                    print("🛑 CAPTCHA requires manual solving. Browser left open.")
                    return {
                        "success": False,
                        "captcha_detected": True,
                        "captcha_type": captcha_info.get('type', 'unknown'),
                        "captcha_strategy": solve_result.strategy_used.value,
                        "message": solve_result.error or "Please solve the CAPTCHA in the browser window, then click Submit.",
                        "browser_left_open": True,
                        "fields_filled": fill_result.get("filled_fields", []),
                        "fill_rate": fill_result.get("fill_rate", 0)
                    }
                else:
                    # Solver failed unexpectedly
                    print(f"⚠️ CAPTCHA solve failed: {solve_result.error}")
                    return {
                        "success": False,
                        "captcha_detected": True,
                        "captcha_type": captcha_info.get('type', 'unknown'),
                        "message": f"CAPTCHA solve failed: {solve_result.error}. Please solve manually.",
                        "browser_left_open": True,
                        "fields_filled": fill_result.get("filled_fields", []),
                        "fill_rate": fill_result.get("fill_rate", 0)
                    }
            
            # ================================================================
            # STEP 3: NO CAPTCHA - SUBMIT NORMALLY
            # ================================================================
            submit_ok = await (self._submit_google_form if is_google else self._submit_form)(page, form_schema)
            await asyncio.sleep(2)
            
            validation = await self.validate_form_submission(page, initial_url)
            
            # Clean up browser after successful submission
            await context.close()
            await browser.close()
            await playwright.stop()
            
            success = submit_ok and not fill_result.get("errors") and validation.get("likely_success", False)
            
            return {
                "success": success,
                "captcha_detected": False,
                "message": "Form submitted successfully" if success else "Form submission completed with issues",
                "submission_result": fill_result,
                "validation_result": validation
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e), "message": "Form submission failed"}
    
    async def _fill_form_only(self, page, form_data: Dict[str, str], form_schema: List[Dict], is_google_form: bool = False) -> Dict[str, Any]:
        """Fill form fields WITHOUT submitting."""
        filled, errors = [], []
        
        # Build field mapping
        field_map = {f.get('name', ''): f for form in form_schema for f in form.get('fields', [])}
        
        # Find password for confirmation fields
        password_val = next((v for k, v in form_data.items() 
                            if 'password' in k.lower() and not any(x in k.lower() for x in ['confirm', 'verify', 'retype', 'cpass'])), '')
        
        def is_confirm_field(name, label):
            combined = (name + (label or '')).lower()
            return any(k in combined for k in ['confirm', 'verify', 'retype', 'repeat', 'cpass', 'cpassword']) and 'password' in combined
        
        # Build fields to process
        fields_to_process, processed = [], set()
        for name, value in form_data.items():
            field_info = field_map.get(name, {})
            label = field_info.get('label') or field_info.get('display_name', '')
            final_val = password_val if is_confirm_field(name, label) and password_val else value
            fields_to_process.append((name, final_val))
            processed.add(name)
        
        # Add missing confirm fields from schema
        for name, info in field_map.items():
            if name not in processed:
                label = info.get('label', '')
                if is_confirm_field(name, label) and password_val:
                    fields_to_process.append((name, password_val))
        
        # Fill each field
        for name, value in fields_to_process:
            if name not in field_map:
                continue
            field_info = field_map[name]
            success = False
            
            for attempt in range(3):
                try:
                    success = await (self._fill_google_form_field if is_google_form else self._fill_field)(page, field_info, value, attempt)
                    if success:
                        filled.append(name)
                        break
                except Exception as e:
                    if attempt == 2:
                        errors.append(f"Error filling {name}: {e}")
                await asyncio.sleep(0.5)
            
            if not success:
                errors.append(f"Failed to fill: {name}")
        
        await asyncio.sleep(1)
        
        # Auto-check terms
        try:
            checked = await self._auto_check_terms(page)
            if checked:
                print(f"✅ Auto-checked {checked} Terms/Privacy checkbox(es)")
        except:
            logger.warning("Error auto-checking terms", exc_info=True)
            pass
        
        return {
            "filled_fields": filled,
            "errors": errors,
            "total_fields": len(form_data),
            "successful_fields": len(filled),
            "fill_rate": len(filled) / len(form_data) if form_data else 0
        }