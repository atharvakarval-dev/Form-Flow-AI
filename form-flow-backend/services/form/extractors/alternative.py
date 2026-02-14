"""
Alternative Extractors
Handles Shadow DOM, formless containers, custom dropdowns, and frame extraction.
"""

import asyncio
from typing import List, Dict
from bs4 import BeautifulSoup


async def extract_from_shadow_dom(page) -> List[Dict]:
    """
    Extract forms from within Shadow DOM components.
    Uses a recursive traversal to find inputs inside shadow roots.
    """
    return await page.evaluate("""
        () => {
            const getText = el => el ? (el.innerText || el.textContent || '').trim() : '';
            const isVisible = el => {
                if (!el) return false;
                try {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                } catch(e) { return false; }
            };
            
            const getAllElements = (root) => {
                const elements = [];
                const traverse = (node) => {
                    if (!node) return;
                    if (node.nodeType === 1) elements.push(node);
                    if (node.shadowRoot) traverse(node.shadowRoot);
                    if (node.children) {
                        Array.from(node.children).forEach(child => traverse(child));
                    }
                    if (node.childNodes) {
                        node.childNodes.forEach(child => {
                            if (child.nodeType === 1) traverse(child);
                        });
                    }
                };
                traverse(root);
                return elements;
            };
            
            const allElements = getAllElements(document.body);
            const shadowInputs = allElements.filter(el => 
                ['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) ||
                el.getAttribute('role') === 'combobox'
            ).filter(el => {
                let parent = el.parentNode;
                while (parent) {
                    if (parent.host) return true;
                    parent = parent.parentNode;
                }
                return false;
            });
            
            if (shadowInputs.length === 0) return [];
            
            const fields = [];
            const processedNames = new Set();
            
            shadowInputs.forEach(field => {
                const name = field.name || field.id || `shadow_field_${fields.length}`;
                if (processedNames.has(name)) return;
                if (field.type === 'hidden' || field.type === 'submit') return;
                
                processedNames.add(name);
                
                let label = field.getAttribute('aria-label') || '';
                if (!label) {
                    let root = field.getRootNode();
                    if (root && root !== document) {
                        const lbl = root.querySelector(`label[for="${field.id}"]`);
                        if (lbl) label = getText(lbl);
                    }
                }
                if (!label) label = field.placeholder || name;
                
                fields.push({
                    name: name,
                    type: field.type || field.tagName.toLowerCase(),
                    tagName: field.tagName.toLowerCase(),
                    label: label.replace(/[*:]$/g, '').trim(),
                    placeholder: field.placeholder || null,
                    required: field.required || field.getAttribute('aria-required') === 'true',
                    hidden: !isVisible(field),
                    options: field.tagName === 'SELECT' ?
                        Array.from(field.options).map(o => ({ value: o.value, label: o.text })) : [],
                    isInShadowDOM: true
                });
            });
            
            if (fields.length === 0) return [];
            
            return [{
                formIndex: 0,
                action: null,
                method: 'POST',
                id: 'shadow-dom-form',
                name: null,
                fields: fields,
                isShadowDOM: true
            }];
        }
    """)


async def extract_formless_containers(page) -> List[Dict]:
    """
    Extract fields from form-like containers that don't use <form> tags.
    Common in SPAs (React, Vue, Angular) where forms are just divs with inputs.
    """
    try:
        return await page.evaluate("""
            () => {
                const getText = (el) => (el?.innerText || el?.textContent || '').trim().split('\\n')[0].substring(0, 100);
                
                const isVisible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && 
                           style.visibility !== 'hidden' && 
                           style.opacity !== '0' &&
                           el.offsetWidth > 0;
                };
                
                const formLikeSelectors = [
                    '[role="form"]',
                    '[data-form]', '[data-testid*="form"]',
                    '[class*="form-container"]', '[class*="form-wrapper"]',
                    '[class*="contact-form"]', '[class*="signup-form"]', '[class*="login-form"]',
                    '[id*="form"]', '[class*="form"]',
                ];
                
                const containers = [];
                const seen = new Set();
                
                formLikeSelectors.forEach(selector => {
                    try {
                        document.querySelectorAll(selector).forEach(el => {
                            if (seen.has(el)) return;
                            const inputs = el.querySelectorAll('input:not([type="hidden"]), select, textarea, [role="combobox"]');
                            const hasSubmit = el.querySelector('button[type="submit"], input[type="submit"], button:not([type])');
                            if (inputs.length >= 2 && hasSubmit) {
                                seen.add(el);
                                containers.push(el);
                            }
                        });
                    } catch(e) {}
                });
                
                if (containers.length === 0) {
                    document.querySelectorAll('div, section, article, main').forEach(el => {
                        if (seen.has(el)) return;
                        const inputs = el.querySelectorAll('input:not([type="hidden"]), select, textarea');
                        const buttons = el.querySelectorAll('button, input[type="submit"]');
                        if (inputs.length >= 2 && buttons.length >= 1 && el.querySelectorAll('div').length < 50) {
                            const rect = el.getBoundingClientRect();
                            if (rect.height < window.innerHeight * 2) {
                                seen.add(el);
                                containers.push(el);
                            }
                        }
                    });
                }
                
                return containers.slice(0, 5).map((container, idx) => {
                    const fields = [];
                    const processedNames = new Set();
                    
                    container.querySelectorAll('input, select, textarea, [role="combobox"]').forEach(field => {
                        const name = field.name || field.id || `field_${fields.length}`;
                        if (processedNames.has(name)) return;
                        if (field.type === 'hidden' || field.type === 'submit') return;
                        if (!isVisible(field)) return;
                        
                        processedNames.add(name);
                        
                        let label = '';
                        if (field.id) {
                            const lbl = document.querySelector(`label[for="${field.id}"]`);
                            if (lbl) label = getText(lbl);
                        }
                        if (!label) {
                            const parent = field.closest('.form-group, .form-field, .input-group, [class*="field"], [class*="input"]');
                            if (parent) {
                                const lbl = parent.querySelector('label, .label, [class*="label"]');
                                if (lbl) label = getText(lbl);
                            }
                        }
                        if (!label) {
                            label = field.placeholder || field.getAttribute('aria-label') || name;
                        }
                        
                        let type = field.type || field.tagName.toLowerCase();
                        if (field.getAttribute('role') === 'combobox') type = 'dropdown';
                        if (field.tagName === 'SELECT') type = 'dropdown';
                        
                        fields.push({
                            name: name,
                            type: type,
                            tagName: field.tagName.toLowerCase(),
                            label: label.replace(/[*:]$/g, '').trim(),
                            placeholder: field.placeholder || null,
                            required: field.required || field.hasAttribute('required') || 
                                      field.getAttribute('aria-required') === 'true',
                            hidden: false,
                            options: field.tagName === 'SELECT' ? 
                                Array.from(field.options).filter(o => o.value).map(o => ({
                                    value: o.value, label: o.text.trim()
                                })) : []
                        });
                    });
                    
                    return {
                        formIndex: idx,
                        action: null,
                        method: 'POST',
                        id: container.id || null,
                        name: null,
                        fields: fields,
                        isFormless: true
                    };
                }).filter(f => f.fields.length > 0);
            }
        """)
    except Exception as e:
        print(f"  ⚠️ Formless extraction error: {e}")
        return []


async def extract_custom_dropdown_options(page, forms_data: List[Dict]) -> List[Dict]:
    """
    Click on custom dropdowns to reveal and extract their options.
    Supports: Ant Design, Material-UI, Vuetify, React-Select, Select2, etc.
    """
    for form in forms_data:
        for field in form.get('fields', []):
            if not (field.get('isCustomComponent') and 
                   field.get('type') == 'dropdown' and 
                   len(field.get('options', [])) == 0):
                continue
            
            field_name = field.get('name', '')
            print(f"  🔽 Extracting options for custom dropdown: {field_name}")
            
            try:
                click_selectors = [
                    f'#{field_name}',
                    f'[name="{field_name}"]',
                    f'.ant-select:has([id="{field_name}"])',
                    f'[aria-controls="{field_name}"]',
                    '.ant-select-selector',
                    '[class*="select__control"]',
                    '.MuiSelect-root',
                    '[role="combobox"]',
                ]
                
                clicked = False
                for selector in click_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            await element.click()
                            clicked = True
                            break
                    except:
                        continue
                
                if not clicked:
                    continue
                
                await asyncio.sleep(0.5)
                
                options = await page.evaluate("""
                    () => {
                        const optionSelectors = [
                            '.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option-content',
                            '.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item',
                            '.MuiMenu-paper .MuiMenuItem-root',
                            '.MuiAutocomplete-popper .MuiAutocomplete-option',
                            '[class*="MuiMenu"] [class*="MuiMenuItem"]',
                            '.v-menu__content .v-list-item',
                            '.v-select-list .v-list-item__title',
                            '.el-select-dropdown .el-select-dropdown__item',
                            '[class*="menu"] [class*="option"]',
                            '[class*="-menu"] [class*="-option"]',
                            '.select2-results__option',
                            '.choices__list--dropdown .choices__item',
                            '.bp4-menu-item', '.bp5-menu-item',
                            '.p-dropdown-panel .p-dropdown-item',
                            '.ui.active.visible.dropdown .menu .item',
                            '[data-headlessui-state*="open"] [role="option"]',
                            '[role="listbox"] [role="option"]',
                            '[role="menu"] [role="menuitem"]',
                            '.dropdown-menu .dropdown-item',
                            '[class*="dropdown"][class*="menu"] [class*="item"]',
                        ];
                        
                        const options = [];
                        const seen = new Set();
                        
                        optionSelectors.forEach(selector => {
                            try {
                                document.querySelectorAll(selector).forEach(opt => {
                                    const text = (opt.innerText || opt.textContent || '').trim();
                                    if (text && text.length > 0 && text.length < 200 && !seen.has(text)) {
                                        seen.add(text);
                                        options.push({ 
                                            value: opt.getAttribute('data-value') || text, 
                                            label: text 
                                        });
                                    }
                                });
                            } catch(e) {}
                        });
                        
                        return options;
                    }
                """)
                
                if options and len(options) > 0:
                    field['options'] = options
                    print(f"    ✓ Found {len(options)} options")
                else:
                    print(f"    ⚠️ No options found in dropdown portal")
                
                await page.keyboard.press('Escape')
                await asyncio.sleep(0.2)
                
            except Exception as e:
                print(f"    ⚠️ Could not extract options for {field_name}: {e}")
                continue
    
    return forms_data


async def extract_all_frames(page, url: str, extract_fn) -> List[Dict]:
    """Extract forms from all frames, including Shadow DOM, with deduplication."""
    seen_urls, seen_fields, forms_data = set(), set(), []
    
    for frame in page.frames:
        if frame.url in seen_urls or frame.is_detached():
            continue
        seen_urls.add(frame.url)
        
        try:
            frame_forms = await extract_fn(frame)
            for form in frame_forms:
                form['fields'] = [f for f in form.get('fields', []) 
                                  if not f.get('name') or (f['name'] not in seen_fields and not seen_fields.add(f['name']))]
            forms_data.extend([f for f in frame_forms if f.get('fields')])
        except Exception as e:
            if 'cross-origin' not in str(e).lower():
                print(f">> Frame error: {e}")
    
    # Try Shadow DOM
    if not forms_data:
        print(">> Trying Shadow DOM extraction...")
        try:
            shadow_forms = await extract_from_shadow_dom(page)
            forms_data.extend(shadow_forms)
        except Exception as e:
            print(f">> Shadow DOM error: {e}")
    
    # BeautifulSoup fallback
    if not forms_data:
        print(">> Trying BeautifulSoup fallback...")
        try:
            forms_data = extract_with_beautifulsoup(await page.content())
        except:
            pass
    
    return forms_data


def extract_with_beautifulsoup(html: str) -> List[Dict]:
    """BeautifulSoup fallback extraction with radio/checkbox grouping."""
    soup = BeautifulSoup(html, 'lxml')
    forms_data = []
    
    for idx, form in enumerate(soup.find_all('form')):
        fields = []
        processed_radio_groups = set()
        processed_checkbox_groups = set()
        
        for element in form.find_all(['input', 'select', 'textarea']):
            input_type = element.get('type', 'text') if element.name == 'input' else element.name
            name = element.get('name') or element.get('id')
            
            if not name or input_type in ('submit', 'button', 'hidden'):
                continue
            
            # Find label
            label = ''
            if element.get('id'):
                label_el = soup.find('label', {'for': element['id']})
                if label_el:
                    label = label_el.get_text(strip=True)
            
            if not label:
                label = element.get('placeholder', '') or element.get('aria-label', '') or name
            
            # Handle radio buttons
            if input_type == 'radio':
                if name in processed_radio_groups:
                    continue
                processed_radio_groups.add(name)
                
                radios = form.find_all('input', {'type': 'radio', 'name': name})
                options = []
                for r in radios:
                    opt_label = ''
                    if r.get('id'):
                        lbl = soup.find('label', {'for': r['id']})
                        if lbl:
                            opt_label = lbl.get_text(strip=True)
                    if not opt_label:
                        opt_label = r.get('value', '')
                    options.append({'value': r.get('value', opt_label), 'label': opt_label or r.get('value', '')})
                
                fields.append({
                    'name': name,
                    'type': 'radio',
                    'tagName': 'radio-group',
                    'label': label,
                    'required': any(r.get('required') for r in radios),
                    'hidden': False,
                    'options': options
                })
                continue
            
            # Handle checkboxes
            if input_type == 'checkbox':
                checkboxes = form.find_all('input', {'type': 'checkbox', 'name': name})
                if len(checkboxes) > 1:
                    if name in processed_checkbox_groups:
                        continue
                    processed_checkbox_groups.add(name)
                    
                    options = []
                    for c in checkboxes:
                        opt_label = ''
                        if c.get('id'):
                            lbl = soup.find('label', {'for': c['id']})
                            if lbl:
                                opt_label = lbl.get_text(strip=True)
                        if not opt_label:
                            opt_label = c.get('value', '')
                        options.append({'value': c.get('value', opt_label), 'label': opt_label})
                    
                    fields.append({
                        'name': name,
                        'type': 'checkbox-group',
                        'tagName': 'checkbox-group',
                        'label': label,
                        'required': any(c.get('required') for c in checkboxes),
                        'hidden': False,
                        'allows_multiple': True,
                        'options': options
                    })
                    continue
            
            # Handle select
            if element.name == 'select':
                options = [{'value': opt.get('value', ''), 'label': opt.get_text(strip=True)} 
                          for opt in element.find_all('option') if opt.get('value')]
                fields.append({
                    'name': name,
                    'type': 'dropdown',
                    'tagName': 'select',
                    'label': label,
                    'required': element.get('required') is not None,
                    'hidden': False,
                    'options': options
                })
                continue
            
            # Standard input
            fields.append({
                'name': name,
                'type': input_type,
                'tagName': element.name,
                'label': label,
                'placeholder': element.get('placeholder'),
                'required': element.get('required') is not None,
                'hidden': False
            })
        
        if fields:
            forms_data.append({
                'formIndex': idx,
                'action': form.get('action'),
                'method': (form.get('method') or 'GET').upper(),
                'id': form.get('id'),
                'name': form.get('name'),
                'fields': fields
            })
    
    return forms_data
