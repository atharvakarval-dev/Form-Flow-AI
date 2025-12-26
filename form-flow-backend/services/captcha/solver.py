"""
CAPTCHA Solver Service - Main Orchestrator

Implements multi-strategy CAPTCHA solving:
1. Prevention (stealth mode) - avoid triggering CAPTCHA
2. Turnstile auto-wait - Cloudflare invisible challenges auto-solve
3. Manual fallback - pause and notify user
4. 2Captcha/AntiCaptcha API - automated paid solving
"""

import asyncio
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

from .twocaptcha import TwoCaptchaClient, TwoCaptchaResult


class CaptchaType(Enum):
    """Supported CAPTCHA types."""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    CLOUDFLARE_TURNSTILE = "cloudflare-turnstile"
    GENERIC = "generic"
    UNKNOWN = "unknown"


class SolveStrategy(Enum):
    """CAPTCHA solving strategies in priority order."""
    NONE_REQUIRED = "none_required"          # No CAPTCHA detected
    AUTO_WAIT = "auto_wait"                  # Turnstile/invisible - just wait
    API_SOLVE = "api_solve"                  # 2Captcha/AntiCaptcha
    MANUAL_FALLBACK = "manual_fallback"      # User solves manually


@dataclass
class CaptchaSolveResult:
    """Result from CAPTCHA solving attempt."""
    success: bool
    strategy_used: SolveStrategy
    captcha_type: Optional[CaptchaType] = None
    token: Optional[str] = None
    error: Optional[str] = None
    requires_user_action: bool = False
    solve_time_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "strategy": self.strategy_used.value,
            "captcha_type": self.captcha_type.value if self.captcha_type else None,
            "token": self.token,
            "error": self.error,
            "requires_user_action": self.requires_user_action,
            "solve_time_seconds": self.solve_time_seconds
        }


class CaptchaSolverService:
    """
    Multi-strategy CAPTCHA solving orchestrator.
    
    Priority Order:
    1. Check if no CAPTCHA present -> proceed
    2. Turnstile/invisible -> wait for auto-solve
    3. API key available -> use 2Captcha/AntiCaptcha
    4. No API key -> manual fallback (notify user)
    
    Usage:
        solver = CaptchaSolverService()
        result = await solver.solve(page, captcha_info)
        if result.success:
            # Continue with form submission
        elif result.requires_user_action:
            # Pause and wait for user to solve manually
    """
    
    # Turnstile typically auto-solves in 1-5 seconds
    TURNSTILE_WAIT_TIMEOUT = 15
    TURNSTILE_POLL_INTERVAL = 0.5
    
    def __init__(
        self, 
        twocaptcha_key: Optional[str] = None,
        anticaptcha_key: Optional[str] = None,
        solve_timeout: int = 120
    ):
        """
        Initialize solver with optional API keys.
        
        Args:
            twocaptcha_key: 2Captcha API key (or from TWOCAPTCHA_API_KEY env)
            anticaptcha_key: AntiCaptcha API key (or from ANTICAPTCHA_API_KEY env)
            solve_timeout: Max seconds to wait for API solve
        """
        self.twocaptcha_key = twocaptcha_key or os.getenv("TWOCAPTCHA_API_KEY")
        self.anticaptcha_key = anticaptcha_key or os.getenv("ANTICAPTCHA_API_KEY")
        self.solve_timeout = solve_timeout
        
        # Initialize clients if keys available
        self._twocaptcha_client: Optional[TwoCaptchaClient] = None
        if self.twocaptcha_key:
            self._twocaptcha_client = TwoCaptchaClient(
                self.twocaptcha_key, 
                timeout=solve_timeout
            )
    
    @property
    def has_api_key(self) -> bool:
        """Check if any solving API key is configured."""
        return bool(self.twocaptcha_key or self.anticaptcha_key)
    
    async def close(self):
        """Cleanup resources."""
        if self._twocaptcha_client:
            await self._twocaptcha_client.close()
    
    def _parse_captcha_type(self, captcha_info: Dict[str, Any]) -> CaptchaType:
        """Parse CAPTCHA type from detection result."""
        type_str = captcha_info.get("type", "unknown").lower()
        
        if "recaptcha" in type_str:
            # Check for v3 indicators
            if captcha_info.get("is_v3") or "v3" in type_str:
                return CaptchaType.RECAPTCHA_V3
            return CaptchaType.RECAPTCHA_V2
        elif "hcaptcha" in type_str:
            return CaptchaType.HCAPTCHA
        elif "turnstile" in type_str or "cloudflare" in type_str:
            return CaptchaType.CLOUDFLARE_TURNSTILE
        elif "captcha" in type_str:
            return CaptchaType.GENERIC
        
        return CaptchaType.UNKNOWN
    
    async def solve(
        self, 
        page, 
        captcha_info: Dict[str, Any],
        page_url: Optional[str] = None
    ) -> CaptchaSolveResult:
        """
        Main entry point - attempt to solve CAPTCHA using best available strategy.
        
        Args:
            page: Playwright page object
            captcha_info: Result from detect_captcha() function
            page_url: URL of the page (defaults to page.url)
        
        Returns:
            CaptchaSolveResult with success status and any token
        """
        import time
        start_time = time.time()
        
        # Check if CAPTCHA actually present
        if not captcha_info.get("hasCaptcha"):
            return CaptchaSolveResult(
                success=True,
                strategy_used=SolveStrategy.NONE_REQUIRED
            )
        
        captcha_type = self._parse_captcha_type(captcha_info)
        page_url = page_url or page.url
        
        print(f"🔐 CAPTCHA detected: {captcha_type.value}")
        
        # Strategy 1: Turnstile auto-wait
        if captcha_type == CaptchaType.CLOUDFLARE_TURNSTILE:
            result = await self._wait_for_turnstile(page)
            if result.success:
                result.solve_time_seconds = time.time() - start_time
                return result
            # Fall through to other strategies if auto-wait fails
        
        # Strategy 2: API solving (if key available)
        if self.has_api_key:
            sitekey = await self._extract_sitekey(page, captcha_type)
            if sitekey:
                result = await self._solve_with_api(
                    captcha_type, sitekey, page_url
                )
                if result.success:
                    # Inject token into page
                    await self._inject_token(page, captcha_type, result.token)
                    result.solve_time_seconds = time.time() - start_time
                    return result
        
        # Strategy 3: Manual fallback
        return CaptchaSolveResult(
            success=False,
            strategy_used=SolveStrategy.MANUAL_FALLBACK,
            captcha_type=captcha_type,
            requires_user_action=True,
            error="Please solve the CAPTCHA manually and click Continue.",
            solve_time_seconds=time.time() - start_time
        )
    
    async def _wait_for_turnstile(self, page, timeout: int = None) -> CaptchaSolveResult:
        """
        Wait for Cloudflare Turnstile to auto-solve.
        Turnstile is often invisible and solves in 1-5 seconds.
        """
        timeout = timeout or self.TURNSTILE_WAIT_TIMEOUT
        
        try:
            # Look for the response token input
            selectors = [
                'input[name="cf-turnstile-response"]',
                'input[name="cf-chl-response"]',
                '[name="turnstileToken"]'
            ]
            
            elapsed = 0
            while elapsed < timeout:
                for selector in selectors:
                    try:
                        token = await page.evaluate(f'''
                            () => {{
                                const el = document.querySelector('{selector}');
                                return el ? el.value : null;
                            }}
                        ''')
                        if token and len(token) > 10:
                            print(f"✅ Turnstile auto-solved in {elapsed:.1f}s")
                            return CaptchaSolveResult(
                                success=True,
                                strategy_used=SolveStrategy.AUTO_WAIT,
                                captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE,
                                token=token
                            )
                    except:
                        pass
                
                await asyncio.sleep(self.TURNSTILE_POLL_INTERVAL)
                elapsed += self.TURNSTILE_POLL_INTERVAL
            
            return CaptchaSolveResult(
                success=False,
                strategy_used=SolveStrategy.AUTO_WAIT,
                captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE,
                error="Turnstile did not auto-solve within timeout"
            )
            
        except Exception as e:
            return CaptchaSolveResult(
                success=False,
                strategy_used=SolveStrategy.AUTO_WAIT,
                captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE,
                error=str(e)
            )
    
    async def _extract_sitekey(self, page, captcha_type: CaptchaType) -> Optional[str]:
        """Extract sitekey from CAPTCHA element on page."""
        try:
            if captcha_type in (CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_V3):
                # reCAPTCHA sitekey locations
                sitekey = await page.evaluate('''
                    () => {
                        // From element attribute
                        const el = document.querySelector('[data-sitekey]');
                        if (el) return el.getAttribute('data-sitekey');
                        
                        // From script URL
                        const scripts = Array.from(document.querySelectorAll('script[src*="recaptcha"]'));
                        for (const s of scripts) {
                            const match = s.src.match(/[?&]render=([^&]+)/);
                            if (match) return match[1];
                        }
                        
                        // From grecaptcha object
                        if (window.grecaptcha && window.grecaptcha.enterprise) {
                            // Enterprise reCAPTCHA
                        }
                        
                        return null;
                    }
                ''')
                return sitekey
                
            elif captcha_type == CaptchaType.HCAPTCHA:
                return await page.evaluate('''
                    () => {
                        const el = document.querySelector('.h-captcha[data-sitekey], [data-hcaptcha-sitekey]');
                        return el ? (el.getAttribute('data-sitekey') || el.getAttribute('data-hcaptcha-sitekey')) : null;
                    }
                ''')
                
            elif captcha_type == CaptchaType.CLOUDFLARE_TURNSTILE:
                return await page.evaluate('''
                    () => {
                        const el = document.querySelector('.cf-turnstile[data-sitekey], [data-cf-turnstile]');
                        return el ? el.getAttribute('data-sitekey') : null;
                    }
                ''')
                
        except Exception as e:
            print(f"⚠️ Sitekey extraction failed: {e}")
        
        return None
    
    async def _solve_with_api(
        self, 
        captcha_type: CaptchaType, 
        sitekey: str, 
        page_url: str
    ) -> CaptchaSolveResult:
        """Solve CAPTCHA using 2Captcha API."""
        if not self._twocaptcha_client:
            return CaptchaSolveResult(
                success=False,
                strategy_used=SolveStrategy.API_SOLVE,
                captcha_type=captcha_type,
                error="No API client configured"
            )
        
        try:
            print(f"🔄 Sending to 2Captcha: {captcha_type.value}")
            
            if captcha_type == CaptchaType.RECAPTCHA_V2:
                result = await self._twocaptcha_client.solve_recaptcha(
                    sitekey, page_url, version="v2"
                )
            elif captcha_type == CaptchaType.RECAPTCHA_V3:
                result = await self._twocaptcha_client.solve_recaptcha(
                    sitekey, page_url, version="v3"
                )
            elif captcha_type == CaptchaType.HCAPTCHA:
                result = await self._twocaptcha_client.solve_hcaptcha(
                    sitekey, page_url
                )
            elif captcha_type == CaptchaType.CLOUDFLARE_TURNSTILE:
                result = await self._twocaptcha_client.solve_turnstile(
                    sitekey, page_url
                )
            else:
                return CaptchaSolveResult(
                    success=False,
                    strategy_used=SolveStrategy.API_SOLVE,
                    captcha_type=captcha_type,
                    error=f"Unsupported CAPTCHA type: {captcha_type.value}"
                )
            
            return CaptchaSolveResult(
                success=result.success,
                strategy_used=SolveStrategy.API_SOLVE,
                captcha_type=captcha_type,
                token=result.token,
                error=result.error,
                solve_time_seconds=result.solve_time_seconds
            )
            
        except Exception as e:
            return CaptchaSolveResult(
                success=False,
                strategy_used=SolveStrategy.API_SOLVE,
                captcha_type=captcha_type,
                error=str(e)
            )
    
    async def _inject_token(self, page, captcha_type: CaptchaType, token: str) -> bool:
        """Inject solved token into page."""
        try:
            if captcha_type in (CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_V3):
                await page.evaluate(f'''
                    (token) => {{
                        // Set textarea
                        const textarea = document.querySelector('#g-recaptcha-response, [name="g-recaptcha-response"]');
                        if (textarea) {{
                            textarea.value = token;
                            textarea.style.display = 'block';  // Some sites check visibility
                        }}
                        
                        // Also try hidden inputs
                        const hidden = document.querySelector('input[name="g-recaptcha-response"]');
                        if (hidden) hidden.value = token;
                        
                        // Trigger callback if exists
                        if (typeof window.captchaCallback === 'function') {{
                            window.captchaCallback(token);
                        }}
                    }}
                ''', token)
                
            elif captcha_type == CaptchaType.HCAPTCHA:
                await page.evaluate(f'''
                    (token) => {{
                        const textarea = document.querySelector('[name="h-captcha-response"], [name="g-recaptcha-response"]');
                        if (textarea) textarea.value = token;
                        
                        // hCaptcha callback
                        if (window.hcaptcha && typeof window.hcaptcha.getRespKey === 'function') {{
                            // Use API to set
                        }}
                    }}
                ''', token)
                
            elif captcha_type == CaptchaType.CLOUDFLARE_TURNSTILE:
                await page.evaluate(f'''
                    (token) => {{
                        const input = document.querySelector('[name="cf-turnstile-response"]');
                        if (input) input.value = token;
                    }}
                ''', token)
            
            print("✅ Token injected into page")
            return True
            
        except Exception as e:
            print(f"⚠️ Token injection failed: {e}")
            return False


# Singleton instance for dependency injection
_solver_instance: Optional[CaptchaSolverService] = None

def get_captcha_solver() -> CaptchaSolverService:
    """Get or create singleton CAPTCHA solver instance."""
    global _solver_instance
    if _solver_instance is None:
        _solver_instance = CaptchaSolverService()
    return _solver_instance
