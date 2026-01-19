"""
Conditional Field Handler Module.

Provides safe and controlled triggering of conditional/dependent form fields.
Supports "safe mode" to avoid accidental form interactions.
"""

import asyncio
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


class TriggerStrategy(Enum):
    """Strategy for triggering conditional fields."""
    SAFE = "safe"          # Only detect, don't trigger changes
    CAUTIOUS = "cautious"  # Trigger only obvious cascading selects
    AGGRESSIVE = "aggressive"  # Try all triggers to discover hidden fields


@dataclass
class ConditionalFieldResult:
    """Result of conditional field detection/triggering."""
    discovered_fields: List[Dict] = field(default_factory=list)
    dependencies: Dict[str, List[Dict]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    triggered_count: int = 0
    skipped_count: int = 0


# Common patterns that indicate cascading/dependent fields
CASCADE_PATTERNS = [
    # Country → State → City patterns
    ('country', ['state', 'province', 'region']),
    ('state', ['city', 'district', 'municipality']),
    ('region', ['subregion', 'area', 'zone']),
    
    # Category → Subcategory patterns
    ('category', ['subcategory', 'sub_category']),
    ('type', ['subtype', 'sub_type']),
    
    # Department → Role patterns
    ('department', ['role', 'position', 'team']),
    ('company', ['branch', 'location', 'office']),
    
    # Date-related patterns
    ('year', ['month']),
    ('month', ['day', 'date']),
]


async def detect_conditional_triggers(
    page, 
    forms_data: List[Dict],
    strategy: TriggerStrategy = TriggerStrategy.SAFE
) -> ConditionalFieldResult:
    """
    Detect fields that may trigger conditional behavior.
    
    In SAFE mode, only detects potential triggers without interacting.
    In CAUTIOUS mode, tests obvious cascade patterns.
    In AGGRESSIVE mode, tests all selects/radios/checkboxes.
    
    Args:
        page: Playwright page object
        forms_data: List of form dictionaries
        strategy: How aggressive to be with triggering
        
    Returns:
        ConditionalFieldResult with discovered fields and dependencies
    """
    result = ConditionalFieldResult()
    
    # Collect all field names for pattern matching
    all_fields = {}
    for form in forms_data:
        for f in form.get('fields', []):
            name = f.get('name', '').lower()
            if name:
                all_fields[name] = f
    
    # Detect potential cascade triggers based on naming patterns
    potential_triggers = []
    for trigger_pattern, dependent_patterns in CASCADE_PATTERNS:
        for field_name in all_fields:
            if trigger_pattern in field_name:
                # Check if any dependent fields exist
                for dep_pattern in dependent_patterns:
                    for dep_name in all_fields:
                        if dep_pattern in dep_name:
                            potential_triggers.append({
                                'trigger_field': field_name,
                                'dependent_field': dep_name,
                                'pattern': f"{trigger_pattern} → {dep_pattern}"
                            })
    
    if potential_triggers:
        result.warnings.append(
            f"💡 Detected {len(potential_triggers)} potential cascading field relationship(s)"
        )
    
    if strategy == TriggerStrategy.SAFE:
        # Only detect, don't trigger
        for trigger in potential_triggers:
            result.dependencies[trigger['trigger_field']] = [{
                'field': trigger['dependent_field'],
                'pattern': trigger['pattern'],
                'detected_only': True
            }]
        result.skipped_count = len(potential_triggers)
        return result
    
    # CAUTIOUS or AGGRESSIVE mode - actually trigger fields
    try:
        from ..detectors.dependencies import map_conditional_fields, detect_chained_selects
        
        if strategy == TriggerStrategy.CAUTIOUS:
            # Only test detected patterns
            result.warnings.append("🔍 Testing detected cascade patterns...")
            
            for trigger in potential_triggers[:5]:  # Limit to 5 triggers
                trigger_field = trigger['trigger_field']
                selector = f'select[name="{trigger_field}"], select#{trigger_field}'
                select_el = await page.query_selector(selector)
                
                if not select_el:
                    continue
                
                # Test selecting an option
                options = await select_el.evaluate('el => Array.from(el.options).map(o => o.value)')
                if len(options) > 1:
                    original = await select_el.evaluate('el => el.value')
                    test_val = options[1] if options[0] == original else options[0]
                    
                    try:
                        await select_el.select_option(value=test_val)
                        await asyncio.sleep(0.3)
                        
                        # Check for new fields
                        new_fields = await page.evaluate("""
                            () => {
                                return Array.from(document.querySelectorAll('input, select, textarea'))
                                    .filter(el => el.offsetParent !== null)
                                    .map(el => ({
                                        name: el.name || el.id,
                                        type: el.type || el.tagName.toLowerCase(),
                                        visible: true
                                    }));
                            }
                        """)
                        
                        new_field_names = {f['name'] for f in new_fields if f['name']}
                        existing_names = set(all_fields.keys())
                        discovered = new_field_names - existing_names
                        
                        if discovered:
                            result.discovered_fields.extend([
                                {'name': n, 'discovered_by': trigger_field}
                                for n in discovered
                            ])
                        
                        # Restore original value
                        await select_el.select_option(value=original)
                        await asyncio.sleep(0.2)
                        
                        result.triggered_count += 1
                        
                    except Exception as e:
                        result.warnings.append(f"⚠️ Could not test {trigger_field}: {str(e)[:50]}")
        
        elif strategy == TriggerStrategy.AGGRESSIVE:
            # Use existing comprehensive mapping
            result.warnings.append("🔍 Performing comprehensive conditional field scan...")
            deps = await map_conditional_fields(page, forms_data)
            result.dependencies = deps
            
            # Also detect chained selects
            forms_data = await detect_chained_selects(page, forms_data)
            
            result.triggered_count = len(deps)
            
    except ImportError as e:
        result.warnings.append(f"⚠️ Dependencies module not available: {e}")
    except Exception as e:
        result.warnings.append(f"⚠️ Error during conditional field detection: {e}")
    
    return result


async def trigger_cascade_fields(
    page,
    field_name: str,
    field_value: str,
    wait_ms: int = 300
) -> List[Dict]:
    """
    Trigger a specific field and return any newly appearing fields.
    
    This is used during form filling when selecting a value
    should reveal dependent fields.
    
    Args:
        page: Playwright page object
        field_name: Name of the field to change
        field_value: Value to set
        wait_ms: Milliseconds to wait after change
        
    Returns:
        List of newly visible field info dicts
    """
    # Get field state before change
    before_state = await page.evaluate("""
        () => {
            const fields = new Map();
            document.querySelectorAll('input, select, textarea').forEach(el => {
                const name = el.name || el.id;
                if (name) {
                    fields.set(name, {
                        visible: el.offsetParent !== null,
                        disabled: el.disabled,
                        optionCount: el.tagName === 'SELECT' ? el.options.length : 0
                    });
                }
            });
            return Object.fromEntries(fields);
        }
    """)
    
    # Try to set the value
    selector = f'select[name="{field_name}"], select#{field_name}, input[name="{field_name}"], input#{field_name}'
    element = await page.query_selector(selector)
    
    if not element:
        return []
    
    tag = await element.evaluate('el => el.tagName')
    
    if tag == 'SELECT':
        await element.select_option(value=field_value)
    else:
        input_type = await element.evaluate('el => el.type')
        if input_type in ['radio', 'checkbox']:
            await element.click()
        else:
            await element.fill(field_value)
    
    # Wait for any conditional rendering
    await asyncio.sleep(wait_ms / 1000)
    
    # Get field state after change
    after_state = await page.evaluate("""
        () => {
            const fields = [];
            document.querySelectorAll('input, select, textarea').forEach(el => {
                const name = el.name || el.id;
                if (name && el.offsetParent !== null) {
                    fields.push({
                        name: name,
                        type: el.type || el.tagName.toLowerCase(),
                        label: (() => {
                            if (el.id) {
                                const lbl = document.querySelector(`label[for="${el.id}"]`);
                                if (lbl) return lbl.textContent.trim();
                            }
                            return el.placeholder || name;
                        })(),
                        required: el.required,
                        optionCount: el.tagName === 'SELECT' ? el.options.length : 0
                    });
                }
            });
            return fields;
        }
    """)
    
    # Find newly visible or changed fields
    new_fields = []
    for field in after_state:
        name = field['name']
        before = before_state.get(name, {'visible': False})
        
        if not before.get('visible') and name != field_name:
            # Field became visible
            new_fields.append({**field, 'appeared': True})
        elif field.get('optionCount', 0) != before.get('optionCount', 0):
            # Options changed (cascading select)
            new_fields.append({**field, 'options_changed': True})
    
    return new_fields


def get_suggested_fill_order(
    fields: List[Dict],
    dependencies: Dict[str, List[Dict]]
) -> List[str]:
    """
    Get suggested order to fill fields based on dependencies.
    
    Trigger fields should be filled before their dependents.
    
    Args:
        fields: List of field dicts
        dependencies: Dependency mapping from detect_conditional_triggers
        
    Returns:
        Ordered list of field names
    """
    field_names = [f.get('name') for f in fields if f.get('name')]
    
    # Build simple dependency graph
    dependents: Dict[str, Set[str]] = {}
    for trigger, deps in dependencies.items():
        if trigger not in dependents:
            dependents[trigger] = set()
        for dep in deps:
            dep_name = dep.get('field', '')
            if dep_name:
                dependents[trigger].add(dep_name)
    
    # Topological sort (simplified - just put triggers first)
    triggers = list(dependents.keys())
    dependent_fields = set()
    for deps in dependents.values():
        dependent_fields.update(deps)
    
    ordered = []
    
    # Add triggers first
    for name in field_names:
        if name in triggers:
            ordered.append(name)
    
    # Add non-dependent fields
    for name in field_names:
        if name not in triggers and name not in dependent_fields:
            ordered.append(name)
    
    # Add dependent fields last
    for name in field_names:
        if name in dependent_fields and name not in ordered:
            ordered.append(name)
    
    return ordered
