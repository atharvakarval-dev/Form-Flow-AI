"""
CAPTCHA detection module.
Detects various types of CAPTCHAs to allow early exit.
"""

import json
from typing import Dict, Any
from ..utils.constants import CAPTCHA_SELECTORS


async def detect_captcha(page) -> Dict[str, Any]:
    """
    Detect if form has CAPTCHA. Return early to save time.
    
    Returns:
        Dict with keys: hasCaptcha, type, message
    """
    selectors_js = json.dumps(CAPTCHA_SELECTORS)
    
    result = await page.evaluate(f"""
        () => {{
            const captchaIndicators = {selectors_js};
            
            // Helper function to check if element is visible
            const isVisible = (el) => {{
                if (!el) return false;
                // For iframes, just check if they exist (they're often hidden via CSS transforms)
                if (el.tagName === 'IFRAME') return true;
                // For other elements, do a more thorough check
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' && 
                       style.visibility !== 'hidden' && 
                       rect.width > 0 && 
                       rect.height > 0;
            }};
            
            for (const selector of captchaIndicators) {{
                try {{
                    const elements = document.querySelectorAll(selector);
                    for (const el of elements) {{
                        if (isVisible(el)) {{
                            let captchaType = 'unknown';
                            const selectorLower = selector.toLowerCase();
                            const html = el.outerHTML.toLowerCase();
                            
                            if (selectorLower.includes('recaptcha') || selectorLower.includes('g-recaptcha') || 
                                html.includes('recaptcha') || html.includes('g-recaptcha')) {{
                                captchaType = 'recaptcha';
                            }} else if (selectorLower.includes('hcaptcha') || html.includes('hcaptcha')) {{
                                captchaType = 'hcaptcha';
                            }} else if (selectorLower.includes('turnstile') || selectorLower.includes('cf-') ||
                                       html.includes('turnstile') || html.includes('cf-turnstile')) {{
                                captchaType = 'cloudflare-turnstile';
                            }} else if (html.includes('captcha')) {{
                                captchaType = 'generic-captcha';
                            }}
                            
                            console.log('🔍 CAPTCHA DETECTED:', captchaType, 'Selector:', selector);
                            
                            return {{
                                hasCaptcha: true,
                                type: captchaType,
                                selector: selector,
                                message: 'Form requires CAPTCHA verification. Please solve it manually.'
                            }};
                        }}
                    }}
                }} catch(e) {{
                    console.log('CAPTCHA check error for selector:', selector, e);
                }}
            }}
            
            // Also check for any iframes that might contain captcha
            const allIframes = document.querySelectorAll('iframe');
            for (const iframe of allIframes) {{
                const src = (iframe.src || '').toLowerCase();
                const title = (iframe.title || '').toLowerCase();
                if (src.includes('captcha') || src.includes('recaptcha') || src.includes('hcaptcha') ||
                    title.includes('captcha') || title.includes('recaptcha') || title.includes('challenge')) {{
                    console.log('🔍 CAPTCHA IFRAME DETECTED:', src || title);
                    return {{
                        hasCaptcha: true,
                        type: src.includes('hcaptcha') ? 'hcaptcha' : 'recaptcha',
                        selector: 'iframe',
                        message: 'Form requires CAPTCHA verification. Please solve it manually.'
                    }};
                }}
            }}
            
            console.log('✅ No CAPTCHA detected');
            return {{ hasCaptcha: false, type: null, message: null }};
        }}
    """)
    
    # Log the result for debugging
    if result.get('hasCaptcha'):
        print(f"🔍 CAPTCHA detected: {result.get('type')} via {result.get('selector')}")
    else:
        print("✅ No CAPTCHA detected on page")
    
    return result


async def detect_login_required(page) -> Dict[str, Any]:
    """
    Detect if the page requires login to access the form.
    """
    return await page.evaluate("""
        () => {
            // Check for common login indicators
            const loginIndicators = [
                // URL patterns
                window.location.href.includes('/login'),
                window.location.href.includes('/signin'),
                window.location.href.includes('/auth'),
                
                // Page content
                document.querySelector('form[action*="login"]') !== null,
                document.querySelector('form[action*="signin"]') !== null,
                document.querySelector('input[type="password"]') !== null &&
                    document.querySelectorAll('input').length <= 3,
                
                // Redirect indicators
                document.querySelector('meta[http-equiv="refresh"][content*="login"]') !== null
            ];
            
            const requiresLogin = loginIndicators.some(Boolean);
            
            return {
                requiresLogin: requiresLogin,
                message: requiresLogin ? 'Page appears to require authentication' : null,
                indicators: loginIndicators.map((v, i) => v ? i : null).filter(v => v !== null)
            };
        }
    """)


async def detect_bot_protection(page) -> Dict[str, Any]:
    """
    Detect advanced bot protection that might block scraping.
    """
    return await page.evaluate("""
        () => {
            const protectionIndicators = {
                cloudflare: !!document.querySelector('#cf-wrapper, .cf-browser-verification'),
                datadome: !!document.querySelector('[class*="datadome"]'),
                perimeterx: !!document.querySelector('[class*="px-"]'),
                akamai: !!document.querySelector('[id*="akamai"]'),
                incapsula: window._incapsula_settings !== undefined
            };
            
            const detected = Object.entries(protectionIndicators)
                .filter(([k, v]) => v)
                .map(([k]) => k);
            
            return {
                hasProtection: detected.length > 0,
                protectionTypes: detected,
                message: detected.length > 0 ? 
                    `Bot protection detected: ${detected.join(', ')}` : null
            };
        }
    """)
