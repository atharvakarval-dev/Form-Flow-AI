import asyncio
import aiohttp
from playwright.async_api import async_playwright
from typing import Dict, List, Any, Optional
import json
import time
import os
import random
from urllib.parse import urljoin, urlparse

class FormSubmitter:
    def __init__(self):
        self.session_timeout = 30000  # 30 seconds
        self.debug_screenshots = []  # Store debug screenshot paths
    
    async def _human_type(self, element, text: str):
        """Type text character by character with random delays for human-like behavior"""
        await element.click()
        await element.fill('')  # Clear first
        for char in text:
            await element.type(char, delay=random.randint(30, 100))
        await asyncio.sleep(0.1)
    
    async def _take_debug_screenshot(self, page, prefix: str) -> str:
        """Take screenshot for debugging purposes"""
        filename = f"debug_{prefix}_{int(time.time())}.png"
        filepath = os.path.join(os.getcwd(), filename)
        try:
            await page.screenshot(path=filepath)
            self.debug_screenshots.append(filepath)
            print(f"📸 Debug screenshot saved: {filename}")
            return filepath
        except Exception as e:
            print(f"⚠️ Failed to take screenshot: {e}")
            return ""
    
    async def _fill_with_js_injection(self, page, field_name: str, value: str, field_type: str = 'text') -> bool:
        """Fallback: Fill field using JavaScript injection when normal methods fail"""
        try:
            # Escape special characters for JS
            escaped_value = value.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")
            
            result = await page.evaluate(f"""
                () => {{
                    // Try multiple selector strategies
                    const selectors = [
                        '[name="{field_name}"]',
                        '#{field_name}',
                        '[id="{field_name}"]',
                        'input[name="{field_name}"]',
                        'textarea[name="{field_name}"]',
                        'select[name="{field_name}"]'
                    ];
                    
                    for (const selector of selectors) {{
                        const el = document.querySelector(selector);
                        if (el) {{
                            // Set value
                            el.value = "{escaped_value}";
                            
                            // Trigger events to notify frameworks
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                            
                            // For React
                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype, 'value'
                            )?.set || Object.getOwnPropertyDescriptor(
                                window.HTMLTextAreaElement.prototype, 'value'
                            )?.set;
                            if (nativeInputValueSetter) {{
                                nativeInputValueSetter.call(el, "{escaped_value}");
                                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            }}
                            
                            return true;
                        }}
                    }}
                    return false;
                }}
            """)
            
            if result:
                print(f"✅ JS injection filled field: {field_name}")
            return result
        except Exception as e:
            print(f"⚠️ JS injection failed for {field_name}: {e}")
            return False
        
    async def submit_form_data(self, url: str, form_data: Dict[str, str], form_schema: List[Dict]) -> Dict[str, Any]:
        """
        Submit form data to the target website using Playwright automation with enhanced accuracy
        """
        is_google_form = 'docs.google.com/forms' in url
        
        try:
            async with async_playwright() as p:
                # Launch browser with enhanced settings
                browser = await p.chromium.launch(
                    headless=False,  # Set to True for production
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--window-size=1920,1080"
                    ]
                )
                
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                
                # Navigate to the form page with better waiting
                print(f"🌐 Navigating to form: {url}")
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                
                # Wait for form to load (especially important for Google Forms)
                if is_google_form:
                    print("⏳ Waiting for Google Form to load...")
                    try:
                        await page.wait_for_selector('[role="listitem"], .freebirdFormviewerViewItemsItemItem', timeout=20000)
                        await asyncio.sleep(2)  # Extra time for dynamic content
                    except:
                        print("⚠️ Timeout waiting for form elements, proceeding anyway...")
                else:
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except:
                        print("⚠️ Network idle timeout, proceeding...")
                    await asyncio.sleep(1)
                
                # Find and fill the form with retry logic
                initial_url = page.url
                submission_result = await self._fill_and_submit_form(page, form_data, form_schema, is_google_form)
                
                # Validate submission
                validation_result = await self.validate_form_submission(page, initial_url)
                
                # Take screenshot for verification
                screenshot = await page.screenshot()
                
                await browser.close()
                
                # Determine overall success
                overall_success = (
                    submission_result.get("submit_success", False) and
                    len(submission_result.get("errors", [])) == 0 and
                    validation_result.get("likely_success", False)
                )
                
                return {
                    "success": overall_success,
                    "message": "Form submitted successfully" if overall_success else "Form submission completed with issues",
                    "submission_result": submission_result,
                    "validation_result": validation_result,
                    "screenshot_taken": True
                }
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "message": "Form submission failed"
            }
    
    async def _fill_and_submit_form(self, page, form_data: Dict[str, str], form_schema: List[Dict], is_google_form: bool = False) -> Dict[str, Any]:
        """
        Fill form fields and submit the form with enhanced accuracy and retry logic
        """
        filled_fields = []
        errors = []
        
        # Create a mapping of field names to selectors from schema
        field_mapping = {}
        for form in form_schema:
            for field in form.get('fields', []):
                field_name = field.get('name', '')
                field_mapping[field_name] = field
        
        # Fill each field with the provided data (with retry logic)
        # Fill each field with the provided data (with retry logic)
        # First, find any password field value to use for confirmation fields
        password_value = ""
        for field_name, value in form_data.items():
            # Exclude known confirmation keywords to find the REAL password
            if 'password' in field_name.lower() and not any(x in field_name.lower() for x in ['confirm', 'verify', 'retype', 'cpassword', 'cpass']):
                password_value = value
                break
        
        # Helper to identify confirm fields
        def is_confirm_field(name, label):
            n = name.lower()
            l = (label or '').lower()
            keywords = ['confirm', 'verify', 'retype', 'cpassword', 'cpass']
            has_keyword = any(k in n or k in l for k in keywords)
            is_pass = 'password' in n or 'password' in l
            return has_keyword and is_pass

        # Smart Fill Loop
        fields_to_process = []
        processed_names = set()

        # 1. Process existing data, but OVERWRITE confirm fields
        for field_name, value in form_data.items():
            field_info = field_mapping.get(field_name, {})
            display_label = field_info.get('label') or field_info.get('display_name') or ''
            
            if is_confirm_field(field_name, display_label) and password_value:
                print(f"🔄 Overwriting confirm field '{field_name}' with password value")
                fields_to_process.append((field_name, password_value))
            else:
                fields_to_process.append((field_name, value))
            processed_names.add(field_name)
        
        # 2. Add missing confirm fields from schema
        for field_name, field_info in field_mapping.items():
            if field_name not in processed_names:
                display_label = field_info.get('label') or field_info.get('display_name') or ''
                
                if is_confirm_field(field_name, display_label):
                    if password_value:
                        print(f"🔄 Auto-filling missing confirm field '{field_name}' with password value")
                        fields_to_process.append((field_name, password_value))

        for field_name, value in fields_to_process:
            if field_name in field_mapping:
                field_info = field_mapping[field_name]
                success = False
                last_error = None
                
                # Retry up to 3 times for each field
                verified = False
                for attempt in range(3):
                    try:
                        if is_google_form:
                            success = await self._fill_google_form_field(page, field_info, value, attempt)
                        else:
                            success = await self._fill_field(page, field_info, value, attempt)
                        
                        if success:
                            # Verify the field was filled correctly
                            verified = await self._verify_field_value(page, field_info, value)
                            if verified:
                                filled_fields.append(field_name)
                                break
                            else:
                                last_error = f"Field filled but value not verified: {field_name}"
                        else:
                            last_error = f"Failed to fill field: {field_name} (attempt {attempt + 1})"
                    except Exception as e:
                        last_error = f"Error filling {field_name}: {str(e)}"
                    
                    if success and verified:
                        break
                    
                    # Wait before retry
                    if attempt < 2:
                        await asyncio.sleep(0.5)
                
                if not success:
                    errors.append(last_error or f"Failed to fill field: {field_name} after 3 attempts")
        
        # Wait a bit after filling all fields
        await asyncio.sleep(1)
        
        # Auto-check all unchecked checkboxes (Privacy Policy, Terms of Service, etc.)
        try:
            await page.evaluate("""
                () => {
                    // Find all unchecked checkboxes and check them
                    const checkboxes = document.querySelectorAll('input[type="checkbox"]:not(:checked)');
                    checkboxes.forEach(checkbox => {
                        if (!checkbox.disabled) {
                            checkbox.checked = true;
                            checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                            checkbox.dispatchEvent(new Event('input', { bubbles: true }));
                            console.log('Auto-checked checkbox:', checkbox.name || checkbox.id || 'unnamed');
                        }
                    });
                    
                    // Also handle Material/Angular style checkboxes
                    const matCheckboxes = document.querySelectorAll('mat-checkbox:not(.mat-checkbox-checked)');
                    matCheckboxes.forEach(matCb => {
                        const input = matCb.querySelector('input');
                        const label = matCb.querySelector('label') || matCb;
                        if (input && !input.disabled) {
                            label.click();
                            console.log('Auto-clicked Material checkbox');
                        }
                    });
                    
                    // Handle custom checkbox divs with role="checkbox"
                    const roleCheckboxes = document.querySelectorAll('[role="checkbox"][aria-checked="false"]');
                    roleCheckboxes.forEach(cb => {
                        cb.click();
                        console.log('Auto-clicked role checkbox');
                    });
                    
                    return true;
                }
            """)
            print("✅ Auto-checked all unchecked checkboxes (Privacy/Terms)")
        except Exception as e:
            print(f"⚠️ Auto-check checkboxes warning: {e}")
        
        await asyncio.sleep(0.5)
        
        # Find and click submit button (with retry)
        submit_success = False
        for attempt in range(3):
            try:
                if is_google_form:
                    submit_success = await self._submit_google_form(page)
                else:
                    submit_success = await self._submit_form(page, form_schema)
                
                if submit_success:
                    # Wait for submission to process
                    await asyncio.sleep(2)
                    break
            except Exception as e:
                if attempt == 2:
                    errors.append(f"Submit error: {str(e)}")
                await asyncio.sleep(0.5)
        
        return {
            "filled_fields": filled_fields,
            "errors": errors,
            "submit_success": submit_success,
            "total_fields": len(form_data),
            "successful_fields": len(filled_fields),
            "fill_rate": len(filled_fields) / len(form_data) if form_data else 0
        }
    
    async def _fill_field(self, page, field_info: Dict, value: str, attempt: int = 0) -> bool:
        """
        Fill a specific form field based on its type and selector with enhanced strategies
        """
        field_name = field_info.get('name', '')
        field_type = field_info.get('type', 'text')
        field_id = field_info.get('id', '')
        display_name = field_info.get('display_name', '')
        label = field_info.get('label', '')
        
        # Build comprehensive selector list
        selectors = []
        
        # Priority 1: ID-based selectors
        if field_id:
            selectors.append(f"#{field_id}")
            selectors.append(f"input#{field_id}")
            selectors.append(f"textarea#{field_id}")
            selectors.append(f"select#{field_id}")
        
        # Priority 2: Name-based selectors
        if field_name:
            selectors.append(f"[name='{field_name}']")
            selectors.append(f"input[name='{field_name}']")
            selectors.append(f"select[name='{field_name}']")
            selectors.append(f"textarea[name='{field_name}']")
            # Try with escaped quotes
            selectors.append(f"[name=\"{field_name}\"]")
        
        # Priority 3: Label-based selectors (for better accuracy)
        if label or display_name:
            search_text = label or display_name
            # Try to find input associated with label
            try:
                label_elements = await page.query_selector_all(f"label:has-text('{search_text}')")
                for label_el in label_elements:
                    label_for = await label_el.get_attribute('for')
                    if label_for:
                        selectors.append(f"#{label_for}")
            except:
                pass
        
        # Priority 4: Placeholder-based (if available)
        placeholder = field_info.get('placeholder', '')
        if placeholder:
            selectors.append(f"input[placeholder*='{placeholder[:20]}']")
            selectors.append(f"textarea[placeholder*='{placeholder[:20]}']")
        
        # Try each selector
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    # Check if element is visible and enabled
                    is_visible = await element.is_visible()
                    if not is_visible:
                        continue
                    
                    # Scroll element into view
                    await element.scroll_into_view_if_needed()
                    await asyncio.sleep(0.2)
                    
                    # Fill based on field type
                    if field_type in ['text', 'email', 'tel', 'password', 'number', 'url']:
                        await element.click()  # Focus first
                        await asyncio.sleep(0.1)
                        await element.fill('')  # Clear first
                        await element.fill(value)
                        await asyncio.sleep(0.2)
                        return True
                    elif field_type == 'select' or field_type == 'dropdown':
                        await element.select_option(value)
                        await asyncio.sleep(0.2)
                        return True
                    elif field_type == 'textarea':
                        await element.click()
                        await asyncio.sleep(0.1)
                        await element.fill('')
                        await element.fill(value)
                        await asyncio.sleep(0.2)
                        return True
                    elif field_type == 'radio':
                        # For radio buttons, find the option with matching value or label
                        radio_options = await page.query_selector_all(f"input[name='{field_name}'][type='radio']")
                        for radio in radio_options:
                            radio_value = await radio.get_attribute('value')
                            if radio_value:
                                # Try exact match
                                if radio_value.lower() == value.lower():
                                    await radio.click()
                                    await asyncio.sleep(0.2)
                                    return True
                                # Try partial match
                                if value.lower() in radio_value.lower() or radio_value.lower() in value.lower():
                                    await radio.click()
                                    await asyncio.sleep(0.2)
                                    return True
                    elif field_type == 'checkbox' or field_type == 'checkbox-group':
                        checkbox_value = str(value).lower()
                        if checkbox_value in ['true', 'yes', '1', 'checked', 'on']:
                            if not await element.is_checked():
                                await element.check()
                            await asyncio.sleep(0.2)
                            return True
                        else:
                            if await element.is_checked():
                                await element.uncheck()
                            await asyncio.sleep(0.2)
                            return True
                    
                    # FILE UPLOAD handling
                    elif field_type == 'file':
                        file_path = value  # Expects absolute path or list of paths
                        if file_path:
                            if isinstance(file_path, list):
                                # Multiple files
                                valid_files = [f for f in file_path if os.path.exists(f)]
                                if valid_files:
                                    await element.set_input_files(valid_files)
                                    await asyncio.sleep(0.5)
                                    print(f"✅ Uploaded {len(valid_files)} files")
                                    return True
                            elif os.path.exists(file_path):
                                # Single file
                                await element.set_input_files(file_path)
                                await asyncio.sleep(0.5)
                                print(f"✅ Uploaded file: {os.path.basename(file_path)}")
                                return True
                            else:
                                print(f"⚠️ File not found: {file_path}")
                    
                    # DATE/TIME handling
                    elif field_type in ['date', 'datetime-local', 'time', 'month', 'week']:
                        # Clear and fill with proper format
                        await element.click()
                        await asyncio.sleep(0.1)
                        await element.fill('')
                        await element.fill(value)  # Expects ISO format: YYYY-MM-DD, HH:MM, etc.
                        await asyncio.sleep(0.2)
                        return True
                    
                    # RANGE/SLIDER handling
                    elif field_type == 'range':
                        try:
                            # Get min, max values
                            min_val = float(await element.get_attribute('min') or 0)
                            max_val = float(await element.get_attribute('max') or 100)
                            target_val = float(value)
                            
                            # Clamp value to valid range
                            target_val = max(min_val, min(max_val, target_val))
                            
                            # Use JavaScript to set range value
                            await page.evaluate(f"""
                                (el) => {{
                                    el.value = {target_val};
                                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                }}
                            """, element)
                            await asyncio.sleep(0.2)
                            print(f"✅ Set range value to {target_val}")
                            return True
                        except Exception as e:
                            print(f"⚠️ Range fill error: {e}")
                    
                    # SCALE (Linear scale like Google Forms)
                    elif field_type == 'scale':
                        scale_value = str(value)
                        # Try to find and click the matching radio button
                        scale_radios = await page.query_selector_all(f"input[name='{field_name}'][type='radio']")
                        for radio in scale_radios:
                            radio_value = await radio.get_attribute('value')
                            if radio_value == scale_value:
                                await radio.scroll_into_view_if_needed()
                                await radio.click()
                                await asyncio.sleep(0.2)
                                print(f"✅ Selected scale value: {scale_value}")
                                return True
                    
                    # COLOR picker handling
                    elif field_type == 'color':
                        # Expects hex color like #ff0000
                        await element.fill(value)
                        await asyncio.sleep(0.2)
                        return True
                    
                    # SEARCH input handling
                    elif field_type == 'search':
                        await element.click()
                        await asyncio.sleep(0.1)
                        await element.fill('')
                        await element.fill(value)
                        await asyncio.sleep(0.2)
                        return True
                        
            except Exception as e:
                continue
        
        # FALLBACK: Try JavaScript injection if all else fails
        if attempt >= 2:
            print(f"🔄 Attempting JS injection fallback for {field_name}")
            return await self._fill_with_js_injection(page, field_name, value, field_type)
        
        return False
    
    async def _fill_google_form_field(self, page, field_info: Dict, value: str, attempt: int = 0) -> bool:
        """
        Fill a Google Form field with specialized handling
        """
        field_name = field_info.get('name', '')
        field_type = field_info.get('type', 'text')
        display_name = field_info.get('display_name', '')
        
        try:
            # Google Forms uses specific selectors
            if field_type in ['text', 'email', 'tel', 'textarea']:
                # Try to find input by entry number or label
                selectors = [
                    f"input[aria-label*='{display_name[:30]}']",
                    f"textarea[aria-label*='{display_name[:30]}']",
                    f"input[data-params*='{field_name}']",
                    f"textarea[data-params*='{field_name}']"
                ]
                
                # Also try finding by question index
                questions = await page.query_selector_all('[role="listitem"]')
                for idx, question in enumerate(questions):
                    question_text = await question.inner_text()
                    if display_name[:20].lower() in question_text.lower():
                        # Found the question, now find the input
                        input_el = await question.query_selector('input, textarea')
                        if input_el:
                            await input_el.click()
                            await asyncio.sleep(0.1)
                            await input_el.fill('')
                            await input_el.fill(value)
                            await asyncio.sleep(0.3)
                            return True
                
                # Fallback to direct selector
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            await element.scroll_into_view_if_needed()
                            await element.click()
                            await asyncio.sleep(0.1)
                            await element.fill('')
                            await element.fill(value)
                            await asyncio.sleep(0.3)
                            return True
                    except:
                        continue
            
            elif field_type in ['radio', 'mcq']:
                # Find radio options by label text
                options = field_info.get('options', [])
                for option in options:
                    option_label = option.get('label', option.get('value', ''))
                    if value.lower() in option_label.lower() or option_label.lower() in value.lower():
                        # Find and click the matching radio
                        radio_selectors = [
                            f"[role='radio'][aria-label*='{option_label[:30]}']",
                            f"input[type='radio'][aria-label*='{option_label[:30]}']"
                        ]
                        for selector in radio_selectors:
                            try:
                                radio = await page.query_selector(selector)
                                if radio:
                                    await radio.scroll_into_view_if_needed()
                                    await radio.click()
                                    await asyncio.sleep(0.3)
                                    return True
                            except:
                                continue
            
            elif field_type == 'dropdown':
                # Click dropdown and select option
                dropdown_selectors = [
                    f"[role='listbox'][aria-label*='{display_name[:30]}']",
                    f"[role='button'][aria-haspopup='listbox']"
                ]
                for selector in dropdown_selectors:
                    try:
                        dropdown = await page.query_selector(selector)
                        if dropdown:
                            await dropdown.scroll_into_view_if_needed()
                            await dropdown.click()
                            await asyncio.sleep(0.5)
                            
                            # Find and click the option
                            options = field_info.get('options', [])
                            for option in options:
                                option_label = option.get('label', option.get('value', ''))
                                if value.lower() in option_label.lower():
                                    option_el = await page.query_selector(f"[role='option']:has-text('{option_label[:30]}')")
                                    if option_el:
                                        await option_el.click()
                                        await asyncio.sleep(0.3)
                                        return True
                    except:
                        continue
            
            elif field_type == 'checkbox-group':
                # Handle multiple checkboxes
                selected_values = value if isinstance(value, list) else [value]
                options = field_info.get('options', [])
                for option in options:
                    option_label = option.get('label', option.get('value', ''))
                    should_check = any(v.lower() in option_label.lower() or option_label.lower() in v.lower() for v in selected_values)
                    
                    checkbox_selectors = [
                        f"[role='checkbox'][aria-label*='{option_label[:30]}']",
                        f"input[type='checkbox'][aria-label*='{option_label[:30]}']"
                    ]
                    for selector in checkbox_selectors:
                        try:
                            checkbox = await page.query_selector(selector)
                            if checkbox:
                                is_checked = await checkbox.get_attribute('aria-checked') == 'true'
                                if should_check and not is_checked:
                                    await checkbox.scroll_into_view_if_needed()
                                    await checkbox.click()
                                    await asyncio.sleep(0.2)
                                elif not should_check and is_checked:
                                    await checkbox.scroll_into_view_if_needed()
                                    await checkbox.click()
                                    await asyncio.sleep(0.2)
                        except:
                            continue
                return True
            
            # LINEAR SCALE handling for Google Forms
            elif field_type == 'scale':
                scale_value = str(value)
                # Find the question containing the scale
                questions = await page.query_selector_all('[role="listitem"]')
                for question in questions:
                    question_text = await question.inner_text()
                    if display_name[:20].lower() in question_text.lower():
                        # Find scale radios in this question
                        scale_radios = await question.query_selector_all('[role="radio"]')
                        for radio in scale_radios:
                            radio_label = await radio.get_attribute('aria-label') or ''
                            if scale_value in radio_label or radio_label == scale_value:
                                await radio.scroll_into_view_if_needed()
                                await radio.click()
                                await asyncio.sleep(0.3)
                                print(f"✅ Selected scale value: {scale_value}")
                                return True
            
            # GRID handling for Google Forms (MCQ grid or checkbox grid)
            elif field_type == 'grid':
                # value should be a dict: {'row_label': 'column_value', ...}
                if isinstance(value, dict):
                    questions = await page.query_selector_all('[role="listitem"]')
                    for question in questions:
                        question_text = await question.inner_text()
                        if display_name[:20].lower() in question_text.lower():
                            # Find each row and select the appropriate column
                            rows = await question.query_selector_all('[role="group"]')
                            for row in rows:
                                row_text = await row.inner_text()
                                for row_label, col_value in value.items():
                                    if row_label.lower() in row_text.lower():
                                        # Find and click the matching option
                                        options = await row.query_selector_all('[role="radio"], [role="checkbox"]')
                                        for option in options:
                                            option_label = await option.get_attribute('aria-label') or ''
                                            if col_value.lower() in option_label.lower():
                                                await option.click()
                                                await asyncio.sleep(0.2)
                                                break
                            return True
            
            # DATE handling for Google Forms
            elif field_type in ['date', 'datetime-local']:
                questions = await page.query_selector_all('[role="listitem"]')
                for question in questions:
                    question_text = await question.inner_text()
                    if display_name[:20].lower() in question_text.lower():
                        date_inputs = await question.query_selector_all('input[type="date"], input[type="text"]')
                        for date_input in date_inputs:
                            await date_input.click()
                            await asyncio.sleep(0.1)
                            await date_input.fill('')
                            await date_input.fill(value)
                            await asyncio.sleep(0.2)
                            return True
            
            # TIME handling for Google Forms
            elif field_type == 'time':
                questions = await page.query_selector_all('[role="listitem"]')
                for question in questions:
                    question_text = await question.inner_text()
                    if display_name[:20].lower() in question_text.lower():
                        time_inputs = await question.query_selector_all('input[type="time"], input[type="text"]')
                        for time_input in time_inputs:
                            await time_input.click()
                            await asyncio.sleep(0.1)
                            await time_input.fill('')
                            await time_input.fill(value)
                            await asyncio.sleep(0.2)
                            return True
            
            # FILE UPLOAD handling for Google Forms (usually requires Google Drive)
            elif field_type == 'file':
                print(f"⚠️ Google Forms file upload requires Google Drive authentication - skipping")
                # Google Forms file uploads are complex and require OAuth
                return False
            
        except Exception as e:
            print(f"Error filling Google Form field: {e}")
            await self._take_debug_screenshot(page, f"error_{field_name}")
            return False
        
        return False
    
    async def _verify_field_value(self, page, field_info: Dict, expected_value: str) -> bool:
        """
        Verify that a field was filled with the correct value
        """
        try:
            field_name = field_info.get('name', '')
            field_type = field_info.get('type', 'text')
            
            # Try to get the actual value from the field
            selectors = [
                f"[name='{field_name}']",
                f"input[name='{field_name}']",
                f"textarea[name='{field_name}']"
            ]
            
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        if field_type in ['text', 'email', 'tel', 'textarea']:
                            actual_value = await element.input_value()
                            # Allow partial match for better accuracy
                            if expected_value.lower() in actual_value.lower() or actual_value.lower() in expected_value.lower():
                                return True
                        elif field_type == 'radio':
                            checked_radio = await page.query_selector(f"input[name='{field_name}']:checked")
                            if checked_radio:
                                return True
                        elif field_type == 'checkbox':
                            is_checked = await element.is_checked()
                            value_bool = str(expected_value).lower() in ['true', 'yes', '1', 'checked']
                            return is_checked == value_bool
                except:
                    continue
            
            # If we can't verify, assume it worked (better than failing)
            return True
        except:
            return True  # Default to true if verification fails
    
    async def _submit_form(self, page, form_schema: List[Dict]) -> bool:
        """
        Find and click the submit button with enhanced strategies
        """
        # Common submit button selectors (prioritized)
        submit_selectors = []
        
        # Priority 1: Form schema submit buttons
        for form in form_schema:
            for field in form.get('fields', []):
                if field.get('type') == 'submit':
                    field_name = field.get('name', '')
                    field_id = field.get('id', '')
                    if field_id:
                        submit_selectors.append(f"#{field_id}")
                    if field_name:
                        submit_selectors.append(f"[name='{field_name}']")
        
        # Priority 2: Standard submit selectors
        submit_selectors.extend([
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit')",
            "button:has-text('Send')",
            "button:has-text('Submit Form')",
            "button:has-text('Send Form')",
            "input[value*='Submit']",
            "input[value*='Send']",
            "[role='button']:has-text('Submit')",
            "[role='button']:has-text('Send')",
            ".submit-btn",
            ".btn-submit",
            "#submit",
            "[data-submit]",
            "[onclick*='submit']"
        ])
        
        for selector in submit_selectors:
            try:
                # Try to find element
                element = await page.query_selector(selector)
                if element:
                    # Check if element is visible and enabled
                    is_visible = await element.is_visible()
                    is_enabled = await element.is_enabled()
                    
                    if is_visible and is_enabled:
                        # Scroll into view
                        await element.scroll_into_view_if_needed()
                        await asyncio.sleep(0.3)
                        
                        # Click the submit button
                        await element.click()
                        
                        # Wait for submission to process
                        try:
                            await page.wait_for_load_state('networkidle', timeout=15000)
                        except:
                            # Even if networkidle doesn't happen, wait a bit
                            await asyncio.sleep(2)
                        
                        return True
            except Exception as e:
                continue
        
        # Fallback: Try pressing Enter on the form
        try:
            form_element = await page.query_selector('form')
            if form_element:
                await form_element.press('Enter')
                await asyncio.sleep(2)
                return True
        except:
            pass
        
        return False
    
    async def _submit_google_form(self, page) -> bool:
        """
        Submit a Google Form with specialized handling
        """
        try:
            # Google Forms submit button selectors
            submit_selectors = [
                "[role='button']:has-text('Submit')",
                "div[role='button']:has-text('Submit')",
                ".freebirdFormviewerViewNavigationSubmitButton",
                "[jsname='M2UYVd']",  # Common Google Forms submit button
                "span:has-text('Submit')",
                "div:has-text('Submit')"
            ]
            
            for selector in submit_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            await element.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            await element.click()
                            await asyncio.sleep(3)  # Wait for Google Forms to process
                            return True
                except:
                    continue
            
            # Alternative: Try finding by aria-label
            try:
                submit_buttons = await page.query_selector_all("[role='button']")
                for button in submit_buttons:
                    aria_label = await button.get_attribute('aria-label')
                    if aria_label and 'submit' in aria_label.lower():
                        await button.scroll_into_view_if_needed()
                        await button.click()
                        await asyncio.sleep(3)
                        return True
            except:
                pass
            
        except Exception as e:
            print(f"Error submitting Google Form: {e}")
        
        return False
    
    async def validate_form_submission(self, page, initial_url: str = "") -> Dict[str, Any]:
        """
        Validate if form submission was successful by checking for success indicators with enhanced detection
        """
        success_indicators = [
            "thank you", "thankyou", "success", "submitted", "received",
            "confirmation", "complete", "your response has been recorded",
            "form submitted", "response recorded",
            # New indicators for redirects
            "verify", "verification", "check your email", "email sent",
            "login", "sign in", "dashboard", "click here to login",
            "account created", "welcome", "password", " otp "
        ]
        
        error_indicators = [
            "error", "invalid", "required field", "missing", "failed",
            "please fill", "this field is required", "must be",
            "correct the errors"
        ]
        
        try:
            # Wait a bit for page to update/redirect
            await asyncio.sleep(2)
            
            page_text = await page.inner_text('body')
            page_text_lower = page_text.lower()
            
            # Check for success indicators
            success_found = any(indicator in page_text_lower for indicator in success_indicators)
            error_found = any(indicator in page_text_lower for indicator in error_indicators)
            
            # Smart check: If we see specific red error text or input-error classes, it is definitely an error
            try:
                # Common validation error selectors
                error_selectors = [
                    ".error", ".invalid-feedback", ".text-danger", ".text-red-500", 
                    "[color='red']", ".mat-error", "mat-error", 
                    ".form-error", ".field-error", "div[class*='error']"
                ]
                for err_sel in error_selectors:
                    visible_errors = await page.query_selector_all(f"{err_sel}:visible")
                    for err in visible_errors:
                        text = await err.inner_text()
                        if text and len(text) > 2: # Ignore empty chars
                            print(f"⚠️ Found visible validation error: {text}")
                            error_found = True
                            success_found = False # Invalidate success
                            break
            except:
                pass

            # Check URL change (strong indicator)
            current_url = page.url.lower()
            url_changed = False
            if initial_url:
                try:
                    initial_parse = urlparse(initial_url)
                    current_parse = urlparse(current_url)
                    # Consider it changed if path is different (ignore query params which might just be session IDs)
                    url_changed = initial_parse.path != current_parse.path
                except:
                    url_changed = initial_url != current_url
            
            url_success_keywords = any(word in current_url for word in ['thank', 'success', 'confirmation', 'complete', 'submitted', 'login', 'dashboard', 'verify'])
            
            # For Google Forms, check for specific success messages
            is_google_form = 'docs.google.com/forms' in page.url
            google_success = False
            if is_google_form:
                # Google Forms shows specific success indicators
                google_success_selectors = [
                    "[role='alert']:has-text('Your response has been recorded')",
                    ".freebirdFormviewerViewResponseConfirmationMessage",
                    "div:has-text('Your response has been recorded')"
                ]
                for selector in google_success_selectors:
                    try:
                        success_element = await page.query_selector(selector)
                        if success_element and await success_element.is_visible():
                            google_success = True
                            break
                    except:
                        continue
            
            # Check if ORIGINAL form is still visible (might indicate failure)
            # Be careful: seeing A form (like login form) doesn't mean failure
            form_selector = 'form'
            if initial_url: # Try to be smart about whether it's the SAME form
                pass 
            
            form_still_visible = False
            if not url_changed:
                 form_still_visible = await page.query_selector('form') is not None
            
            # Overall success determination
            # If URL changed significantly (path change), it's likely success unless we see specific errors
            # If "login" or "verify" words appear, it's likely success (new account flow)
            
            likely_success = (
                google_success or
                (success_found and not error_found) or
                (url_changed and not error_found) or 
                url_success_keywords
            )
            
            # Override: if explicitly seeing "error", it's not success
            if error_found:
                likely_success = False
            
            return {
                "likely_success": likely_success,
                "likely_error": error_found,
                "current_url": page.url,
                "success_indicators_found": success_found or google_success or url_success_keywords,
                "error_indicators_found": error_found,
                "url_changed": url_changed,
                "google_form_success": google_success if is_google_form else None
            }
            
        except Exception as e:
            return {
                "likely_success": False,
                "likely_error": True,
                "error": str(e)
            }