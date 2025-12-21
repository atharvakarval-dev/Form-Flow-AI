"""
Special fields extractor module.
Handles: Rich text editors, dropzones, sliders, autocomplete, date pickers.
"""

import json
from typing import List, Dict, Any
from ..utils.constants import (
    DROPZONE_SELECTORS,
    RANGE_SLIDER_SELECTORS,
    AUTOCOMPLETE_SELECTORS,
    DATE_PICKER_SELECTORS,
)


async def extract_rich_text_editors(page) -> List[Dict]:
    """
    Extract content and structure from rich text editors.
    Supports: TinyMCE, CKEditor, Quill, Draft.js, Tiptap, Froala
    """
    return await page.evaluate("""
        () => {
            const editors = [];
            const getText = el => (el?.innerText || el?.textContent || '').trim();
            
            // TinyMCE
            if (window.tinymce && window.tinymce.editors) {
                window.tinymce.editors.forEach((editor, idx) => {
                    try {
                        editors.push({
                            type: 'rich-text',
                            subtype: 'tinymce',
                            name: editor.id || `tinymce_${idx}`,
                            tagName: 'rich-text-editor',
                            label: editor.getElement()?.getAttribute('aria-label') || 
                                   document.querySelector(`label[for="${editor.id}"]`)?.textContent?.trim() || 
                                   'Rich Text',
                            value: editor.getContent(),
                            plainText: editor.getContent({format: 'text'}),
                            required: false,
                            hidden: false
                        });
                    } catch(e) {}
                });
            }
            
            // CKEditor 4
            if (window.CKEDITOR && window.CKEDITOR.instances) {
                for (let name in window.CKEDITOR.instances) {
                    try {
                        const editor = window.CKEDITOR.instances[name];
                        editors.push({
                            type: 'rich-text',
                            subtype: 'ckeditor4',
                            name: name,
                            tagName: 'rich-text-editor',
                            label: editor.element?.getAttribute('aria-label') || 'Rich Text',
                            value: editor.getData(),
                            plainText: editor.document?.getBody()?.getText() || '',
                            required: false,
                            hidden: false
                        });
                    } catch(e) {}
                }
            }
            
            // CKEditor 5
            document.querySelectorAll('.ck-editor__editable').forEach((el, idx) => {
                if (el.ckeditorInstance) {
                    try {
                        editors.push({
                            type: 'rich-text',
                            subtype: 'ckeditor5',
                            name: el.id || `ckeditor5_${idx}`,
                            tagName: 'rich-text-editor',
                            label: el.getAttribute('aria-label') || 'Rich Text',
                            value: el.ckeditorInstance.getData(),
                            plainText: getText(el),
                            required: false,
                            hidden: false
                        });
                    } catch(e) {}
                }
            });
            
            // Quill
            document.querySelectorAll('.ql-editor').forEach((el, idx) => {
                const container = el.closest('.ql-container');
                try {
                    const quillInstance = container?.__quill || window.Quill?.find(container);
                    editors.push({
                        type: 'rich-text',
                        subtype: 'quill',
                        name: el.id || container?.id || `quill_${idx}`,
                        tagName: 'rich-text-editor',
                        label: el.getAttribute('aria-label') || 'Rich Text',
                        value: el.innerHTML,
                        plainText: quillInstance?.getText?.() || getText(el),
                        required: false,
                        hidden: el.offsetParent === null
                    });
                } catch(e) {}
            });
            
            // Draft.js (React)
            document.querySelectorAll('[class*="DraftEditor"], [class*="draft-editor"]').forEach((el, idx) => {
                editors.push({
                    type: 'rich-text',
                    subtype: 'draftjs',
                    name: el.id || `draft_${idx}`,
                    tagName: 'rich-text-editor',
                    label: el.getAttribute('aria-label') || 'Rich Text',
                    value: el.innerHTML,
                    plainText: getText(el),
                    required: false,
                    hidden: el.offsetParent === null
                });
            });
            
            // Tiptap / ProseMirror
            document.querySelectorAll('.ProseMirror').forEach((el, idx) => {
                // Skip if already captured by other editors
                if (el.closest('.ql-editor, .ck-editor__editable')) return;
                
                editors.push({
                    type: 'rich-text',
                    subtype: 'tiptap',
                    name: el.id || `tiptap_${idx}`,
                    tagName: 'rich-text-editor',
                    label: el.getAttribute('aria-label') || 'Rich Text',
                    value: el.innerHTML,
                    plainText: getText(el),
                    required: false,
                    hidden: el.offsetParent === null
                });
            });
            
            // Froala
            document.querySelectorAll('.fr-element').forEach((el, idx) => {
                editors.push({
                    type: 'rich-text',
                    subtype: 'froala',
                    name: el.id || `froala_${idx}`,
                    tagName: 'rich-text-editor',
                    label: el.getAttribute('aria-label') || 'Rich Text',
                    value: el.innerHTML,
                    plainText: getText(el),
                    required: false,
                    hidden: el.offsetParent === null
                });
            });
            
            return editors;
        }
    """)


async def extract_dropzones(page) -> List[Dict]:
    """
    Extract drag-and-drop upload zones that don't use input[type=file].
    Supports: Dropzone.js, react-dropzone, vue-dropzone, uppy, filepond
    """
    selectors_js = json.dumps(DROPZONE_SELECTORS)
    
    return await page.evaluate(f"""
        () => {{
            const dropzones = [];
            const dropzoneSelectors = {selectors_js};
            const processed = new Set();
            
            dropzoneSelectors.forEach(selector => {{
                try {{
                    document.querySelectorAll(selector).forEach((el, idx) => {{
                        // Skip if not visible or already has file input
                        if (el.offsetParent === null) return;
                        if (el.querySelector('input[type="file"]')) return;
                        
                        // Skip duplicates
                        const id = el.id || el.className;
                        if (processed.has(id)) return;
                        processed.add(id);
                        
                        const rect = el.getBoundingClientRect();
                        if (rect.height < 30 || rect.width < 100) return;
                        
                        // Find label
                        let label = el.getAttribute('aria-label') || 
                                   el.querySelector('label, [class*="label"], [class*="title"]')?.textContent?.trim() ||
                                   el.querySelector('[class*="text"], [class*="message"]')?.textContent?.trim() ||
                                   'File Upload';
                        
                        // Clean up label
                        label = label.split('\\n')[0].substring(0, 50);
                        
                        dropzones.push({{
                            name: el.id || `dropzone_${{dropzones.length}}`,
                            type: 'file',
                            tagName: 'dropzone',
                            label: label,
                            required: el.hasAttribute('required') || label.includes('*'),
                            hidden: false,
                            multiple: el.hasAttribute('multiple') || el.classList.contains('multiple'),
                            accept: el.getAttribute('accept') || el.getAttribute('data-accept') || '*/*',
                            isDragDrop: true,
                            isCustomComponent: true
                        }});
                    }});
                }} catch(e) {{}}
            }});
            
            return dropzones;
        }}
    """)


async def extract_range_sliders(page) -> List[Dict]:
    """
    Extract range sliders including custom implementations.
    Supports: Native, noUiSlider, rc-slider, MUI Slider, Vuetify, Element Plus
    """
    sliders_js = json.dumps(RANGE_SLIDER_SELECTORS)
    
    return await page.evaluate(f"""
        () => {{
            const sliders = [];
            const processed = new Set();
            
            // Native HTML5 range inputs
            document.querySelectorAll('input[type="range"]').forEach(input => {{
                const name = input.name || input.id;
                if (name) processed.add(name);
                
                const label = input.getAttribute('aria-label') || 
                             document.querySelector(`label[for="${{input.id}}"]`)?.textContent?.trim() ||
                             'Range';
                
                sliders.push({{
                    name: name || `range_${{sliders.length}}`,
                    type: 'range',
                    tagName: 'input',
                    label: label.replace(/[*:]/g, '').trim(),
                    min: parseFloat(input.min) || 0,
                    max: parseFloat(input.max) || 100,
                    step: parseFloat(input.step) || 1,
                    value: parseFloat(input.value) || 50,
                    required: input.required,
                    hidden: input.offsetParent === null
                }});
            }});
            
            // Custom sliders
            const customSliderSelectors = {sliders_js};
            
            customSliderSelectors.forEach(selector => {{
                try {{
                    document.querySelectorAll(selector).forEach((el, idx) => {{
                        // Skip if contains native range input
                        if (el.querySelector('input[type="range"]')) return;
                        if (el.closest('input[type="range"]')) return;
                        
                        const hiddenInput = el.querySelector('input[type="hidden"]');
                        const name = hiddenInput?.name || el.id || `slider_${{sliders.length}}`;
                        
                        if (processed.has(name)) return;
                        processed.add(name);
                        
                        // Find label
                        const container = el.closest('.form-group, .form-field, [class*="field"]');
                        const label = container?.querySelector('label')?.textContent?.trim() ||
                                     el.getAttribute('aria-label') || 'Slider';
                        
                        sliders.push({{
                            name: name,
                            type: 'range',
                            tagName: 'custom-slider',
                            label: label.replace(/[*:]/g, '').trim(),
                            min: parseFloat(el.getAttribute('data-min') || el.getAttribute('min')) || 0,
                            max: parseFloat(el.getAttribute('data-max') || el.getAttribute('max')) || 100,
                            step: parseFloat(el.getAttribute('data-step') || el.getAttribute('step')) || 1,
                            value: parseFloat(hiddenInput?.value) || 50,
                            required: false,
                            hidden: el.offsetParent === null,
                            isCustomComponent: true
                        }});
                    }});
                }} catch(e) {{}}
            }});
            
            return sliders;
        }}
    """)


async def extract_autocomplete_fields(page) -> List[Dict]:
    """
    Detect autocomplete/typeahead fields (Google Places, custom autocomplete).
    """
    selectors_js = json.dumps(AUTOCOMPLETE_SELECTORS)
    
    return await page.evaluate(f"""
        () => {{
            const autocompletes = [];
            const processed = new Set();
            
            // Google Places Autocomplete
            if (window.google && window.google.maps && window.google.maps.places) {{
                document.querySelectorAll('input').forEach((input, idx) => {{
                    // Check if this input has Google Places attached
                    if (input.getAttribute('autocomplete') === 'off' && 
                        (input.className.includes('pac-target') || 
                         input.placeholder.toLowerCase().includes('address') ||
                         input.placeholder.toLowerCase().includes('location'))) {{
                        
                        const name = input.name || input.id || `places_${{autocompletes.length}}`;
                        if (processed.has(name)) return;
                        processed.add(name);
                        
                        autocompletes.push({{
                            name: name,
                            type: 'autocomplete',
                            subtype: 'google-places',
                            tagName: 'input',
                            label: input.placeholder || 
                                   document.querySelector(`label[for="${{input.id}}"]`)?.textContent?.trim() ||
                                   'Address',
                            required: input.required,
                            hidden: input.offsetParent === null,
                            isCustomComponent: true
                        }});
                    }}
                }});
            }}
            
            // Generic autocomplete
            const autocompleteSelectors = {selectors_js};
            
            autocompleteSelectors.forEach(selector => {{
                try {{
                    document.querySelectorAll(selector).forEach(input => {{
                        const name = input.name || input.id;
                        if (!name || processed.has(name)) return;
                        processed.add(name);
                        
                        autocompletes.push({{
                            name: name,
                            type: 'autocomplete',
                            subtype: 'generic',
                            tagName: 'input',
                            label: input.placeholder || 
                                   input.getAttribute('aria-label') || 
                                   document.querySelector(`label[for="${{input.id}}"]`)?.textContent?.trim() ||
                                   'Search',
                            required: input.required,
                            hidden: input.offsetParent === null,
                            datalist: input.getAttribute('list'),
                            isCustomComponent: true
                        }});
                    }});
                }} catch(e) {{}}
            }});
            
            return autocompletes;
        }}
    """)


async def extract_custom_date_pickers(page) -> List[Dict]:
    """
    Detect custom date/time pickers beyond native HTML5 date inputs.
    Supports: flatpickr, react-datepicker, vuejs-datepicker, Ant Design, MUI, etc.
    """
    selectors_js = json.dumps(DATE_PICKER_SELECTORS)
    
    return await page.evaluate(f"""
        () => {{
            const pickers = [];
            const processed = new Set();
            const datePickerSelectors = {selectors_js};
            
            datePickerSelectors.forEach(selector => {{
                try {{
                    document.querySelectorAll(selector).forEach((el, idx) => {{
                        const input = el.tagName === 'INPUT' ? el : el.querySelector('input');
                        if (!input) return;
                        
                        // Skip native date/time inputs
                        if (['date', 'time', 'datetime-local'].includes(input.type)) return;
                        
                        const name = input.name || input.id || `datepicker_${{pickers.length}}`;
                        if (processed.has(name)) return;
                        processed.add(name);
                        
                        // Detect if it's date, time, or datetime
                        const labelText = (input.placeholder || input.getAttribute('aria-label') || '').toLowerCase();
                        const containerText = el.closest('[class*="date"], [class*="time"]')?.className || '';
                        
                        let pickerType = 'date';
                        if ((labelText.includes('time') || containerText.includes('time')) && 
                            !labelText.includes('date') && !containerText.includes('date')) {{
                            pickerType = 'time';
                        }}
                        if (labelText.includes('datetime') || containerText.includes('datetime') ||
                            (labelText.includes('date') && labelText.includes('time'))) {{
                            pickerType = 'datetime';
                        }}
                        
                        pickers.push({{
                            name: name,
                            type: pickerType,
                            tagName: 'datepicker',
                            label: input.placeholder || 
                                   input.getAttribute('aria-label') || 
                                   document.querySelector(`label[for="${{input.id}}"]`)?.textContent?.trim() ||
                                   (pickerType === 'time' ? 'Time' : 'Date'),
                            required: input.required || input.getAttribute('aria-required') === 'true',
                            hidden: input.offsetParent === null,
                            format: input.getAttribute('data-date-format') || 
                                   input.getAttribute('data-format') || 
                                   'YYYY-MM-DD',
                            isCustomComponent: true
                        }});
                    }});
                }} catch(e) {{}}
            }});
            
            return pickers;
        }}
    """)
