"""
Third-Party Form Provider Detection Module.

Detects embedded third-party form providers (TypeForm, JotForm, etc.)
and analyzes iframe accessibility for cross-origin limitations.
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ProviderAccessibility(Enum):
    """Accessibility status of a third-party form provider."""
    ACCESSIBLE = "accessible"          # Same-origin, can extract
    CROSS_ORIGIN = "cross_origin"      # Cross-origin, blocked by CORS
    SANDBOXED = "sandboxed"            # Sandboxed iframe, limited access
    UNKNOWN = "unknown"                # Could not determine


@dataclass
class ThirdPartyFormInfo:
    """Information about a detected third-party form."""
    provider: str
    url: str
    accessibility: ProviderAccessibility
    iframe_id: Optional[str] = None
    warning_message: Optional[str] = None
    extraction_hint: Optional[str] = None


# Known third-party form providers with their detection patterns
KNOWN_PROVIDERS = {
    # Provider domain patterns -> (Display Name, Extraction Hint)
    'typeform.com': ('TypeForm', 'TypeForm embeds are cross-origin. Consider using TypeForm API for data access.'),
    'jotform.com': ('JotForm', 'JotForm forms can be accessed via their API with form ID.'),
    'cognito': ('Cognito Forms', 'Cognito Forms embeds may allow limited interaction via postMessage.'),
    'google.com/forms': ('Google Forms', 'Google Forms are always cross-origin. Use form link directly.'),
    'docs.google.com/forms': ('Google Forms', 'Google Forms are always cross-origin. Use form link directly.'),
    'hubspot': ('HubSpot Forms', 'HubSpot embeds are cross-origin. Use HubSpot API for programmatic access.'),
    'forms.hubspot': ('HubSpot Forms', 'HubSpot embeds are cross-origin. Use HubSpot API for programmatic access.'),
    'wufoo.com': ('Wufoo', 'Wufoo forms may allow API access with form hash.'),
    'formstack.com': ('Formstack', 'Consider using Formstack API for form data.'),
    'airtable.com': ('Airtable', 'Airtable forms are cross-origin. Use Airtable API.'),
    'paperform.co': ('Paperform', 'Paperform embeds are typically cross-origin.'),
    'tally.so': ('Tally', 'Tally forms may support limited embedding configurations.'),
    'form.io': ('Form.io', 'Form.io forms may be accessible depending on CORS settings.'),
    'netlify.com/forms': ('Netlify Forms', 'Netlify Forms are often same-origin if hosted on same domain.'),
    'formspree.io': ('Formspree', 'Formspree handles submission only; form lives on your page.'),
    'getform.io': ('Getform', 'Getform handles submission; extraction depends on form host.'),
    'basin.io': ('Basin', 'Basin handles submission; form structure is on host page.'),
}

# Selectors for common embedded form containers
EMBEDDED_FORM_SELECTORS = [
    'iframe[src*="typeform"]',
    'iframe[src*="jotform"]',
    'iframe[src*="cognito"]',
    'iframe[src*="google.com/forms"]',
    'iframe[src*="docs.google.com/forms"]',
    'iframe[src*="hubspot"]',
    'iframe[src*="wufoo"]',
    'iframe[src*="formstack"]',
    'iframe[src*="airtable"]',
    'iframe[src*="paperform"]',
    'iframe[src*="tally.so"]',
    'iframe[src*="form.io"]',
    '[data-tf-widget]',  # TypeForm widget
    '[data-formkit-uid]',  # FormKit
    '.cognito-form-embed',
    '.hubspot-form-wrapper',
    '#hubspot-form',
]


async def detect_third_party_forms(page) -> List[ThirdPartyFormInfo]:
    """
    Detect third-party form providers embedded in the page.
    
    Args:
        page: Playwright page object
        
    Returns:
        List of detected third-party form providers with accessibility info
    """
    selectors_js = json.dumps(EMBEDDED_FORM_SELECTORS)
    providers_js = json.dumps({k: v[0] for k, v in KNOWN_PROVIDERS.items()})
    
    detected = await page.evaluate(f"""
        () => {{
            const providers = {providers_js};
            const selectors = {selectors_js};
            const results = [];
            const seen = new Set();
            
            // Check all iframes
            document.querySelectorAll('iframe').forEach(iframe => {{
                const src = iframe.src || '';
                if (!src || seen.has(src)) return;
                seen.add(src);
                
                // Determine provider
                let provider = 'Unknown Provider';
                let hint = '';
                
                for (const [pattern, name] of Object.entries(providers)) {{
                    if (src.toLowerCase().includes(pattern.toLowerCase())) {{
                        provider = name;
                        break;
                    }}
                }}
                
                // Check accessibility
                let accessibility = 'unknown';
                try {{
                    const currentOrigin = window.location.origin;
                    const iframeUrl = new URL(src);
                    if (iframeUrl.origin === currentOrigin) {{
                        accessibility = 'accessible';
                    }} else {{
                        accessibility = 'cross_origin';
                    }}
                }} catch (e) {{
                    accessibility = 'cross_origin';
                }}
                
                // Check if sandboxed
                if (iframe.sandbox && iframe.sandbox.length > 0) {{
                    if (!iframe.sandbox.contains('allow-scripts') || 
                        !iframe.sandbox.contains('allow-same-origin')) {{
                        accessibility = 'sandboxed';
                    }}
                }}
                
                results.push({{
                    provider: provider,
                    url: src,
                    accessibility: accessibility,
                    iframeId: iframe.id || null,
                    iframeName: iframe.name || null,
                    title: iframe.title || null,
                    dimensions: {{
                        width: iframe.offsetWidth,
                        height: iframe.offsetHeight
                    }}
                }});
            }});
            
            // Also check for specific embed selectors
            selectors.forEach(selector => {{
                try {{
                    document.querySelectorAll(selector).forEach(el => {{
                        if (el.tagName !== 'IFRAME') {{
                            let provider = 'Embedded Form Widget';
                            if (selector.includes('typeform') || selector.includes('tf-widget')) {{
                                provider = 'TypeForm';
                            }} else if (selector.includes('cognito')) {{
                                provider = 'Cognito Forms';
                            }} else if (selector.includes('hubspot')) {{
                                provider = 'HubSpot Forms';
                            }} else if (selector.includes('formkit')) {{
                                provider = 'FormKit';
                            }}
                            
                            const key = provider + '_widget';
                            if (!seen.has(key)) {{
                                seen.add(key);
                                results.push({{
                                    provider: provider,
                                    url: null,
                                    accessibility: 'accessible',
                                    iframeId: null,
                                    isWidget: true
                                }});
                            }}
                        }}
                    }});
                }} catch(e) {{}}
            }});
            
            return results;
        }}
    """)
    
    # Convert to ThirdPartyFormInfo objects
    forms = []
    for item in detected:
        provider_key = None
        for pattern, (name, hint) in KNOWN_PROVIDERS.items():
            if item.get('provider') == name:
                provider_key = pattern
                break
        
        extraction_hint = None
        if provider_key:
            extraction_hint = KNOWN_PROVIDERS[provider_key][1]
        
        accessibility = ProviderAccessibility(item.get('accessibility', 'unknown'))
        
        warning = None
        if accessibility == ProviderAccessibility.CROSS_ORIGIN:
            warning = f"⚠️ {item['provider']} form detected but cannot be extracted (cross-origin security restriction)"
        elif accessibility == ProviderAccessibility.SANDBOXED:
            warning = f"⚠️ {item['provider']} form is sandboxed with restricted permissions"
        
        forms.append(ThirdPartyFormInfo(
            provider=item['provider'],
            url=item.get('url'),
            accessibility=accessibility,
            iframe_id=item.get('iframeId'),
            warning_message=warning,
            extraction_hint=extraction_hint
        ))
    
    return forms


async def analyze_iframe_accessibility(page) -> Dict[str, Any]:
    """
    Analyze all iframes on the page for accessibility status.
    
    Returns:
        Dict with categorized iframes and overall status
    """
    result = await page.evaluate("""
        () => {
            const currentOrigin = window.location.origin;
            const sameOrigin = [];
            const crossOrigin = [];
            const sandboxed = [];
            const warnings = [];
            
            document.querySelectorAll('iframe').forEach(iframe => {
                const src = iframe.src || '';
                if (!src) return;
                
                const info = {
                    url: src,
                    id: iframe.id || null,
                    name: iframe.name || null,
                    title: iframe.title || null,
                    visible: iframe.offsetParent !== null,
                    dimensions: {
                        width: iframe.offsetWidth,
                        height: iframe.offsetHeight
                    }
                };
                
                try {
                    const iframeUrl = new URL(src);
                    
                    if (iframeUrl.origin === currentOrigin) {
                        sameOrigin.push(info);
                    } else {
                        crossOrigin.push(info);
                        
                        // Check if this iframe appears to contain a form
                        const hasFormKeywords = /form|signup|register|contact|apply|survey|questionnaire/i.test(src);
                        if (hasFormKeywords && info.visible) {
                            warnings.push(`Cross-origin iframe detected that may contain a form: ${src.substring(0, 100)}...`);
                        }
                    }
                    
                    // Check sandbox
                    if (iframe.sandbox && iframe.sandbox.length > 0) {
                        if (!iframe.sandbox.contains('allow-same-origin')) {
                            sandboxed.push(info);
                        }
                    }
                } catch(e) {
                    crossOrigin.push(info);
                }
            });
            
            return {
                sameOrigin,
                crossOrigin,
                sandboxed,
                warnings,
                totalIframes: sameOrigin.length + crossOrigin.length,
                hasEmbeddedForms: warnings.length > 0 || crossOrigin.some(f => 
                    /form|typeform|jotform|cognito|hubspot|wufoo|google.*form/i.test(f.url || '')
                )
            };
        }
    """)
    
    return result


async def get_third_party_warnings(page) -> List[str]:
    """
    Get user-friendly warnings about third-party forms.
    
    Returns:
        List of warning messages to display to the user
    """
    warnings = []
    
    # Detect third-party forms
    third_party = await detect_third_party_forms(page)
    
    for form in third_party:
        if form.warning_message:
            warnings.append(form.warning_message)
        if form.extraction_hint:
            warnings.append(f"💡 Tip: {form.extraction_hint}")
    
    # Analyze iframe accessibility
    iframe_analysis = await analyze_iframe_accessibility(page)
    
    if iframe_analysis.get('hasEmbeddedForms') and not third_party:
        warnings.append("⚠️ Cross-origin iframe detected that may contain form content. Extraction may be limited.")
    
    # Count blocked forms
    blocked_count = sum(1 for f in third_party if f.accessibility == ProviderAccessibility.CROSS_ORIGIN)
    if blocked_count > 1:
        warnings.insert(0, f"⚠️ {blocked_count} third-party embedded forms detected. These cannot be automatically extracted due to browser security.")
    
    return warnings
