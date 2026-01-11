"""
Form Parser - Optimized & Refactored
Scrapes form fields from any URL including Google Forms with iframe support.
"""

from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import asyncio
from asyncio import TimeoutError
import re
import os
import sys

# Import modular extractors
from services.form.extractors.standard import extract_standard_forms as _modular_extract_standard
from services.form.extractors.google_forms import extract_google_forms as _modular_extract_google, wait_for_google_form as _modular_wait_google

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
    
    On Windows, uses sync Playwright via asyncio.to_thread() to bypass
    asyncio subprocess limitations in Python 3.14.
    
    Args:
        url: Target URL to scrape
        generate_speech: Whether to generate TTS for fields
        wait_for_dynamic: Whether to wait for JS content
    
    Returns:
        Dict with 'forms', 'url', 'is_google_form', 'total_forms', 'total_fields'
    """
    # On Windows, use sync Playwright to avoid asyncio subprocess issues
    if sys.platform == 'win32':
        return await asyncio.to_thread(_sync_get_form_schema, url, generate_speech, wait_for_dynamic)
    
    # Non-Windows: use async Playwright as before
    return await _async_get_form_schema(url, generate_speech, wait_for_dynamic)


def _sync_get_form_schema(url: str, generate_speech: bool = True, wait_for_dynamic: bool = True) -> Dict[str, Any]:
    """Sync Playwright implementation for Windows."""
    is_google_form = 'docs.google.com/forms' in url
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=BROWSER_ARGS)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US"
            )
            context.add_init_script(STEALTH_SCRIPT)
            
            page = context.new_page()
            page.route("**/*", lambda r: r.abort() if r.request.resource_type in {"media", "font"} else r.continue_())
            
            print(f"🔗 Navigating to {'Google Form' if is_google_form else 'page'}...")
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            
            # Wait for content
            if is_google_form:
                _sync_wait_for_google_form(page)
            else:
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass
                import time
                time.sleep(2)
            
            print("✓ Page loaded, extracting forms...")
            
            # Extract forms using sync JS evaluation
            html_content = page.content()
            forms_data = _extract_with_beautifulsoup(html_content)
            
            # Also try the JS extraction
            if not forms_data:
                forms_data = page.evaluate(_get_standard_extraction_js())
            
            print(f"✓ Found {len(forms_data)} form(s)")
            
            browser.close()
            
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


def _sync_wait_for_google_form(page):
    """Sync version of waiting for Google Form content."""
    import time
    selectors = ['.Qr7Oae', '[role="listitem"]', '.freebirdFormviewerViewNumberedItemContainer']
    for selector in selectors:
        try:
            page.wait_for_selector(selector, timeout=10000)
            return
        except:
            continue
    time.sleep(3)


def _get_standard_extraction_js():
    """Return the JS code for standard form extraction."""
    return """
        () => {
            const getText = el => el ? (el.innerText || el.textContent || '').trim() : '';
            
            return Array.from(document.querySelectorAll('form')).map((form, idx) => {
                const fields = [];
                
                Array.from(form.querySelectorAll('input, select, textarea')).forEach(field => {
                    const type = field.type || field.tagName.toLowerCase();
                    const name = field.name || field.id;
                    
                    if (!name || type === 'submit' || type === 'button' || type === 'hidden') return;
                    
                    if (field.tagName === 'SELECT') {
                        fields.push({
                            name: name, type: 'dropdown', tagName: 'select',
                            label: getText(form.querySelector(`label[for="${field.id}"]`)) || name,
                            required: field.required,
                            options: Array.from(field.options).filter(o => o.value).map(o => ({
                                value: o.value, label: o.text.trim()
                            }))
                        });
                        return;
                    }
                    
                    fields.push({
                        name: name, type: type, tagName: field.tagName.toLowerCase(),
                        label: getText(form.querySelector(`label[for="${field.id}"]`)) || field.placeholder || name,
                        placeholder: field.placeholder || null,
                        required: field.required
                    });
                });
                
                return {
                    formIndex: idx,
                    action: form.action || null,
                    method: (form.method || 'GET').toUpperCase(),
                    fields: fields
                };
            }).filter(f => f.fields.length > 0);
        }
    """


async def _async_get_form_schema(url: str, generate_speech: bool = True, wait_for_dynamic: bool = True) -> Dict[str, Any]:
    """Original async Playwright implementation for non-Windows platforms."""
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
            
            # Click custom dropdowns to extract options
            if not is_google_form and forms_data:
                print("🔽 Extracting custom dropdown options...")
                forms_data = await _extract_custom_dropdown_options(page, forms_data)
            
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
    """Wait for Google Form content to load. Delegates to modular extractor."""
    await _modular_wait_google(page)


async def _extract_custom_dropdown_options(page, forms_data: List[Dict]) -> List[Dict]:
    """
    Click on custom dropdowns (Ant Design, React Select, etc.) to reveal their options.
    Updates the forms_data with extracted options.
    """
    try:
        # Find all custom dropdown fields
        custom_dropdowns = []
        for form in forms_data:
            for field in form.get('fields', []):
                if field.get('is_custom_dropdown') or (field.get('type') == 'dropdown' and field.get('tagName') == 'custom-select'):
                    custom_dropdowns.append(field)
        
        if not custom_dropdowns:
            return forms_data
        
        print(f"   Found {len(custom_dropdowns)} custom dropdown(s) to expand...")
        
        # Click each dropdown to reveal options
        for field in custom_dropdowns:
            try:
                label = field.get('label', '')
                
                # Find the dropdown element by searching for its label
                dropdown = await page.query_selector(f'.ant-select:has(.ant-select-selection-placeholder:has-text("{label}"))')
                
                if not dropdown:
                    # Try alternative selectors
                    dropdown = await page.query_selector(f'.ant-form-item:has-text("{label}") .ant-select')
                
                if not dropdown:
                    dropdown = await page.query_selector(f'[role="combobox"][aria-label*="{label}"]')
                
                if dropdown:
                    # Click to open dropdown
                    await dropdown.click()
                    await asyncio.sleep(0.5)  # Wait for options to render
                    
                    # Extract options from the dropdown panel
                    options = await page.evaluate("""
                        () => {
                            const getText = el => el ? (el.innerText || el.textContent || '').trim() : '';
                            const optionEls = document.querySelectorAll(
                                '.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option, ' +
                                '.ant-select-dropdown:not(.ant-select-dropdown-hidden) [role="option"], ' +
                                '.rc-virtual-list-holder-inner .ant-select-item'
                            );
                            return Array.from(optionEls).map(o => ({
                                value: o.getAttribute('data-value') || o.getAttribute('title') || getText(o),
                                label: getText(o)
                            })).filter(o => o.label && o.label.length > 0);
                        }
                    """)
                    
                    if options:
                        field['options'] = options
                        print(f"   ✓ Extracted {len(options)} options for '{label}'")
                    
                    # Close dropdown by clicking elsewhere or pressing Escape
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(0.3)
                    
            except Exception as e:
                print(f"   ⚠️ Could not extract options for dropdown: {e}")
                continue
        
    except Exception as e:
        print(f"   ⚠️ Custom dropdown extraction error: {e}")
    
    return forms_data


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
    """Extract forms using modular standard extractor."""
    return await _modular_extract_standard(frame)


# NOTE: The original inline JS extraction code has been moved to
# services/form/extractors/standard.py for better maintainability.
# The following placeholder prevents accidental usage of old code.
_STANDARD_EXTRACTION_MOVED = r"""
            const isVisible = el => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0' && el.getBoundingClientRect().height > 0;
            };
            
            const findLabel = (field, form) => {
                if (field.id) {
                    const lbl = form.querySelector(`label[for="${field.id}"]`);
                    if (lbl) return getText(lbl);
                }
                if (field.closest('label')) return getText(field.closest('label'));
                const prev = field.previousElementSibling;
                if (prev?.tagName === 'LABEL') return getText(prev);
                return field.getAttribute('aria-label') || field.placeholder || '';
            };
            
            const findGroupLabel = (inputs, form) => {
                if (inputs.length === 0) return '';
                const firstInput = inputs[0];
                
                const fieldset = firstInput.closest('fieldset');
                if (fieldset) {
                    const legend = fieldset.querySelector('legend');
                    if (legend) return getText(legend);
                }
                
                const container = firstInput.closest(
                    'fieldset, .form-group, .question, .field-wrapper, [role="group"], [role="radiogroup"], ' +
                    '.radio-group, .checkbox-group, .input-field, .field, .grouped, .form-field, ' +
                    '.field-container, .form-item, .form-row, [class*="mb-"], .callout'
                ) || firstInput.parentElement?.parentElement;
                
                if (container) {
                    const labelEl = container.querySelector(
                        'h1, h2, h3, h4, h5, h6, legend, label:not(:has(input)), .question-text, ' +
                        '.form-label, .control-label, .col-form-label, [class*="label"], ' +
                        '.field-label, .input-label, span.label, p.label, .title'
                    );
                    if (labelEl && !labelEl.querySelector('input, [role="radio"], [role="checkbox"]')) {
                        return getText(labelEl);
                    }
                }
                
                const ariaLabel = firstInput.closest('[aria-label]')?.getAttribute('aria-label');
                if (ariaLabel) return ariaLabel;
                
                const labelledBy = firstInput.getAttribute('aria-labelledby');
                if (labelledBy) {
                    const labelEl = document.getElementById(labelledBy);
                    if (labelEl) return getText(labelEl);
                }
                
                const dataLabel = firstInput.closest('[data-label]')?.getAttribute('data-label') ||
                                 firstInput.getAttribute('data-label');
                if (dataLabel) return dataLabel;
                
                const name = firstInput.name || '';
                return name.replace(/[_-]/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/\\[\\]/g, '').trim();
            };

            return Array.from(document.querySelectorAll('form')).map((form, idx) => {
                const fields = [];
                const processedRadioGroups = new Set();
                const processedCheckboxGroups = new Set();
                
                Array.from(form.querySelectorAll('input, select, textarea')).forEach(field => {
                    const type = field.type || field.tagName.toLowerCase();
                    const name = field.name || field.id;
                    
                    if (!name || type === 'submit' || type === 'button' || type === 'hidden') return;
                    
                    if (type === 'radio') {
                        if (processedRadioGroups.has(name)) return;
                        processedRadioGroups.add(name);
                        
                        const radios = Array.from(form.querySelectorAll(`input[type="radio"][name="${name}"]`));
                        const options = radios.map(r => {
                            let optLabel = r.getAttribute('aria-label') || '';
                            if (!optLabel && r.id) {
                                const lbl = form.querySelector(`label[for="${r.id}"]`);
                                if (lbl) optLabel = getText(lbl);
                            }
                            if (!optLabel) {
                                const parentLabel = r.closest('label');
                                if (parentLabel) optLabel = getText(parentLabel).replace(r.value, '').trim();
                            }
                            if (!optLabel && r.nextSibling) optLabel = (r.nextSibling.textContent || '').trim();
                            if (!optLabel) optLabel = r.value || '';
                            return { value: r.value || optLabel, label: optLabel || r.value };
                        }).filter(o => o.label);
                        
                        fields.push({
                            name: name, type: 'radio', tagName: 'radio-group',
                            label: findGroupLabel(radios, form),
                            required: radios.some(r => r.required),
                            hidden: !radios.some(r => isVisible(r)),
                            options: options
                        });
                        return;
                    }
                    
                    if (type === 'checkbox') {
                        const checkboxes = Array.from(form.querySelectorAll(`input[type="checkbox"][name="${name}"]`));
                        
                        if (checkboxes.length > 1) {
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
                                return { value: c.value || optLabel, label: optLabel || c.value, checked: c.checked };
                            }).filter(o => o.label);
                            
                            fields.push({
                                name: name, type: 'checkbox-group', tagName: 'checkbox-group',
                                label: findGroupLabel(checkboxes, form),
                                required: checkboxes.some(c => c.required),
                                hidden: !checkboxes.some(c => isVisible(c)),
                                allows_multiple: true, options: options
                            });
                        } else {
                            fields.push({
                                name: name, type: 'checkbox', tagName: 'input',
                                label: findLabel(field, form),
                                required: field.required,
                                hidden: !isVisible(field),
                                checked: field.checked
                            });
                        }
                        return;
                    }
                    
                    if (field.tagName === 'SELECT') {
                        fields.push({
                            name: name, type: 'dropdown', tagName: 'select',
                            label: findLabel(field, form),
                            required: field.required,
                            hidden: !isVisible(field),
                            options: Array.from(field.options).filter(o => o.value).map(o => ({
                                value: o.value, label: o.text.trim(), selected: o.selected
                            }))
                        });
                        return;
                    }
                    
                    fields.push({
                        name: name, type: type, tagName: field.tagName.toLowerCase(),
                        label: findLabel(field, form),
                        placeholder: field.placeholder || null,
                        required: field.required || field.hasAttribute('required'),
                        hidden: !isVisible(field),
                        value: field.value || null,
                        disabled: field.disabled,
                        readonly: field.readOnly
                    });
                });
                
                // ========================================================
                // CUSTOM DROPDOWNS (Ant Design, MUI, React Select, etc.)
                // These don't use standard <select> tags
                // ========================================================
                const processedCustomDropdowns = new Set();
                const customDropdownSelectors = [
                    '.ant-select',           // Ant Design
                    '[role="combobox"]',     // ARIA combobox
                    '.react-select',         // React Select
                    '.Select',               // React Select (old)
                    '.MuiSelect-root',       // Material UI
                    '.vs__dropdown-toggle',  // Vue Select
                    '.choices',              // Choices.js
                    '.select2-container',    // Select2
                    '[data-select]',         // Generic data attribute
                ];
                
                form.querySelectorAll(customDropdownSelectors.join(', ')).forEach((dropdown, dIdx) => {
                    // Find the label for this dropdown
                    let label = '';
                    
                    // Try to find associated label
                    const container = dropdown.closest('.ant-form-item, .form-group, .form-item, .field-wrapper, [class*="form-item"]');
                    if (container) {
                        const labelEl = container.querySelector('label, .ant-form-item-label, .form-label, [class*="label"]');
                        if (labelEl) label = getText(labelEl).replace(/\*$/, '').trim();
                    }
                    
                    // Try aria-label
                    if (!label) {
                        label = dropdown.getAttribute('aria-label') || '';
                    }
                    
                    // Try placeholder text
                    if (!label) {
                        const placeholder = dropdown.querySelector('.ant-select-selection-placeholder, [class*="placeholder"]');
                        if (placeholder) label = getText(placeholder);
                    }
                    
                    // Skip if no label found or already processed
                    if (!label || processedCustomDropdowns.has(label)) return;
                    processedCustomDropdowns.add(label);
                    
                    // Check if required (asterisk in label or aria-required)
                    const isRequired = container?.innerHTML?.includes('*') || 
                                      dropdown.getAttribute('aria-required') === 'true' ||
                                      container?.querySelector('.ant-form-item-required') !== null;
                    
                    // Try to get options (may need to click to populate)
                    let options = [];
                    
                    // Look for already rendered options
                    const optionEls = document.querySelectorAll('.ant-select-item-option, [role="option"], .ant-select-dropdown .ant-select-item');
                    if (optionEls.length > 0) {
                        options = Array.from(optionEls).map(o => ({
                            value: o.getAttribute('data-value') || getText(o),
                            label: getText(o)
                        })).filter(o => o.label);
                    }
                    
                    fields.push({
                        name: `custom_dropdown_${dIdx}`,
                        type: 'dropdown',
                        tagName: 'custom-select',
                        label: label,
                        required: isRequired,
                        hidden: !isVisible(dropdown),
                        options: options,
                        is_custom_dropdown: true
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
"""


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
            
            if field_type == "radio":
                if name in processed_radio_groups:
                    continue
                processed_radio_groups.add(name)
                
                radios = form.find_all("input", {"type": "radio", "name": name})
                options = []
                for r in radios:
                    opt_label = r.get("aria-label")
                    if not opt_label and r.get("id"):
                        lbl = soup.find("label", {"for": r["id"]})
                        if lbl:
                            opt_label = lbl.get_text(strip=True)
                    if not opt_label:
                        parent_label = r.find_parent("label")
                        if parent_label:
                            opt_label = parent_label.get_text(strip=True)
                    if not opt_label:
                        opt_label = r.get("value", "")
                    
                    if opt_label:
                        options.append({"value": r.get("value", opt_label), "label": opt_label})
                
                group_label = None
                fieldset = tag.find_parent("fieldset")
                if fieldset:
                    legend = fieldset.find("legend")
                    if legend:
                        group_label = legend.get_text(strip=True)
                
                fields.append({
                    "name": name, "type": "radio", "tagName": "radio-group",
                    "label": group_label or name.replace("_", " ").title(),
                    "required": any(r.has_attr("required") for r in radios),
                    "hidden": False, "options": options
                })
                continue
            
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
                        "name": name, "type": "checkbox-group", "tagName": "checkbox-group",
                        "label": name.replace("_", " ").title(),
                        "required": any(c.has_attr("required") for c in checkboxes),
                        "hidden": False, "allows_multiple": True, "options": options
                    })
                    continue
            
            label = None
            if tag.get("id"):
                lbl = soup.find("label", {"for": tag["id"]})
                if lbl:
                    label = lbl.get_text(strip=True)
            
            field = {
                "name": name, "id": tag.get("id"), "type": field_type, "tagName": tag.name,
                "label": label, "placeholder": tag.get("placeholder"),
                "required": tag.has_attr("required"), "hidden": False
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
    """Extract Google Forms using modular extractor."""
    return await _modular_extract_google(page)


# NOTE: The original inline JS extraction code has been moved to
# services/form/extractors/google_forms.py for better maintainability.
_GOOGLE_FORMS_EXTRACTION_MOVED = r"""
            const getText = el => el ? (el.innerText || el.textContent || '').trim() : '';
            const titleEl = document.querySelector('[role="heading"], .freebirdFormviewerViewHeaderTitle, h1');
            const formTitle = getText(titleEl);
            
            const form = {
                formIndex: 0, action: location.href, method: 'POST',
                id: 'google-form', name: formTitle || 'Google Form',
                title: formTitle, fields: []
            };
            
            let questions = document.querySelectorAll('.Qr7Oae');
            if (questions.length === 0) {
                questions = document.querySelectorAll('[role="listitem"]');
            }
            
            questions.forEach((q, idx) => {
                let label = '';
                
                const titleSpan = q.querySelector('.M7eMe > span, .M7eMe');
                if (titleSpan) {
                    const clone = titleSpan.cloneNode(true);
                    clone.querySelectorAll('[role="radio"], [role="checkbox"], .docssharedWizToggleLabeledContainer, input').forEach(el => el.remove());
                    label = getText(clone);
                }
                
                if (!label) {
                    const paramEl = q.querySelector('[data-params]');
                    if (paramEl) {
                        try {
                            const params = paramEl.getAttribute('data-params');
                            const match = params.match(/\\[null,"([^"]+)"/);
                            if (match) label = match[1];
                        } catch(e) {}
                    }
                }
                
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
                
                label = label.replace(/\\*$/, '').replace(/\\s*\\(Required\\)\\s*/gi, '').trim();
                if (!label) label = `Question ${idx + 1}`;
                
                const required = q.innerHTML.includes('*') || 
                                q.querySelector('[aria-label*="Required"]') !== null;
                
                const radioInputs = q.querySelectorAll('[role="radio"]');
                const checkboxInputs = q.querySelectorAll('[role="checkbox"]');
                const selectEl = q.querySelector('select, [role="listbox"]');
                const isDateQuestion = label.toLowerCase().includes('date') ||
                                      q.querySelector('[data-date]') !== null ||
                                      q.querySelector('.qLWDgb') !== null;
                const textInput = q.querySelector('input.whsOnd, input[type="text"], input[type="email"]');
                const textArea = q.querySelector('textarea.KHxj8b, textarea');
                const fileInput = q.querySelector('input[type="file"]');
                
                let field = null;
                const isEmail = textInput?.getAttribute('aria-label')?.toLowerCase().includes('email') ||
                               label.toLowerCase().includes('email');
                
                if (radioInputs.length > 0) {
                    const options = Array.from(radioInputs).map((r, i) => {
                        let optionLabel = r.getAttribute('aria-label') || r.getAttribute('data-value') || '';
                        if (!optionLabel) {
                            const labelSpan = r.querySelector('span') || r.closest('[role="presentation"]')?.querySelector('span');
                            optionLabel = labelSpan ? getText(labelSpan) : '';
                        }
                        if (!optionLabel && r.nextElementSibling) optionLabel = getText(r.nextElementSibling);
                        if (!optionLabel) {
                            const optContainer = r.closest('.docssharedWizToggleLabeledContainer, .SG0AAe, [data-answer-value]');
                            if (optContainer) optionLabel = getText(optContainer);
                        }
                        return { value: optionLabel || `Option ${i + 1}`, label: optionLabel || `Option ${i + 1}` };
                    }).filter(o => o.label && o.label.length > 0);
                    
                    field = { name: `radio_${idx}`, type: 'radio', tagName: 'radio-group', options: options };
                } else if (checkboxInputs.length > 0) {
                    const options = Array.from(checkboxInputs).map((c, i) => {
                        let optionLabel = c.getAttribute('aria-label') || c.getAttribute('data-value') || '';
                        if (!optionLabel) {
                            const optContainer = c.closest('.docssharedWizToggleLabeledContainer, .SG0AAe, [data-answer-value]');
                            if (optContainer) optionLabel = getText(optContainer);
                        }
                        if (!optionLabel) optionLabel = getText(c.parentElement);
                        return { value: optionLabel || `Option ${i + 1}`, label: optionLabel || `Option ${i + 1}` };
                    }).filter(o => o.label && o.label.length > 0);
                    
                    field = { name: `checkbox_${idx}`, type: 'checkbox-group', tagName: 'checkbox-group', allows_multiple: true, options: options };
                } else if (selectEl) {
                    const options = selectEl.tagName === 'SELECT' 
                        ? Array.from(selectEl.options).map(o => ({value: o.value, label: o.text}))
                        : Array.from(q.querySelectorAll('[role="option"], [data-value]')).map(o => ({
                            value: o.getAttribute('data-value') || getText(o), label: getText(o)
                        }));
                    field = { name: selectEl.name || `dropdown_${idx}`, type: 'dropdown', tagName: 'select', options };
                } else if (isDateQuestion) {
                    field = { name: `date_${idx}`, type: 'date', tagName: 'input', is_google_date: true };
                } else if (fileInput) {
                    field = { name: fileInput.name || `file_${idx}`, type: 'file', tagName: 'input', accept: fileInput.accept, multiple: fileInput.multiple };
                } else if (textArea) {
                    field = { name: textArea.name || `textarea_${idx}`, type: 'textarea', tagName: 'textarea' };
                } else if (textInput) {
                    field = { name: textInput.name || `text_${idx}`, type: isEmail ? 'email' : 'text', tagName: 'input' };
                }
                
                if (field) {
                    if (field.options && field.options.length > 0) {
                        let cleanLabel = label;
                        for (const opt of field.options) {
                            if (opt.label) {
                                cleanLabel = cleanLabel.replace(new RegExp('\\\\b' + opt.label.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + '\\\\b', 'gi'), '');
                            }
                        }
                        cleanLabel = cleanLabel.replace(/Other:\\s*$/i, '').replace(/\\s{2,}/g, ' ').trim();
                        if (cleanLabel && cleanLabel.length > 5) label = cleanLabel;
                    }
                    
                    field.label = label;
                    field.display_name = label;
                    field.required = required;
                    field.hidden = false;
                    form.fields.push(field);
                }
            });
            
            return form.fields.length > 0 ? [form] : [];
        }
"""


# ============================================================================
# PROCESSING & ENRICHMENT
# ============================================================================

def _process_forms(forms_data: List[Dict]) -> List[Dict]:
    """Process and enrich extracted forms with additional metadata."""
    result = []
    EXCLUDE_KEYWORDS = ['search', 'login', 'signin', 'sign-in', 'newsletter', 'subscribe']
    
    for form in forms_data:
        form_id = (form.get("id") or "").lower()
        form_name = (form.get("name") or "").lower()
        form_action = (form.get("action") or "").lower()
        
        combined = f"{form_id} {form_name} {form_action}"
        if any(kw in combined for kw in EXCLUDE_KEYWORDS):
            print(f"⏭️ Skipping excluded form: {form_id or form_name or form_action}")
            continue
        
        visible_fields = [f for f in form.get("fields", []) if not f.get("hidden") and f.get("type") != "hidden"]
        
        if len(visible_fields) < 3:
            field_names = [f.get("name", "") for f in visible_fields]
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
            
            if field.get("hidden") or field_type == "hidden":
                continue
            
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
        
        if processed["fields"]:
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
    if field.get('label'):
        return field['label'].strip()
    
    if field.get('placeholder'):
        return field['placeholder'].strip()
    
    name = field.get('name', 'Field')
    for prefix in ['input_', 'field_', 'form_', 'data_', 'entry.']:
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
    
    return name.replace('_', ' ').replace('-', ' ').title()


def _generate_speech(fields: List[Dict]) -> Dict:
    """Generate speech data for fields."""
    try:
        from services.voice.speech import SpeechService
        service = SpeechService(api_key=os.getenv('ELEVENLABS_API_KEY'))
        all_fields = [f for form in fields for f in form.get('fields', [])]
        return service.generate_form_speech(all_fields)
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
    
    if required and not value:
        return False, f"{field.get('display_name', 'Field')} is required"
    
    if not value:
        return True, ""
    
    if ftype == "email" and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', str(value)):
        return False, "Invalid email format"
    
    if ftype in ["tel", "phone"] and not re.match(r'^[\d\s\-\+\(\)]+$', str(value)):
        return False, "Invalid phone format"
    
    if ftype == "url" and not re.match(r'^https?://', str(value)):
        return False, "Invalid URL format"
    
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

def get_field_speech(field_name: str, speech_data: dict) -> bytes:
    """Get speech audio for a specific field"""
    if not speech_data:
        return None
    return speech_data.get(field_name)