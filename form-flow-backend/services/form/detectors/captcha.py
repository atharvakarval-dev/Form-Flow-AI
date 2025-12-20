"""
CAPTCHA detection module.
Detects various types of CAPTCHAs to allow early exit.
"""

from typing import Dict, Any
from ..utils.constants import CAPTCHA_SELECTORS


async def detect_captcha(page) -> Dict[str, Any]:
    """
    Detect if form has CAPTCHA. Return early to save time.
    
    Returns:
        Dict with keys: hasCaptcha, type, message
    """
    selectors_js = str(CAPTCHA_SELECTORS).replace("'", '"')
    
    return await page.evaluate(f"""
        () => {{
            const captchaIndicators = {selectors_js};
            
            for (const selector of captchaIndicators) {{
                try {{
                    const el = document.querySelector(selector);
                    if (el && el.offsetParent !== null) {{
                        let captchaType = 'unknown';
                        if (selector.includes('recaptcha') || selector.includes('g-recaptcha')) {{
                            captchaType = 'recaptcha';
                        }} else if (selector.includes('hcaptcha')) {{
                            captchaType = 'hcaptcha';
                        }} else if (selector.includes('turnstile') || selector.includes('cf-')) {{
                            captchaType = 'cloudflare-turnstile';
                        }}
                        
                        return {{
                            hasCaptcha: true,
                            type: captchaType,
                            selector: selector,
                            message: 'Form requires CAPTCHA verification. Consider using a CAPTCHA solving service like 2captcha.com'
                        }};
                    }}
                }} catch(e) {{}}
            }}
            
            return {{ hasCaptcha: false, type: null, message: null }};
        }}
    """)


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
