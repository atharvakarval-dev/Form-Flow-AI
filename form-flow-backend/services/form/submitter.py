import asyncio
from typing import Dict, List, Any
import time
import os
import random
from urllib.parse import urlparse

# Import browser pool for memory-efficient browser reuse
from .browser_pool import get_browser_context


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

    def __init__(self):
        self.session_timeout = 30000
        self.debug_screenshots = []

    # ─────────────────────────────────────────────────────────────────────────
    # SELECTOR UTILITIES
    # ─────────────────────────────────────────────────────────────────────────
    
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
            pass
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # CORE FIELD HANDLERS
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _fill_text(self, element, value: str) -> bool:
        """Universal handler for text-like inputs."""
        await element.click()
        await asyncio.sleep(0.1)
        await element.fill('')
        await element.fill(value)
        await asyncio.sleep(0.2)
        return True

    async def _fill_dropdown(self, page, element, value: str, field_info: Dict) -> bool:
        """Unified dropdown handler with multiple strategies."""
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
        
        # Strategy: Partial text match on options
        try:
            options = await element.query_selector_all('option')
            for opt in options:
                text, val = await opt.inner_text(), await opt.get_attribute('value')
                if value.lower() in text.lower() or (val and value.lower() in val.lower()):
                    await element.select_option(value=val or text)
                    return True
        except:
            pass
        
        # Strategy: Click and select (custom dropdowns)
        try:
            await element.click()
            await asyncio.sleep(0.3)
            for opt_sel in [f"option:has-text('{value[:30]}')", f"[role='option']:has-text('{value[:30]}')", f"li:has-text('{value[:30]}')'"]:
                opt = await page.query_selector(opt_sel)
                if opt:
                    await opt.click()
                    return True
        except:
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
        """Fill form fields and submit."""
        filled, errors = [], []
        
        # Build field mapping
        field_map = {f.get('name', ''): f for form in form_schema for f in form.get('fields', [])}
        
        # Find password for confirmation fields
        password_val = next((v for k, v in form_data.items() 
                            if 'password' in k.lower() and not any(x in k.lower() for x in ['confirm', 'verify', 'retype', 'cpass'])), '')
        
        def is_confirm_field(name, label):
            combined = (name + (label or '')).lower()
            return any(k in combined for k in ['confirm', 'verify', 'retype', 'cpass']) and 'password' in combined
        
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
        
        # Fill each field with retry
        for name, value in fields_to_process:
            if name not in field_map:
                continue
            field_info = field_map[name]
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
        
        await asyncio.sleep(1)
        
        # Auto-check terms
        try:
            checked = await self._auto_check_terms(page)
            if checked:
                print(f"✅ Auto-checked {checked} Terms/Privacy checkbox(es)")
        except:
            pass
        
        await asyncio.sleep(0.5)
        
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
            "filled_fields": filled, "errors": errors, "submit_success": submit_ok,
            "total_fields": len(form_data), "successful_fields": len(filled),
            "fill_rate": len(filled) / len(form_data) if form_data else 0
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
                    pass
            
            # URL change detection
            url_changed = False
            if initial_url:
                try:
                    url_changed = urlparse(initial_url).path != urlparse(current_url).path
                except:
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
    
    async def submit_form_data(self, url: str, form_data: Dict[str, str], form_schema: List[Dict]) -> Dict[str, Any]:
        """Submit form data to target website with visible browser.
        
        Uses a dedicated browser instance (not the shared pool) so the user 
        can see the form being filled in real-time.
        """
        is_google = 'docs.google.com/forms' in url
        
        try:
            from playwright.async_api import async_playwright
            
            # Create a dedicated browser for form submission (visible mode)
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=False,  # Visible browser so user can see form filling
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
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
                    pass
            else:
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except:
                    pass
                await asyncio.sleep(1)
            
            initial_url = page.url
            result = await self._fill_and_submit_form(page, form_data, form_schema, is_google)
            validation = await self.validate_form_submission(page, initial_url)
            
            try:
                await page.screenshot()
            except:
                pass
            
            # Clean up browser
            await context.close()
            await browser.close()
            await playwright.stop()
            
            success = result.get("submit_success", False) and not result.get("errors") and validation.get("likely_success", False)
            
            return {
                "success": success,
                "message": "Form submitted successfully" if success else "Form submission completed with issues",
                "submission_result": result, "validation_result": validation, "screenshot_taken": True
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e), "message": "Form submission failed"}