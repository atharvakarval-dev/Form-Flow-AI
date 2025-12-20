"""
Form Parser - Optimized & Refactored
Scrapes form fields from any URL including Google Forms with iframe support.
"""

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import asyncio
from asyncio import TimeoutError
import re
import os

# ============================================================================
# CONSTANTS
# ============================================================================

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => false });
Object.defineProperty(navigator, 'plugins', { get: () => [
    {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
    {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'}
]});
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
"""

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage",
    "--no-sandbox", "--disable-setuid-sandbox", "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process", "--window-size=1920,1080"
]

# Field type detection keywords
FIELD_PATTERNS = {
    'email': ['email', 'e-mail', 'mail'],
    'phone': ['phone', 'mobile', 'tel', 'cell', 'contact'],
    'password': ['password', 'pwd', 'pass'],
    'name': ['name', 'fullname', 'full_name'],
    'first_name': ['first', 'fname', 'given'],
    'last_name': ['last', 'lname', 'surname', 'family'],
    'address': ['address', 'street', 'addr'],
    'city': ['city', 'town'],
    'state': ['state', 'province', 'region'],
    'country': ['country', 'nation'],
    'zip': ['zip', 'postal', 'pincode', 'postcode'],
    'date': ['date', 'dob', 'birthday'],
    'url': ['url', 'website', 'link', 'homepage'],
    'message': ['message', 'comment', 'feedback', 'description', 'note'],
}

# ============================================================================
# MAIN EXPORT FUNCTION
# ============================================================================

async def get_form_schema(url: str, generate_speech: bool = True, wait_for_dynamic: bool = True) -> Dict[str, Any]:
    """
    Scrape form fields from a URL. Supports Google Forms and standard HTML forms.
    
    Args:
        url: Target URL to scrape
        generate_speech: Whether to generate TTS for fields
        wait_for_dynamic: Whether to wait for JS content
    
    Returns:
        Dict with 'forms', 'url', 'is_google_form', 'total_forms', 'total_fields'
    """
    is_google_form = 'docs.google.com/forms' in url
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, args=BROWSER_ARGS)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US"
            )
            await context.add_init_script(STEALTH_SCRIPT)
            
            page = await context.new_page()
            await page.route("**/*", lambda r: r.abort() if r.request.resource_type in {"media", "font"} else r.continue_())
            
            print(f"🔗 Navigating to {'Google Form' if is_google_form else 'page'}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=120000)
            
            # Wait for content
            if is_google_form:
                await _wait_for_google_form(page)
            else:
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass
                await asyncio.sleep(2)
            
            print("✓ Page loaded, extracting forms...")
            
            # Extract forms
            forms_data = await _extract_google_forms(page) if is_google_form else await _extract_all_frames(page, url)
            
            print(f"✓ Found {len(forms_data)} form(s)")
            
            try:
                await page.unroute_all(behavior='ignoreErrors')
            except:
                pass
            await browser.close()
            
            # Process and enrich fields
            fields = _process_forms(forms_data)
            
            result = {
                'forms': fields,
                'url': url,
                'is_google_form': is_google_form,
                'total_forms': len(fields),
                'total_fields': sum(len(f['fields']) for f in fields)
            }
            
            # Generate speech if requested
            if generate_speech and fields:
                result['speech'] = _generate_speech(fields)
            
            return result
            
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        import traceback
        traceback.print_exc()
        return {'forms': [], 'url': url, 'error': str(e)}


# ============================================================================
# EXTRACTION HELPERS
# ============================================================================

async def _wait_for_google_form(page):
    """Wait for Google Form content to load."""
    print("⏳ Waiting for Google Form...")
    try:
        # Try multiple selectors - .Qr7Oae is the main question container class
        await page.wait_for_selector('.Qr7Oae, [role="listitem"], .freebirdFormviewerViewItemsItemItem', timeout=30000)
        await asyncio.sleep(3)
        # Scroll to load lazy content
        await page.evaluate("""
            async () => {
                let total = 0;
                const timer = setInterval(() => {
                    window.scrollBy(0, 200);
                    total += 200;
                    if (total >= document.body.scrollHeight) {
                        clearInterval(timer);
                        window.scrollTo(0, 0);
                    }
                }, 100);
                await new Promise(r => setTimeout(r, 2000));
            }
        """)
        # Scroll back to top and wait for rendering
        await asyncio.sleep(1)
    except TimeoutError:
        print("⚠️ Timeout waiting for form elements - attempting extraction anyway")


async def _extract_all_frames(page, url: str) -> List[Dict]:
    """Extract forms from all frames, with deduplication."""
    seen_urls, seen_fields, forms_data = set(), set(), []
    
    for frame in page.frames:
        if frame.url in seen_urls or frame.is_detached():
            continue
        seen_urls.add(frame.url)
        
        try:
            frame_forms = await _extract_standard_forms(frame)
            for form in frame_forms:
                # Deduplicate fields by name
                form['fields'] = [f for f in form.get('fields', []) 
                                  if not f.get('name') or (f['name'] not in seen_fields and not seen_fields.add(f['name']))]
            forms_data.extend([f for f in frame_forms if f.get('fields')])
        except Exception as e:
            if 'cross-origin' not in str(e).lower():
                print(f">> Frame error: {e}")
    
    # BeautifulSoup fallback
    if not forms_data:
        print(">> Trying BeautifulSoup fallback...")
        try:
            forms_data = _extract_with_beautifulsoup(await page.content())
        except:
            pass
    
    return forms_data


async def _extract_standard_forms(frame) -> List[Dict]:
    """Extract forms using JavaScript evaluation - handles radio/checkbox groups properly."""
    return await frame.evaluate("""
        () => {
            const getText = el => el ? (el.innerText || el.textContent || '').trim() : '';
            const isVisible = el => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0' && el.getBoundingClientRect().height > 0;
            };
            
            const findLabel = (field, form) => {
                // Try explicit label
                if (field.id) {
                    const lbl = form.querySelector(`label[for="${field.id}"]`);
                    if (lbl) return getText(lbl);
                }
                // Try parent label
                if (field.closest('label')) return getText(field.closest('label'));
                // Try previous sibling
                const prev = field.previousElementSibling;
                if (prev?.tagName === 'LABEL') return getText(prev);
                // Try aria-label or placeholder
                return field.getAttribute('aria-label') || field.placeholder || '';
            };
            
            // Find common label for a group of radio/checkbox inputs (the question text)
            const findGroupLabel = (inputs, form) => {
                if (inputs.length === 0) return '';
                
                // Look for a common parent container with a question/label
                const firstInput = inputs[0];
                
                // Method 1: Find fieldset > legend (standard HTML)
                const fieldset = firstInput.closest('fieldset');
                if (fieldset) {
                    const legend = fieldset.querySelector('legend');
                    if (legend) return getText(legend);
                }
                
                // Method 2: Look for a label/heading before the group
                // Universal selectors for popular form libraries:
                // - Bootstrap: .form-group, .mb-3, .form-check
                // - Materialize: .input-field
                // - Foundation: .callout, .fieldset
                // - Tailwind: common patterns like .space-y-*, .flex, [class*="mb-"]
                // - Semantic UI: .field, .grouped.fields
                // - Custom: .question, .field-wrapper, .form-field, .field-container
                const container = firstInput.closest(
                    'fieldset, .form-group, .question, .field-wrapper, [role="group"], [role="radiogroup"], ' +
                    '.radio-group, .checkbox-group, .input-field, .field, .grouped, .form-field, ' +
                    '.field-container, .form-item, .form-row, [class*="mb-"], .callout'
                ) || firstInput.parentElement?.parentElement;
                
                if (container) {
                    // Look for heading, label, or first text element (expanded selectors)
                    const labelEl = container.querySelector(
                        'h1, h2, h3, h4, h5, h6, legend, label:not(:has(input)), .question-text, ' +
                        '.form-label, .control-label, .col-form-label, [class*="label"], ' +
                        '.field-label, .input-label, span.label, p.label, .title'
                    );
                    if (labelEl && !labelEl.querySelector('input, [role="radio"], [role="checkbox"]')) {
                        return getText(labelEl);
                    }
                }
                
                // Method 3: aria-label on container or aria-labelledby
                const ariaLabel = firstInput.closest('[aria-label]')?.getAttribute('aria-label');
                if (ariaLabel) return ariaLabel;
                
                const labelledBy = firstInput.getAttribute('aria-labelledby');
                if (labelledBy) {
                    const labelEl = document.getElementById(labelledBy);
                    if (labelEl) return getText(labelEl);
                }
                
                // Method 4: data-label attribute (common in modern frameworks)
                const dataLabel = firstInput.closest('[data-label]')?.getAttribute('data-label') ||
                                 firstInput.getAttribute('data-label');
                if (dataLabel) return dataLabel;
                
                // Fallback: use the name attribute cleaned up
                const name = firstInput.name || '';
                return name.replace(/[_-]/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/\[\]/g, '').trim();
            };

            
            return Array.from(document.querySelectorAll('form')).map((form, idx) => {
                const fields = [];
                const processedRadioGroups = new Set();
                const processedCheckboxGroups = new Set();
                
                // First pass: Process all inputs
                Array.from(form.querySelectorAll('input, select, textarea')).forEach(field => {
                    const type = field.type || field.tagName.toLowerCase();
                    const name = field.name || field.id;
                    
                    if (!name || type === 'submit' || type === 'button' || type === 'hidden') return;
                    
                    // RADIO BUTTONS: Group by name
                    if (type === 'radio') {
                        if (processedRadioGroups.has(name)) return; // Already processed this group
                        processedRadioGroups.add(name);
                        
                        // Find all radios with this name
                        const radios = Array.from(form.querySelectorAll(`input[type="radio"][name="${name}"]`));
                        const options = radios.map(r => {
                            // Get option label
                            let optLabel = '';
                            
                            // Try aria-label first
                            optLabel = r.getAttribute('aria-label') || '';
                            
                            // Try associated label
                            if (!optLabel && r.id) {
                                const lbl = form.querySelector(`label[for="${r.id}"]`);
                                if (lbl) optLabel = getText(lbl);
                            }
                            
                            // Try parent label
                            if (!optLabel) {
                                const parentLabel = r.closest('label');
                                if (parentLabel) {
                                    // Get text excluding the input itself
                                    optLabel = getText(parentLabel).replace(r.value, '').trim();
                                }
                            }
                            
                            // Try next sibling text
                            if (!optLabel && r.nextSibling) {
                                optLabel = (r.nextSibling.textContent || '').trim();
                            }
                            
                            // Fallback to value
                            if (!optLabel) optLabel = r.value || '';
                            
                            return {
                                value: r.value || optLabel,
                                label: optLabel || r.value
                            };
                        }).filter(o => o.label);
                        
                        const groupLabel = findGroupLabel(radios, form);
                        const isRequired = radios.some(r => r.required || r.hasAttribute('required'));
                        
                        fields.push({
                            name: name,
                            type: 'radio',
                            tagName: 'radio-group',
                            label: groupLabel,
                            required: isRequired,
                            hidden: !radios.some(r => isVisible(r)),
                            options: options
                        });
                        return;
                    }
                    
                    // CHECKBOXES: Group by name if multiple with same name
                    if (type === 'checkbox') {
                        const checkboxes = Array.from(form.querySelectorAll(`input[type="checkbox"][name="${name}"]`));
                        
                        if (checkboxes.length > 1) {
                            // Multiple checkboxes with same name = checkbox group
                            if (processedCheckboxGroups.has(name)) return;
                            processedCheckboxGroups.add(name);
                            
                            const options = checkboxes.map(c => {
                                let optLabel = c.getAttribute('aria-label') || '';
                                if (!optLabel && c.id) {
                                    const lbl = form.querySelector(`label[for="${c.id}"]`);
                                    if (lbl) optLabel = getText(lbl);
                                }
                                if (!optLabel) {
                                    const parentLabel = c.closest('label');
                                    if (parentLabel) optLabel = getText(parentLabel).replace(c.value, '').trim();
                                }
                                if (!optLabel) optLabel = c.value || '';
                                
                                return {
                                    value: c.value || optLabel,
                                    label: optLabel || c.value,
                                    checked: c.checked
                                };
                            }).filter(o => o.label);
                            
                            fields.push({
                                name: name,
                                type: 'checkbox-group',
                                tagName: 'checkbox-group',
                                label: findGroupLabel(checkboxes, form),
                                required: checkboxes.some(c => c.required),
                                hidden: !checkboxes.some(c => isVisible(c)),
                                allows_multiple: true,
                                options: options
                            });
                        } else {
                            // Single checkbox
                            fields.push({
                                name: name,
                                type: 'checkbox',
                                tagName: 'input',
                                label: findLabel(field, form),
                                required: field.required,
                                hidden: !isVisible(field),
                                checked: field.checked
                            });
                        }
                        return;
                    }
                    
                    // SELECT dropdowns
                    if (field.tagName === 'SELECT') {
                        fields.push({
                            name: name,
                            type: 'dropdown',
                            tagName: 'select',
                            label: findLabel(field, form),
                            required: field.required,
                            hidden: !isVisible(field),
                            options: Array.from(field.options).filter(o => o.value).map(o => ({
                                value: o.value,
                                label: o.text.trim(),
                                selected: o.selected
                            }))
                        });
                        return;
                    }
                    
                    // Standard text/email/etc inputs
                    fields.push({
                        name: name,
                        type: type,
                        tagName: field.tagName.toLowerCase(),
                        label: findLabel(field, form),
                        placeholder: field.placeholder || null,
                        required: field.required || field.hasAttribute('required'),
                        hidden: !isVisible(field),
                        value: field.value || null,
                        disabled: field.disabled,
                        readonly: field.readOnly
                    });
                });
                
                return {
                    formIndex: idx,
                    action: form.action || null,
                    method: (form.method || 'GET').toUpperCase(),
                    id: form.id || null,
                    name: form.name || null,
                    fields: fields
                };
            }).filter(f => f.fields.length > 0);
        }
    """)


def _extract_with_beautifulsoup(html: str) -> List[Dict]:
    """BeautifulSoup fallback extraction with radio/checkbox grouping."""
    soup = BeautifulSoup(html, "html.parser")
    forms = []
    
    for idx, form in enumerate(soup.find_all("form")):
        fields = []
        processed_radio_groups = set()
        processed_checkbox_groups = set()
        
        for tag in form.find_all(["input", "select", "textarea"]):
            name = tag.get("name") or tag.get("id")
            field_type = tag.get("type", tag.name)
            
            if not name or field_type in ["submit", "button", "hidden"]:
                continue
            
            # Handle radio groups
            if field_type == "radio":
                if name in processed_radio_groups:
                    continue
                processed_radio_groups.add(name)
                
                # Find all radios with this name
                radios = form.find_all("input", {"type": "radio", "name": name})
                options = []
                for r in radios:
                    opt_label = None
                    # Try aria-label
                    opt_label = r.get("aria-label")
                    # Try associated label
                    if not opt_label and r.get("id"):
                        lbl = soup.find("label", {"for": r["id"]})
                        if lbl:
                            opt_label = lbl.get_text(strip=True)
                    # Try parent label
                    if not opt_label:
                        parent_label = r.find_parent("label")
                        if parent_label:
                            opt_label = parent_label.get_text(strip=True)
                    # Fallback to value
                    if not opt_label:
                        opt_label = r.get("value", "")
                    
                    if opt_label:
                        options.append({"value": r.get("value", opt_label), "label": opt_label})
                
                # Find group label (legend, heading, etc.)
                group_label = None
                fieldset = tag.find_parent("fieldset")
                if fieldset:
                    legend = fieldset.find("legend")
                    if legend:
                        group_label = legend.get_text(strip=True)
                
                fields.append({
                    "name": name,
                    "type": "radio",
                    "tagName": "radio-group",
                    "label": group_label or name.replace("_", " ").title(),
                    "required": any(r.has_attr("required") for r in radios),
                    "hidden": False,
                    "options": options
                })
                continue
            
            # Handle checkbox groups
            if field_type == "checkbox":
                checkboxes = form.find_all("input", {"type": "checkbox", "name": name})
                
                if len(checkboxes) > 1:
                    if name in processed_checkbox_groups:
                        continue
                    processed_checkbox_groups.add(name)
                    
                    options = []
                    for c in checkboxes:
                        opt_label = c.get("aria-label")
                        if not opt_label and c.get("id"):
                            lbl = soup.find("label", {"for": c["id"]})
                            if lbl:
                                opt_label = lbl.get_text(strip=True)
                        if not opt_label:
                            opt_label = c.get("value", "")
                        if opt_label:
                            options.append({"value": c.get("value", opt_label), "label": opt_label})
                    
                    fields.append({
                        "name": name,
                        "type": "checkbox-group",
                        "tagName": "checkbox-group",
                        "label": name.replace("_", " ").title(),
                        "required": any(c.has_attr("required") for c in checkboxes),
                        "hidden": False,
                        "allows_multiple": True,
                        "options": options
                    })
                    continue
            
            # Standard fields (text, email, select, textarea, single checkbox)
            label = None
            if tag.get("id"):
                lbl = soup.find("label", {"for": tag["id"]})
                if lbl:
                    label = lbl.get_text(strip=True)
            
            field = {
                "name": name,
                "type": field_type,
                "tagName": tag.name,
                "label": label,
                "placeholder": tag.get("placeholder"),
                "required": tag.has_attr("required"),
                "hidden": False
            }
            
            if tag.name == "select":
                field["options"] = [{"value": o.get("value"), "label": o.get_text(strip=True)} 
                                    for o in tag.find_all("option")]
            
            fields.append(field)
        
        if fields:
            forms.append({"formIndex": idx, "action": form.get("action"), 
                         "method": (form.get("method") or "GET").upper(), "fields": fields})
    
    return forms


async def _extract_google_forms(page) -> List[Dict]:
    """Specialized Google Forms extraction with robust selectors."""
    print("🔍 Extracting Google Form...")
    
    return await page.evaluate("""
        () => {
            const getText = el => el ? (el.innerText || el.textContent || '').trim() : '';
            
            // Get title
            const titleEl = document.querySelector('[role="heading"], .freebirdFormviewerViewHeaderTitle, h1');
            const formTitle = getText(titleEl);
            
            const form = {
                formIndex: 0, action: location.href, method: 'POST',
                id: 'google-form', name: formTitle || 'Google Form',
                title: formTitle, fields: []
            };
            
            // Find questions using multiple selectors for robustness
            // .Qr7Oae is the main question container class
            // [role="listitem"] is a backup selector
            let questions = document.querySelectorAll('.Qr7Oae');
            if (questions.length === 0) {
                questions = document.querySelectorAll('[role="listitem"]');
            }
            
            console.log(`Found ${questions.length} question containers`);
            
            questions.forEach((q, idx) => {
                // Get label - try multiple selectors for just the QUESTION TEXT (not options)
                // Google Forms structure:
                // - .M7eMe contains the question title
                // - .gubaDc contains the description/helper text
                // - Radio options are inside [role="radiogroup"] or similar
                
                let label = '';
                
                // Method 1: Try the specific title span first (most reliable)
                const titleSpan = q.querySelector('.M7eMe > span, .M7eMe');
                if (titleSpan) {
                    // Get only the DIRECT text, not child elements
                    // Clone the element and remove child elements to get just the text
                    const clone = titleSpan.cloneNode(true);
                    // Remove any child elements that might contain options
                    clone.querySelectorAll('[role="radio"], [role="checkbox"], .docssharedWizToggleLabeledContainer, input').forEach(el => el.remove());
                    label = getText(clone);
                }
                
                // Method 2: Try data-params attribute which often has the question text
                if (!label) {
                    const paramEl = q.querySelector('[data-params]');
                    if (paramEl) {
                        try {
                            const params = paramEl.getAttribute('data-params');
                            // Google Forms encodes the question text in data-params
                            const match = params.match(/\[null,"([^"]+)"/);
                            if (match) label = match[1];
                        } catch(e) {}
                    }
                }
                
                // Method 3: Find the first text block before any form controls
                if (!label) {
                    const children = q.children;
                    for (let i = 0; i < children.length; i++) {
                        const child = children[i];
                        if (!child.querySelector('[role="radio"], [role="checkbox"], input, select, textarea')) {
                            const childText = getText(child);
                            if (childText && childText.length > 0 && childText.length < 500) {
                                label = childText;
                                break;
                            }
                        }
                    }
                }
                
                // Clean up the label
                // Remove asterisks and "Required" text
                label = label.replace(/\*$/, '').replace(/\s*\(Required\)\s*/gi, '').trim();
                
                // IMPORTANT: Remove any option labels that might have leaked into the label
                // If options are extracted later, we'll strip them from the label
                
                // Fallback
                if (!label) label = `Question ${idx + 1}`;
                
                // Check required (asterisk presence or aria-label)
                const required = q.innerHTML.includes('*') || 
                                q.querySelector('[aria-label*="Required"]') !== null ||
                                q.innerHTML.includes('required');
                
                // Detect field type using robust selectors
                // IMPORTANT: Check radio/checkbox FIRST as they may coexist with text inputs
                const radioInputs = q.querySelectorAll('[role="radio"]');
                const checkboxInputs = q.querySelectorAll('[role="checkbox"]');
                const selectEl = q.querySelector('select, [role="listbox"]');
                
                // Google Forms date pickers - they do NOT use input[type="date"]
                // They use text inputs with specific patterns or dedicated date widgets
                const isDateQuestion = label.toLowerCase().includes('date') ||
                                      q.querySelector('[data-date]') !== null ||
                                      q.querySelector('[aria-label*="Day"], [aria-label*="Month"], [aria-label*="Year"]') !== null ||
                                      q.querySelector('.qLWDgb') !== null; // Google Forms date class
                
                // Text inputs - check AFTER determining if it's a date
                const textInput = q.querySelector('input.whsOnd, input[type="text"], input[type="email"]');
                const textArea = q.querySelector('textarea.KHxj8b, textarea');
                const fileInput = q.querySelector('input[type="file"]');
                
                let field = null;
                
                // Check for email input specifically
                const isEmail = textInput?.getAttribute('aria-label')?.toLowerCase().includes('email') ||
                               label.toLowerCase().includes('email');
                
                // PRIORITY ORDER: Radio > Checkbox > Dropdown > Date > File > Textarea > Text
                
                if (radioInputs.length > 0) {
                    // Extract radio options - Google Forms stores option text in aria-label or data-value
                    const options = Array.from(radioInputs).map((r, i) => {
                        // Primary: aria-label contains the option text
                        let optionLabel = r.getAttribute('aria-label') || '';
                        
                        // Fallback 1: data-value attribute
                        if (!optionLabel) {
                            optionLabel = r.getAttribute('data-value') || '';
                        }
                        
                        // Fallback 2: Look for span with option text inside the radio container
                        if (!optionLabel) {
                            const labelSpan = r.querySelector('span') || 
                                             r.closest('[role="presentation"]')?.querySelector('span');
                            optionLabel = labelSpan ? getText(labelSpan) : '';
                        }
                        
                        // Fallback 3: Adjacent sibling text
                        if (!optionLabel && r.nextElementSibling) {
                            optionLabel = getText(r.nextElementSibling);
                        }
                        
                        // Fallback 4: Parent's direct text
                        if (!optionLabel) {
                            // Get just this option's container, not the whole question
                            const optContainer = r.closest('.docssharedWizToggleLabeledContainer, .SG0AAe, [data-answer-value]');
                            if (optContainer) {
                                optionLabel = getText(optContainer);
                            }
                        }
                        
                        return {
                            value: optionLabel || `Option ${i + 1}`,
                            label: optionLabel || `Option ${i + 1}`
                        };
                    }).filter(o => o.label && o.label.length > 0 && o.label !== o.value.slice(0, 6) + '...');
                    
                    // Log for debugging
                    console.log(`Radio options found: ${options.map(o => o.label).join(', ')}`);
                    
                    field = {
                        name: `radio_${idx}`,
                        type: 'radio',
                        tagName: 'radio-group',
                        options: options
                    };
                } else if (checkboxInputs.length > 0) {
                    // Extract checkbox options - same approach as radio buttons
                    const options = Array.from(checkboxInputs).map((c, i) => {
                        // Primary: aria-label contains the option text
                        let optionLabel = c.getAttribute('aria-label') || '';
                        
                        // Fallback 1: data-value attribute
                        if (!optionLabel) {
                            optionLabel = c.getAttribute('data-value') || '';
                        }
                        
                        // Fallback 2: Look for text in the container
                        if (!optionLabel) {
                            const optContainer = c.closest('.docssharedWizToggleLabeledContainer, .SG0AAe, [data-answer-value]');
                            if (optContainer) {
                                optionLabel = getText(optContainer);
                            }
                        }
                        
                        // Fallback 3: Parent element text
                        if (!optionLabel) {
                            optionLabel = getText(c.parentElement);
                        }
                        
                        return {
                            value: optionLabel || `Option ${i + 1}`,
                            label: optionLabel || `Option ${i + 1}`
                        };
                    }).filter(o => o.label && o.label.length > 0);
                    
                    console.log(`Checkbox options found: ${options.map(o => o.label).join(', ')}`);
                    
                    field = {
                        name: `checkbox_${idx}`,
                        type: 'checkbox-group',
                        tagName: 'checkbox-group',
                        allows_multiple: true,
                        options: options
                    };
                } else if (selectEl) {
                    const options = selectEl.tagName === 'SELECT' 
                        ? Array.from(selectEl.options).map(o => ({value: o.value, label: o.text}))
                        : Array.from(q.querySelectorAll('[role="option"], [data-value]')).map(o => ({
                            value: o.getAttribute('data-value') || getText(o),
                            label: getText(o)
                        }));
                    field = {
                        name: selectEl.name || `dropdown_${idx}`,
                        type: 'dropdown', tagName: 'select', options
                    };
                } else if (isDateQuestion) {
                    // Google Forms date picker
                    field = { 
                        name: `date_${idx}`, 
                        type: 'date', 
                        tagName: 'input',
                        is_google_date: true
                    };
                    console.log(`Date field detected: ${label}`);
                } else if (fileInput) {
                    field = { 
                        name: fileInput.name || `file_${idx}`, type: 'file', tagName: 'input',
                        accept: fileInput.accept, multiple: fileInput.multiple 
                    };
                } else if (textArea) {
                    field = {
                        name: textArea.name || `textarea_${idx}`,
                        type: 'textarea',
                        tagName: 'textarea'
                    };
                } else if (textInput) {
                    field = {
                        name: textInput.name || `text_${idx}`,
                        type: isEmail ? 'email' : 'text',
                        tagName: 'input'
                    };
                }
                
                if (field) {
                    // CRITICAL: Clean up label by removing option labels that may have leaked
                    // This happens when the question container's innerText includes the options
                    if (field.options && field.options.length > 0) {
                        let cleanLabel = label;
                        for (const opt of field.options) {
                            // Remove option labels from the main label
                            if (opt.label) {
                                // Remove the option text (handles cases like "Freshman Sophomore...")
                                cleanLabel = cleanLabel.replace(new RegExp('\\\\b' + opt.label.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + '\\\\b', 'gi'), '');
                            }
                        }
                        // Also remove common trailing patterns
                        cleanLabel = cleanLabel
                            .replace(/Other:\s*$/i, '')
                            .replace(/\s*\(This field is required\)\s*/gi, '')
                            .replace(/\s{2,}/g, ' ')
                            .trim();
                        
                        // If we cleaned up the label, use it
                        if (cleanLabel && cleanLabel.length > 5) {
                            label = cleanLabel;
                        }
                        
                        console.log(`Cleaned label: "${label}"`);
                    }
                    
                    field.label = label;
                    field.display_name = label;
                    field.required = required;
                    field.hidden = false;
                    form.fields.push(field);
                    console.log(`Found field: ${label} (${field.type}) with ${field.options ? field.options.length : 0} options`);
                }
            });
            
            console.log(`Total fields extracted: ${form.fields.length}`);
            return form.fields.length > 0 ? [form] : [];
        }
    """)


# ============================================================================
# PROCESSING & ENRICHMENT
# ============================================================================

def _process_forms(forms_data: List[Dict]) -> List[Dict]:
    """Process and enrich extracted forms with additional metadata."""
    result = []
    
    # Keywords indicating a form should be excluded (search/nav forms)
    EXCLUDE_KEYWORDS = ['search', 'login', 'signin', 'sign-in', 'newsletter', 'subscribe']
    
    for form in forms_data:
        # Skip forms that look like search/navigation forms
        form_id = (form.get("id") or "").lower()
        form_name = (form.get("name") or "").lower()
        form_action = (form.get("action") or "").lower()
        
        # Check if form ID/name/action contains exclude keywords
        combined = f"{form_id} {form_name} {form_action}"
        if any(kw in combined for kw in EXCLUDE_KEYWORDS):
            print(f"⏭️ Skipping excluded form: {form_id or form_name or form_action}")
            continue
        
        # Filter out hidden fields and get visible field count
        visible_fields = [f for f in form.get("fields", []) if not f.get("hidden") and f.get("type") != "hidden"]
        
        # Skip forms with only 1-2 visible fields (likely search/nav forms)
        if len(visible_fields) < 3:
            field_names = [f.get("name", "") for f in visible_fields]
            # Unless it's specifically a contact/feedback form with few fields
            if not any(kw in str(field_names).lower() for kw in ['message', 'comment', 'feedback', 'contact']):
                print(f"⏭️ Skipping small form with {len(visible_fields)} visible field(s)")
                continue
        
        processed = {
            "formIndex": form.get("formIndex"),
            "action": form.get("action"),
            "method": form.get("method", "POST"),
            "id": form.get("id"),
            "name": form.get("name"),
            "title": form.get("title"),
            "description": form.get("description"),
            "fields": []
        }
        
        for field in form.get("fields", []):
            field_type = field.get("type", "text")
            
            # Skip hidden fields entirely
            if field.get("hidden") or field_type == "hidden":
                continue
            
            # Skip honeypot fields (common spam traps)
            field_name_lower = (field.get("name") or "").lower()
            if "fax" in field_name_lower or "honeypot" in field_name_lower:
                continue
                
            enriched = {
                **field,
                "display_name": _generate_display_name(field),
                "purpose": _detect_purpose(field),
                "is_checkbox": field_type in ["checkbox", "checkbox-group"],
                "is_multiple_choice": field_type in ["radio", "radio-group", "mcq"],
                "is_dropdown": field_type in ["select", "dropdown"],
            }
            processed["fields"].append(enriched)
        
        if processed["fields"]:  # Only add if has visible fields
            result.append(processed)
    
    return result


def _detect_purpose(field: Dict) -> str:
    """Detect semantic purpose of a field."""
    text = f"{field.get('name', '')} {field.get('label', '')} {field.get('placeholder', '')}".lower()
    
    for purpose, keywords in FIELD_PATTERNS.items():
        if any(kw in text for kw in keywords):
            return purpose
    
    return field.get('type', 'text')


def _generate_display_name(field: Dict) -> str:
    """Generate user-friendly display name."""
    # Try label first
    if field.get('label'):
        return field['label'].strip()
    
    # Try placeholder
    if field.get('placeholder'):
        return field['placeholder'].strip()
    
    # Clean up field name
    name = field.get('name', 'Field')
    # Remove common prefixes
    for prefix in ['input_', 'field_', 'form_', 'data_', 'entry.']:
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
    
    # Convert to title case
    return name.replace('_', ' ').replace('-', ' ').title()


def _generate_speech(fields: List[Dict]) -> Dict:
    """Generate speech data for fields."""
    try:
        from services.voice.speech import SpeechService
        service = SpeechService(api_key=os.getenv('ELEVENLABS_API_KEY'))
        return service.generate_form_speech(fields)
    except Exception as e:
        print(f"⚠️ Speech generation failed: {e}")
        return {}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_template(forms: List[Dict]) -> Dict[str, Any]:
    """Create a template dictionary for form filling."""
    template = {"forms": []}
    
    for form in forms:
        form_tpl = {"form_index": form.get("formIndex"), "form_name": form.get("name"), "fields": {}}
        
        for field in form.get("fields", []):
            name = field.get("name")
            if not name:
                continue
            
            ftype = field.get("type", "text")
            
            field_template = {
                "display_name": field.get("display_name"),
                "type": ftype,
                "required": field.get("required", False)
            }
            
            if ftype == "checkbox":
                field_template["value"] = False
            elif ftype == "checkbox-group":
                field_template["value"] = []
                field_template["options"] = field.get("options", [])
            elif ftype in ["radio", "mcq", "dropdown", "select"]:
                field_template["value"] = None
                field_template["options"] = field.get("options", [])
            elif ftype == "scale":
                field_template["value"] = None
                field_template["scale_min"] = field.get("scale_min")
                field_template["scale_max"] = field.get("scale_max")
            elif ftype == "grid":
                field_template["value"] = {}
                field_template["rows"] = field.get("rows", [])
                field_template["columns"] = field.get("columns", [])
            elif ftype == "file":
                field_template["value"] = None
                field_template["accept"] = field.get("accept")
                field_template["multiple"] = field.get("multiple", False)
            else:
                field_template["value"] = ""
                
            form_tpl["fields"][name] = field_template
        
        template["forms"].append(form_tpl)
    
    return template


def validate_field_value(value: Any, field: Dict) -> tuple:
    """Validate a field value. Returns (is_valid, error_message)."""
    ftype = field.get("type", "text")
    required = field.get("required", False)
    
    # Required check
    if required and not value:
        return False, f"{field.get('display_name', 'Field')} is required"
    
    if not value:
        return True, ""
    
    # Type-specific validation
    if ftype == "email" and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', str(value)):
        return False, "Invalid email format"
    
    if ftype in ["tel", "phone"] and not re.match(r'^[\d\s\-\+\(\)]+$', str(value)):
        return False, "Invalid phone format"
    
    if ftype == "url" and not re.match(r'^https?://', str(value)):
        return False, "Invalid URL format"
    
    # Options validation
    if ftype in ["radio", "dropdown", "select"]:
        options = field.get("options", [])
        valid_values = [o.get("value") or o.get("label") for o in options]
        if value not in valid_values:
            return False, f"Invalid option: {value}"
    
    return True, ""


def get_form_summary(forms: List[Dict]) -> Dict:
    """Get a summary of forms."""
    total_fields = sum(len(f.get('fields', [])) for f in forms)
    required = sum(1 for f in forms for field in f.get('fields', []) if field.get('required'))
    
    return {
        "total_forms": len(forms),
        "total_fields": total_fields,
        "required_fields": required,
        "field_types": list(set(field.get('type') for f in forms for field in f.get('fields', [])))
    }


# Backward-compatible aliases
def get_required_fields(forms: List[Dict]) -> List[Dict]:
    return [f for form in forms for f in form.get('fields', []) if f.get('required')]

def get_mcq_fields(forms: List[Dict]) -> List[Dict]:
    return [f for form in forms for f in form.get('fields', []) if f.get('type') in ['radio', 'mcq']]

def get_dropdown_fields(forms: List[Dict]) -> List[Dict]:
    return [f for form in forms for f in form.get('fields', []) if f.get('type') in ['select', 'dropdown']]

def format_field_value(value: str, purpose: str, field_type: str = None) -> str:
    if not value:
        return value
    if purpose == 'email':
        return value.lower().replace(' ', '')
    if purpose in ['phone', 'mobile']:
        return re.sub(r'[^\d+]', '', value)
    return value.strip()

def format_email_input(text: str) -> str:
    """Format text for email fields"""
    return format_field_value(text, 'email')

# Legacy alias
async def _extract_standard_forms_from_frame(frame):
    return await _extract_standard_forms(frame)

def get_field_speech(field_name: str, speech_data: dict) -> bytes:
    """Get speech audio for a specific field"""
    if not speech_data:
        return None
    return speech_data.get(field_name)