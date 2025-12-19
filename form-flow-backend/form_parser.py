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
        await page.wait_for_selector('[role="list"], .freebirdFormviewerViewItemsItemItem, [jsname]', timeout=20000)
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
    except TimeoutError:
        print("⚠️ Timeout waiting for form elements")


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
    """Extract forms using JavaScript evaluation."""
    return await frame.evaluate("""
        () => {
            const getText = el => el ? (el.innerText || el.textContent || '').trim() : '';
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
            
            return Array.from(document.querySelectorAll('form')).map((form, idx) => ({
                formIndex: idx,
                action: form.action || null,
                method: (form.method || 'GET').toUpperCase(),
                id: form.id || null,
                name: form.name || null,
                fields: Array.from(form.querySelectorAll('input, select, textarea')).map(field => {
                    const type = field.type || field.tagName.toLowerCase();
                    const info = {
                        name: field.name || field.id || null,
                        type: type,
                        tagName: field.tagName.toLowerCase(),
                        label: findLabel(field, form),
                        placeholder: field.placeholder || null,
                        required: field.required || field.hasAttribute('required'),
                        hidden: type === 'hidden' || !isVisible(field),
                        value: field.value || null,
                        disabled: field.disabled,
                        readonly: field.readOnly
                    };
                    
                    // Handle select options
                    if (field.tagName === 'SELECT') {
                        info.options = Array.from(field.options).filter(o => o.value).map(o => ({
                            value: o.value, label: o.text.trim(), selected: o.selected
                        }));
                    }
                    
                    // Handle radio/checkbox groups
                    if (type === 'radio' || type === 'checkbox') {
                        info.checked = field.checked;
                    }
                    
                    return info;
                }).filter(f => f.name && f.type !== 'submit' && f.type !== 'button')
            })).filter(f => f.fields.length > 0);
        }
    """)


def _extract_with_beautifulsoup(html: str) -> List[Dict]:
    """BeautifulSoup fallback extraction."""
    soup = BeautifulSoup(html, "html.parser")
    forms = []
    
    for idx, form in enumerate(soup.find_all("form")):
        fields = []
        for tag in form.find_all(["input", "select", "textarea"]):
            name = tag.get("name") or tag.get("id")
            if not name or tag.get("type") in ["submit", "button", "hidden"]:
                continue
            
            label = None
            if tag.get("id"):
                lbl = soup.find("label", {"for": tag["id"]})
                if lbl:
                    label = lbl.get_text(strip=True)
            
            field = {
                "name": name,
                "type": tag.get("type", tag.name),
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
    """Specialized Google Forms extraction."""
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
            
            // Find questions
            const questions = document.querySelectorAll('[role="listitem"], .freebirdFormviewerViewItemsItemItem');
            
            questions.forEach((q, idx) => {
                // Get label
                const labelEl = q.querySelector('[role="heading"], .M7eMe, .geS5n, [dir="auto"]');
                const label = getText(labelEl) || `Question ${idx + 1}`;
                
                // Check required
                const required = q.innerHTML.includes('Required') || 
                                q.querySelector('[aria-label*="Required"]') !== null;
                
                // Detect field type
                const textInput = q.querySelector('input[type="text"], textarea');
                const radioInputs = q.querySelectorAll('input[type="radio"], [role="radio"]');
                const checkboxInputs = q.querySelectorAll('input[type="checkbox"], [role="checkbox"]');
                const selectEl = q.querySelector('select, [role="listbox"]');
                const dateInput = q.querySelector('input[type="date"]');
                const fileInput = q.querySelector('input[type="file"]');
                
                let field = null;
                
                if (textInput) {
                    field = {
                        name: textInput.name || `text_${idx}`,
                        type: textInput.tagName === 'TEXTAREA' ? 'textarea' : 'text',
                        tagName: textInput.tagName.toLowerCase()
                    };
                } else if (radioInputs.length > 0) {
                    field = {
                        name: radioInputs[0]?.name || `radio_${idx}`,
                        type: 'radio', tagName: 'radio-group',
                        options: Array.from(radioInputs).map((r, i) => ({
                            value: r.value || getText(r.closest('[role="radio"]') || r.parentElement) || `opt_${i}`,
                            label: getText(r.closest('[role="radio"]') || r.parentElement) || r.value
                        }))
                    };
                } else if (checkboxInputs.length > 0) {
                    field = {
                        name: checkboxInputs[0]?.name || `checkbox_${idx}`,
                        type: 'checkbox-group', tagName: 'checkbox-group',
                        allows_multiple: true,
                        options: Array.from(checkboxInputs).map((c, i) => ({
                            value: c.value || getText(c.closest('[role="checkbox"]') || c.parentElement) || `opt_${i}`,
                            label: getText(c.closest('[role="checkbox"]') || c.parentElement) || c.value
                        }))
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
                } else if (dateInput) {
                    field = { name: dateInput.name || `date_${idx}`, type: 'date', tagName: 'input' };
                } else if (fileInput) {
                    field = { 
                        name: fileInput.name || `file_${idx}`, type: 'file', tagName: 'input',
                        accept: fileInput.accept, multiple: fileInput.multiple 
                    };
                }
                
                if (field) {
                    field.label = label;
                    field.required = required;
                    field.hidden = false;
                    form.fields.push(field);
                }
            });
            
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
        from speech_service import SpeechService
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