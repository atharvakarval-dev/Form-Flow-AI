"""
Google Forms Extractor
Specialized extraction for Google Forms with robust selectors.
"""

import asyncio
from typing import List, Dict


async def wait_for_google_form(page):
    """Wait for Google Form content to load."""
    print("⏳ Waiting for Google Form...")
    try:
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
        await asyncio.sleep(1)
    except:
        print("⚠️ Timeout waiting for form elements - attempting extraction anyway")


# Google Forms extraction JavaScript
GOOGLE_FORMS_JS = r'''
() => {
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
    
    console.log(`Found ${questions.length} question containers`);
    
    questions.forEach((q, idx) => {
        let label = '';
        
        // Method 1: Title span
        const titleSpan = q.querySelector('.M7eMe > span, .M7eMe');
        if (titleSpan) {
            const clone = titleSpan.cloneNode(true);
            clone.querySelectorAll('[role="radio"], [role="checkbox"], .docssharedWizToggleLabeledContainer, input').forEach(el => el.remove());
            label = getText(clone);
        }
        
        // Method 2: data-params
        if (!label) {
            const paramEl = q.querySelector('[data-params]');
            if (paramEl) {
                try {
                    const params = paramEl.getAttribute('data-params');
                    const match = params.match(/\[null,"([^"]+)"/);
                    if (match) label = match[1];
                } catch(e) {}
            }
        }
        
        // Method 3: First text block
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
        
        label = label.replace(/\*$/, '').replace(/\s*\(Required\)\s*/gi, '').trim();
        if (!label) label = `Question ${idx + 1}`;
        
        const required = q.innerHTML.includes('*') || 
                        q.querySelector('[aria-label*="Required"]') !== null ||
                        q.innerHTML.includes('required');
        
        const radioInputs = q.querySelectorAll('[role="radio"]');
        const checkboxInputs = q.querySelectorAll('[role="checkbox"]');
        const selectEl = q.querySelector('select, [role="listbox"]');
        
        const isDateQuestion = label.toLowerCase().includes('date') ||
                              q.querySelector('[data-date]') !== null ||
                              q.querySelector('[aria-label*="Day"], [aria-label*="Month"], [aria-label*="Year"]') !== null ||
                              q.querySelector('.qLWDgb') !== null;
        
        const textInput = q.querySelector('input.whsOnd, input[type="text"], input[type="email"]');
        const textArea = q.querySelector('textarea.KHxj8b, textarea');
        const fileInput = q.querySelector('input[type="file"]');
        
        let field = null;
        
        const isEmail = textInput?.getAttribute('aria-label')?.toLowerCase().includes('email') ||
                       label.toLowerCase().includes('email');
        
        if (radioInputs.length > 0) {
            const options = Array.from(radioInputs).map((r, i) => {
                let optionLabel = r.getAttribute('aria-label') || '';
                if (!optionLabel) optionLabel = r.getAttribute('data-value') || '';
                if (!optionLabel) {
                    const labelSpan = r.querySelector('span') || r.closest('[role="presentation"]')?.querySelector('span');
                    optionLabel = labelSpan ? getText(labelSpan) : '';
                }
                if (!optionLabel && r.nextElementSibling) {
                    optionLabel = getText(r.nextElementSibling);
                }
                if (!optionLabel) {
                    const optContainer = r.closest('.docssharedWizToggleLabeledContainer, .SG0AAe, [data-answer-value]');
                    if (optContainer) optionLabel = getText(optContainer);
                }
                return { value: optionLabel || `Option ${i + 1}`, label: optionLabel || `Option ${i + 1}` };
            }).filter(o => o.label && o.label.length > 0);
            
            field = { name: `radio_${idx}`, type: 'radio', tagName: 'radio-group', options };
            
        } else if (checkboxInputs.length > 0) {
            const options = Array.from(checkboxInputs).map((c, i) => {
                let optionLabel = c.getAttribute('aria-label') || '';
                if (!optionLabel) optionLabel = c.getAttribute('data-value') || '';
                if (!optionLabel) {
                    const optContainer = c.closest('.docssharedWizToggleLabeledContainer, .SG0AAe, [data-answer-value]');
                    if (optContainer) optionLabel = getText(optContainer);
                }
                if (!optionLabel) optionLabel = getText(c.parentElement);
                return { value: optionLabel || `Option ${i + 1}`, label: optionLabel || `Option ${i + 1}` };
            }).filter(o => o.label && o.label.length > 0);
            
            field = { name: `checkbox_${idx}`, type: 'checkbox-group', tagName: 'checkbox-group', allows_multiple: true, options };
            
        } else if (selectEl) {
            const options = selectEl.tagName === 'SELECT' 
                ? Array.from(selectEl.options).map(o => ({value: o.value, label: o.text}))
                : Array.from(q.querySelectorAll('[role="option"], [data-value]')).map(o => ({
                    value: o.getAttribute('data-value') || getText(o),
                    label: getText(o)
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
            // Clean label from leaked options
            if (field.options && field.options.length > 0) {
                let cleanLabel = label;
                for (const opt of field.options) {
                    if (opt.label) {
                        cleanLabel = cleanLabel.replace(new RegExp('\\b' + opt.label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'gi'), '');
                    }
                }
                cleanLabel = cleanLabel
                    .replace(/Other:\s*$/i, '')
                    .replace(/\s*\(This field is required\)\s*/gi, '')
                    .replace(/\s{2,}/g, ' ')
                    .trim();
                
                if (cleanLabel && cleanLabel.length > 5) label = cleanLabel;
            }
            
            field.label = label;
            field.display_name = label;
            field.required = required;
            field.hidden = false;
            form.fields.push(field);
        }
    });
    
    console.log(`Total fields extracted: ${form.fields.length}`);
    return form.fields.length > 0 ? [form] : [];
}
'''


async def extract_google_forms(page) -> List[Dict]:
    """Specialized Google Forms extraction with robust selectors."""
    print("🔍 Extracting Google Form...")
    return await page.evaluate(GOOGLE_FORMS_JS)
