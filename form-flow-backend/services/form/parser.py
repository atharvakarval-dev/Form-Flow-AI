"""
Form Parser - Modular Architecture
Scrapes form fields from any URL including Google Forms with iframe support.

This is the main orchestrator that uses:
- utils/ - Constants, page helpers
- detectors/ - CAPTCHA, dependencies
- extractors/ - Standard forms, Google Forms, special fields, wizards
- processors/ - Field enrichment and utilities
"""

from playwright.async_api import async_playwright
from typing import List, Dict, Any
import asyncio
import os

# Import from modular packages
from .utils import (
    STEALTH_SCRIPT,
    BROWSER_ARGS,
    FIELD_PATTERNS,
    wait_for_dom_stability,
    expand_hidden_sections,
    scroll_and_detect_lazy_fields,
)

from .detectors import (
    detect_captcha,
    detect_login_required,
    map_conditional_fields,
    detect_chained_selects,
)

from .extractors import (
    # Standard extraction
    extract_standard_forms,
    # Google Forms
    wait_for_google_form,
    extract_google_forms,
    # Alternative
    extract_from_shadow_dom,
    extract_formless_containers,
    extract_custom_dropdown_options,
    extract_all_frames,
    extract_with_beautifulsoup,
    # Special fields
    extract_rich_text_editors,
    extract_dropzones,
    extract_range_sliders,
    extract_autocomplete_fields,
    extract_custom_date_pickers,
    # Wizard
    detect_wizard_form,
    navigate_wizard_and_extract,
)

from .processors import (
    process_forms,
    generate_speech,
    create_template,
    validate_field_value,
    get_form_summary,
    get_required_fields,
    get_mcq_fields,
    get_dropdown_fields,
    format_field_value,
    format_email_input,
    get_field_speech,
)


# ============================================================================
# MAIN EXPORT FUNCTION
# ============================================================================

async def get_form_schema(url: str, generate_speech_audio: bool = True, wait_for_dynamic: bool = True) -> Dict[str, Any]:
    """
    Scrape form fields from a URL. Supports Google Forms and standard HTML forms.
    
    Enhanced with:
    - CAPTCHA detection (early exit)
    - Wizard/multi-step form navigation
    - Rich text editors, dropzones, sliders, autocomplete
    - Conditional field mapping
    - Shadow DOM support
    
    Args:
        url: Target URL to scrape
        generate_speech_audio: Whether to generate TTS for fields
        wait_for_dynamic: Whether to wait for JS content
    
    Returns:
        Dict with 'forms', 'url', 'is_google_form', 'total_forms', 'total_fields', 'enhancements'
    """
    is_google_form = 'docs.google.com/forms' in url
    enhancements = {
        'captcha_detected': False,
        'login_required': False,
        'is_wizard': False,
        'has_rich_text': False,
        'has_dropzones': False,
        'has_sliders': False,
        'has_autocomplete': False,
        'has_custom_datepickers': False,
        'conditional_fields': {}
    }
    
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
            
            # ================================================================
            # PHASE 0: Pre-flight checks (CAPTCHA, Login, Bot Protection)
            # ================================================================
            if not is_google_form:
                print("🔍 Running pre-flight checks...")
                
                # Check for CAPTCHA
                captcha_check = await detect_captcha(page)
                if captcha_check['hasCaptcha']:
                    print(f"⚠️ CAPTCHA detected: {captcha_check['type']}")
                    enhancements['captcha_detected'] = True
                    enhancements['captcha_type'] = captcha_check['type']
                
                # Check for login requirement
                login_check = await detect_login_required(page)
                if login_check['requiresLogin']:
                    print(f"⚠️ {login_check['message']}")
                    enhancements['login_required'] = True
            
            # ================================================================
            # PHASE 1: Wait for content to fully render
            # ================================================================
            if is_google_form:
                await wait_for_google_form(page)
            else:
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass
                
                print("⏳ Waiting for dynamic content...")
                await wait_for_dom_stability(page)
                
                print("📂 Expanding hidden sections...")
                expanded = await expand_hidden_sections(page)
                if expanded:
                    print(f"    ✓ Expanded {expanded} sections")
                
                print("📜 Scrolling to load lazy content...")
                new_fields = await scroll_and_detect_lazy_fields(page)
                if new_fields:
                    print(f"    ✓ Found {new_fields} lazy-loaded fields")
            
            print("✓ Page loaded, extracting forms...")
            
            # ================================================================
            # PHASE 2: Check for wizard/multi-step forms
            # ================================================================
            wizard_forms = []
            if not is_google_form:
                is_wizard = await detect_wizard_form(page)
                if is_wizard:
                    enhancements['is_wizard'] = True
                    wizard_forms = await navigate_wizard_and_extract(page, extract_standard_forms)
            
            # ================================================================
            # PHASE 3: Extract forms (standard + formless containers)
            # ================================================================
            if is_google_form:
                forms_data = await extract_google_forms(page)
            else:
                forms_data = await extract_all_frames(page, url, extract_standard_forms)
                forms_data.extend(wizard_forms)
            
            # If no forms found, try extracting from form-like containers
            if not is_google_form and len(forms_data) == 0:
                print(">> No <form> tags found, trying form-like containers...")
                forms_data = await extract_formless_containers(page)
            
            print(f"✓ Found {len(forms_data)} form(s)")
            
            # ================================================================
            # PHASE 4: Extract custom dropdown options by clicking them
            # ================================================================
            if not is_google_form:
                forms_data = await extract_custom_dropdown_options(page, forms_data)
            
            # ================================================================
            # PHASE 5: Extract special field types
            # ================================================================
            if not is_google_form and forms_data:
                print("🔧 Extracting special field types...")
                
                rich_text_fields = await extract_rich_text_editors(page)
                if rich_text_fields:
                    enhancements['has_rich_text'] = True
                    print(f"    ✓ Found {len(rich_text_fields)} rich text editor(s)")
                
                dropzone_fields = await extract_dropzones(page)
                if dropzone_fields:
                    enhancements['has_dropzones'] = True
                    print(f"    ✓ Found {len(dropzone_fields)} dropzone(s)")
                
                slider_fields = await extract_range_sliders(page)
                if slider_fields:
                    enhancements['has_sliders'] = True
                    print(f"    ✓ Found {len(slider_fields)} slider(s)")
                
                autocomplete_fields = await extract_autocomplete_fields(page)
                if autocomplete_fields:
                    enhancements['has_autocomplete'] = True
                    print(f"    ✓ Found {len(autocomplete_fields)} autocomplete field(s)")
                
                datepicker_fields = await extract_custom_date_pickers(page)
                if datepicker_fields:
                    enhancements['has_custom_datepickers'] = True
                    print(f"    ✓ Found {len(datepicker_fields)} custom date picker(s)")
                
                extra_fields = (rich_text_fields + dropzone_fields + slider_fields + 
                               autocomplete_fields + datepicker_fields)
                if extra_fields and forms_data:
                    forms_data[0]['fields'].extend(extra_fields)
            
            # ================================================================
            # PHASE 6: Detect field dependencies
            # ================================================================
            if not is_google_form and forms_data:
                print("🔗 Mapping field dependencies...")
                
                try:
                    conditional_deps = await map_conditional_fields(page, forms_data)
                    if conditional_deps:
                        enhancements['conditional_fields'] = conditional_deps
                        print(f"    ✓ Found {len(conditional_deps)} conditional triggers")
                except Exception as e:
                    print(f"    ⚠️ Conditional mapping skipped: {e}")
                
                try:
                    forms_data = await detect_chained_selects(page, forms_data)
                except Exception as e:
                    print(f"    ⚠️ Chained select detection skipped: {e}")
            
            # ================================================================
            # CLEANUP
            # ================================================================
            try:
                await page.unroute_all(behavior='ignoreErrors')
            except:
                pass
            await browser.close()
            
            # Process and enrich fields
            fields = process_forms(forms_data)
            
            result = {
                'forms': fields,
                'url': url,
                'is_google_form': is_google_form,
                'total_forms': len(fields),
                'total_fields': sum(len(f['fields']) for f in fields),
                'enhancements': enhancements
            }
            
            # Generate speech if requested
            if generate_speech_audio and fields:
                result['speech'] = generate_speech(fields)
            
            return result
            
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        import traceback
        traceback.print_exc()
        return {'forms': [], 'url': url, 'error': str(e), 'enhancements': enhancements}


# ============================================================================
# RE-EXPORTED UTILITIES (for backward compatibility)
# ============================================================================

# Re-export commonly used functions from processors
__all__ = [
    'get_form_schema',
    'create_template',
    'validate_field_value',
    'get_form_summary',
    'get_required_fields',
    'get_mcq_fields',
    'get_dropdown_fields',
    'format_field_value',
    'format_email_input',
    'get_field_speech',
    'FIELD_PATTERNS',
]