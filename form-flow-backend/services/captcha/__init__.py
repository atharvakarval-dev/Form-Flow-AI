"""
CAPTCHA Solving Service Package

Provides multi-strategy CAPTCHA handling:
1. Prevention (stealth mode)
2. Manual fallback (notify user)
3. 2Captcha/AntiCaptcha API
4. Cloudflare Turnstile auto-wait
"""

from .solver import CaptchaSolverService, CaptchaSolveResult

__all__ = ['CaptchaSolverService', 'CaptchaSolveResult']
