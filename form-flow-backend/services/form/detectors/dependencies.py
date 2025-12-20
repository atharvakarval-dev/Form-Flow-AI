"""
Field dependency detection module.
Handles conditional fields and chained select boxes.
"""

import asyncio
from typing import Dict, List, Any


async def map_conditional_fields(page, forms_data: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Map conditional field dependencies (if field X = Y, show field Z).
    Returns a dependency graph for smart form filling.
    
    Returns:
        Dict mapping trigger field names to their dependent fields
    """
    try:
        # Get initial field state
        initial_state = await page.evaluate("""
            () => {
                const fields = {};
                document.querySelectorAll('input, select, textarea').forEach(f => {
                    const name = f.name || f.id;
                    if (name) {
                        fields[name] = {
                            visible: f.offsetParent !== null,
                            value: f.value,
                            disabled: f.disabled
                        };
                    }
                });
                return fields;
            }
        """)
        
        dependencies = {}
        
        # Test each select/radio/checkbox for conditional behavior
        triggers = await page.query_selector_all('select, input[type="radio"], input[type="checkbox"]')
        
        for trigger in triggers[:10]:  # Limit to first 10 to avoid too much time
            try:
                trigger_name = await trigger.evaluate('el => el.name || el.id')
                if not trigger_name:
                    continue
                
                tag_name = await trigger.evaluate('el => el.tagName')
                trigger_type = await trigger.evaluate('el => el.type')
                
                if tag_name == 'SELECT':
                    # Test selecting different options
                    options = await trigger.evaluate('el => Array.from(el.options).map(o => o.value)')
                    original_value = await trigger.evaluate('el => el.value')
                    
                    for option in options[:3]:  # Test first 3 options
                        if option == original_value:
                            continue
                        
                        await trigger.select_option(value=option)
                        await asyncio.sleep(0.3)
                        
                        # Check what changed
                        new_state = await page.evaluate("""
                            () => {
                                const fields = {};
                                document.querySelectorAll('input, select, textarea').forEach(f => {
                                    const name = f.name || f.id;
                                    if (name) {
                                        fields[name] = {
                                            visible: f.offsetParent !== null,
                                            value: f.value,
                                            disabled: f.disabled
                                        };
                                    }
                                });
                                return fields;
                            }
                        """)
                        
                        # Find fields that appeared or changed
                        for field_name, state in new_state.items():
                            if field_name == trigger_name:
                                continue
                            old = initial_state.get(field_name, {'visible': False})
                            if state['visible'] and not old.get('visible', False):
                                if trigger_name not in dependencies:
                                    dependencies[trigger_name] = []
                                dependencies[trigger_name].append({
                                    'field': field_name,
                                    'triggerValue': option,
                                    'action': 'show'
                                })
                    
                    # Restore original value
                    await trigger.select_option(value=original_value)
                    
                elif trigger_type in ['radio', 'checkbox']:
                    # Toggle the checkbox/radio
                    was_checked = await trigger.evaluate('el => el.checked')
                    await trigger.click()
                    await asyncio.sleep(0.3)
                    
                    # Check what changed
                    new_state = await page.evaluate("""
                        () => {
                            const fields = {};
                            document.querySelectorAll('input, select, textarea').forEach(f => {
                                const name = f.name || f.id;
                                if (name) {
                                    fields[name] = {
                                        visible: f.offsetParent !== null,
                                        disabled: f.disabled
                                    };
                                }
                            });
                            return fields;
                        }
                    """)
                    
                    for field_name, state in new_state.items():
                        if field_name == trigger_name:
                            continue
                        old = initial_state.get(field_name, {'visible': False})
                        if state['visible'] != old.get('visible', False):
                            if trigger_name not in dependencies:
                                dependencies[trigger_name] = []
                            dependencies[trigger_name].append({
                                'field': field_name,
                                'triggerValue': not was_checked,
                                'action': 'show' if state['visible'] else 'hide'
                            })
                    
                    # Restore original state
                    if was_checked != await trigger.evaluate('el => el.checked'):
                        await trigger.click()
                        
            except Exception:
                continue
        
        return dependencies
        
    except Exception as e:
        print(f"⚠️ Conditional field mapping error: {e}")
        return {}


async def detect_chained_selects(page, forms_data: List[Dict]) -> List[Dict]:
    """
    Detect and mark chained/dependent select boxes.
    (e.g., Country → State → City)
    """
    for form in forms_data:
        dropdowns = [f for f in form.get('fields', []) if f.get('type') == 'dropdown']
        
        for i, field in enumerate(dropdowns):
            try:
                field_name = field.get('name', '')
                select_el = await page.query_selector(f'select[name="{field_name}"], select#{field_name}')
                
                if not select_el:
                    continue
                
                options = field.get('options', [])
                if len(options) < 2:
                    continue
                
                # Remember original value
                original_value = await select_el.evaluate('el => el.value')
                
                # Get other select elements' option counts before change
                other_selects = [d['name'] for d in dropdowns[i+1:i+3]]  # Check next 2
                before_counts = {}
                for other_name in other_selects:
                    count = await page.evaluate(f"""
                        () => {{
                            const sel = document.querySelector('select[name="{other_name}"], select#{other_name}');
                            return sel ? sel.options.length : 0;
                        }}
                    """)
                    before_counts[other_name] = count
                
                # Select a different option
                test_option = options[1]['value'] if len(options) > 1 else options[0]['value']
                if test_option != original_value:
                    await select_el.select_option(value=test_option)
                    await asyncio.sleep(0.5)
                    
                    # Check if other selects' options changed
                    dependent_fields = []
                    for other_name in other_selects:
                        after_count = await page.evaluate(f"""
                            () => {{
                                const sel = document.querySelector('select[name="{other_name}"], select#{other_name}');
                                return sel ? sel.options.length : 0;
                            }}
                        """)
                        if after_count != before_counts[other_name]:
                            dependent_fields.append(other_name)
                    
                    if dependent_fields:
                        field['dependentFields'] = dependent_fields
                        field['isChained'] = True
                        print(f"  🔗 Found chained select: {field_name} → {dependent_fields}")
                    
                    # Restore original value
                    await select_el.select_option(value=original_value)
                    await asyncio.sleep(0.3)
                    
            except Exception:
                continue
    
    return forms_data
