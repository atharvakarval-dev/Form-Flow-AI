"""
Standard Forms Extractor
Extracts fields from standard HTML forms with radio/checkbox grouping.
"""

from typing import List, Dict


# The main extraction JavaScript - handles custom dropdowns, radio groups, checkboxes
STANDARD_FORMS_JS = '''
() => {
    const getText = el => el ? (el.innerText || el.textContent || '').trim() : '';
    const isVisible = el => {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0' && el.getBoundingClientRect().height > 0;
    };
    
    const findLabel = (field, form) => {
        // Strategy 1: Explicit label[for] association
        if (field.id) {
            const lbl = form.querySelector(`label[for="${field.id}"]`);
            if (lbl) return getText(lbl);
        }
        
        // Strategy 2: Label wrapping the field
        const parentLabel = field.closest('label');
        if (parentLabel) {
            const clone = parentLabel.cloneNode(true);
            clone.querySelectorAll('input, select, textarea').forEach(el => el.remove());
            const text = clone.textContent?.trim();
            if (text) return text;
        }
        
        // Strategy 3: aria-label or aria-labelledby
        if (field.getAttribute('aria-label')) {
            return field.getAttribute('aria-label');
        }
        if (field.getAttribute('aria-labelledby')) {
            const labelledBy = document.getElementById(field.getAttribute('aria-labelledby'));
            if (labelledBy) return getText(labelledBy);
        }
        
        // Strategy 4: Previous sibling label
        const prevSibling = field.previousElementSibling;
        if (prevSibling?.tagName === 'LABEL' || prevSibling?.classList?.contains('label')) {
            return getText(prevSibling);
        }
        
        // Strategy 5: Parent container with label
        const wrapper = field.closest(
            '.form-group, .form-field, .field, .input-group, .form-item, ' +
            '.ant-form-item, .MuiFormControl-root, .v-input, .el-form-item, ' +
            '[class*="field"], [class*="input-wrapper"], [class*="form-row"]'
        );
        if (wrapper) {
            const labelEl = wrapper.querySelector(
                'label, .label, .form-label, .control-label, .input-label, ' +
                '.ant-form-item-label, .MuiFormLabel-root, .v-label, .el-form-item__label'
            );
            if (labelEl && !labelEl.contains(field)) {
                return getText(labelEl);
            }
        }
        
        // Strategy 6: VISUAL PROXIMITY - find text above or to the left
        try {
            const fieldRect = field.getBoundingClientRect();
            const candidates = [];
            
            form.querySelectorAll('label, span, p, div, h1, h2, h3, h4, h5, h6, td, th').forEach(el => {
                if (el.querySelector('input, select, textarea')) return;
                const text = getText(el);
                if (!text || text.length > 100 || text.length < 2) return;
                
                const elRect = el.getBoundingClientRect();
                
                const isAbove = elRect.bottom <= fieldRect.top && 
                               elRect.bottom > fieldRect.top - 60 &&
                               Math.abs(elRect.left - fieldRect.left) < 100;
                
                const isLeft = elRect.right <= fieldRect.left &&
                              elRect.right > fieldRect.left - 200 &&
                              Math.abs(elRect.top - fieldRect.top) < 25;
                
                if (isAbove || isLeft) {
                    const distance = Math.hypot(
                        (elRect.right - fieldRect.left),
                        (elRect.bottom - fieldRect.top)
                    );
                    candidates.push({ el, text, distance, isAbove, isLeft });
                }
            });
            
            candidates.sort((a, b) => {
                if (a.isAbove && !b.isAbove) return -1;
                if (b.isAbove && !a.isAbove) return 1;
                return a.distance - b.distance;
            });
            
            if (candidates.length > 0) {
                return candidates[0].text;
            }
        } catch(e) {}
        
        // Strategy 7: Placeholder as fallback
        if (field.placeholder) return field.placeholder;
        
        // Strategy 8: title attribute
        if (field.title) return field.title;
        
        // Fallback: clean up the name attribute
        const name = field.name || field.id || '';
        return name.replace(/[_-]/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').trim();
    };
    
    // Find common label for radio/checkbox groups
    const findGroupLabel = (inputs, form) => {
        if (inputs.length === 0) return '';
        
        const firstInput = inputs[0];
        
        // Method 1: fieldset > legend
        const fieldset = firstInput.closest('fieldset');
        if (fieldset) {
            const legend = fieldset.querySelector('legend');
            if (legend) return getText(legend);
        }
        
        // Method 2: Look in container
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
        
        // Method 3: aria-label
        const ariaLabel = firstInput.closest('[aria-label]')?.getAttribute('aria-label');
        if (ariaLabel) return ariaLabel;
        
        // Method 4: data-label
        const dataLabel = firstInput.closest('[data-label]')?.getAttribute('data-label') ||
                         firstInput.getAttribute('data-label');
        if (dataLabel) return dataLabel;
        
        // Fallback
        const name = firstInput.name || '';
        return name.replace(/[_-]/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/\\[\\]/g, '').trim();
    };

    return Array.from(document.querySelectorAll('form')).map((form, idx) => {
        const fields = [];
        const processedRadioGroups = new Set();
        const processedCheckboxGroups = new Set();
        const skippedCustomDropdownInputs = new Set();
        
        // Custom dropdown selectors
        const customDropdownSelectors = [
            '.ant-select',
            '.MuiSelect-root', '.MuiAutocomplete-root', '[class*="MuiSelect"]',
            '.v-select', '.v-autocomplete',
            '.el-select', '.el-autocomplete',
            '[class*="select__control"]', '[class*="-control"][class*="css-"]',
            '.select2-container', '.select2',
            '.choices',
            '[data-headlessui-state]',
            '.bp4-select', '.bp5-select',
            '.p-dropdown', '.p-autocomplete',
            '.ui.dropdown', '.ui.selection.dropdown',
            '.bootstrap-select', '.dropdown-toggle[data-toggle="dropdown"]',
            '.select', '[class*="dropdown"]',
            '[role="combobox"]:not(input)', '[role="listbox"]',
            '[class*="select-wrapper"]', '[class*="dropdown-wrapper"]',
            '[class*="custom-select"]', '[class*="SelectContainer"]',
        ];
        
        // Pre-scan for custom dropdowns
        form.querySelectorAll(customDropdownSelectors.join(', ')).forEach(dropdown => {
            const innerInput = dropdown.querySelector('input');
            if (innerInput && (innerInput.id || innerInput.name)) {
                skippedCustomDropdownInputs.add(innerInput.id || innerInput.name);
            }
            const combobox = dropdown.querySelector('[role="combobox"]');
            if (combobox && (combobox.id || combobox.getAttribute('aria-controls'))) {
                skippedCustomDropdownInputs.add(combobox.id || combobox.getAttribute('aria-controls'));
            }
            
            // Extract as dropdown field
            let label = '';
            const inputId = innerInput?.id || combobox?.id;
            if (inputId) {
                const lbl = form.querySelector(`label[for="${inputId}"]`);
                if (lbl) label = getText(lbl);
            }
            
            if (!label) {
                const container = dropdown.closest('.ant-form-item, .form-group, .form-field, [class*="form-item"]');
                if (container) {
                    const labelEl = container.querySelector('label, .ant-form-item-label, .form-label');
                    if (labelEl) label = getText(labelEl);
                }
            }
            
            if (!label) {
                label = dropdown.getAttribute('aria-label') || 
                       innerInput?.getAttribute('aria-label') || 
                       combobox?.getAttribute('aria-label') || '';
            }
            
            if (!label) {
                const placeholder = dropdown.querySelector('.ant-select-selection-placeholder, [class*="placeholder"]');
                if (placeholder) {
                    label = getText(placeholder).replace(/^Select\\s*/i, '').trim();
                }
            }
            
            if (!label) return;
            
            const required = dropdown.querySelector('[aria-required="true"]') !== null ||
                            dropdown.closest('.ant-form-item-required') !== null ||
                            dropdown.closest('[class*="required"]') !== null ||
                            label.includes('*');
            
            fields.push({
                name: inputId || `custom_dropdown_${fields.length}`,
                type: 'dropdown',
                tagName: 'custom-select',
                label: label.replace(/\\*$/, '').trim(),
                required: required,
                hidden: !isVisible(dropdown),
                options: [],
                isCustomComponent: true
            });
        });
        
        // Process standard inputs
        Array.from(form.querySelectorAll('input, select, textarea')).forEach(field => {
            const type = field.type || field.tagName.toLowerCase();
            const name = field.name || field.id;
            
            if (!name || type === 'submit' || type === 'button' || type === 'hidden') return;
            if (skippedCustomDropdownInputs.has(name)) return;
            
            // Only skip internal search inputs inside custom select components
            // Don't skip regular text/email/tel inputs that might be siblings
            if (type === 'search' && field.closest('.ant-select, .select2-container, .choices, [class*="select-"][class*="container"]')) {
                // This is the internal search box of a custom dropdown - skip it
                return;
            }
            
            // RADIO BUTTONS
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
                    if (!optLabel && r.nextSibling) {
                        optLabel = (r.nextSibling.textContent || '').trim();
                    }
                    if (!optLabel) optLabel = r.value || '';
                    
                    return { value: r.value || optLabel, label: optLabel || r.value };
                }).filter(o => o.label);
                
                fields.push({
                    name: name,
                    type: 'radio',
                    tagName: 'radio-group',
                    label: findGroupLabel(radios, form),
                    required: radios.some(r => r.required || r.hasAttribute('required')),
                    hidden: !radios.some(r => isVisible(r)),
                    options: options
                });
                return;
            }
            
            // CHECKBOXES
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
                    fields.push({
                        name: name,
                        id: field.id || null,
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
                    id: field.id || null,
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
                id: field.id || null,
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
'''


async def extract_standard_forms(frame) -> List[Dict]:
    """Extract forms using JavaScript evaluation - handles radio/checkbox groups properly."""
    return await frame.evaluate(STANDARD_FORMS_JS)
