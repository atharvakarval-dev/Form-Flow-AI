"""
2Captcha API Client

Implements solving via 2captcha.com service.
Supports reCAPTCHA v2/v3, hCaptcha, and Cloudflare Turnstile.
"""

import asyncio
import aiohttp
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class TwoCaptchaResult:
    """Result from 2Captcha solving attempt."""
    success: bool
    token: Optional[str] = None
    error: Optional[str] = None
    cost: float = 0.0
    solve_time_seconds: float = 0.0


class TwoCaptchaClient:
    """
    Async client for 2Captcha API.
    
    Usage:
        client = TwoCaptchaClient(api_key="YOUR_KEY")
        result = await client.solve_recaptcha(sitekey, page_url)
        if result.success:
            # Use result.token
    """
    
    BASE_URL = "http://2captcha.com"
    
    def __init__(self, api_key: str, timeout: int = 120):
        self.api_key = api_key
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def solve_recaptcha(
        self, 
        sitekey: str, 
        page_url: str,
        version: str = "v2",
        invisible: bool = False,
        action: Optional[str] = None,
        min_score: float = 0.3
    ) -> TwoCaptchaResult:
        """
        Solve reCAPTCHA v2 or v3.
        
        Args:
            sitekey: The data-sitekey from the reCAPTCHA element
            page_url: The full URL of the page with CAPTCHA
            version: "v2" or "v3"
            invisible: True for invisible reCAPTCHA
            action: Action name for v3 (e.g., "submit")
            min_score: Minimum score for v3 (0.1-0.9)
        """
        import time
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            # Step 1: Submit task
            params = {
                "key": self.api_key,
                "method": "userrecaptcha",
                "googlekey": sitekey,
                "pageurl": page_url,
                "json": 1
            }
            
            if version == "v3":
                params["version"] = "v3"
                if action:
                    params["action"] = action
                params["min_score"] = min_score
            elif invisible:
                params["invisible"] = 1
            
            async with session.post(f"{self.BASE_URL}/in.php", data=params) as resp:
                result = await resp.json()
            
            if result.get("status") != 1:
                return TwoCaptchaResult(
                    success=False, 
                    error=result.get("request", "Unknown error")
                )
            
            task_id = result["request"]
            print(f"🔄 2Captcha task submitted: {task_id}")
            
            # Step 2: Poll for result
            poll_url = f"{self.BASE_URL}/res.php"
            poll_params = {
                "key": self.api_key,
                "action": "get",
                "id": task_id,
                "json": 1
            }
            
            elapsed = 0
            poll_interval = 5  # seconds
            
            while elapsed < self.timeout:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                async with session.get(poll_url, params=poll_params) as resp:
                    result = await resp.json()
                
                if result.get("status") == 1:
                    # Success!
                    solve_time = time.time() - start_time
                    print(f"✅ 2Captcha solved in {solve_time:.1f}s")
                    return TwoCaptchaResult(
                        success=True,
                        token=result["request"],
                        solve_time_seconds=solve_time,
                        cost=0.003  # Approximate cost per solve
                    )
                elif result.get("request") == "CAPCHA_NOT_READY":
                    print(f"⏳ 2Captcha: Still solving... ({elapsed}s)")
                    continue
                else:
                    # Error
                    return TwoCaptchaResult(
                        success=False,
                        error=result.get("request", "Unknown error")
                    )
            
            return TwoCaptchaResult(success=False, error="Timeout waiting for solution")
            
        except Exception as e:
            return TwoCaptchaResult(success=False, error=str(e))
    
    async def solve_hcaptcha(self, sitekey: str, page_url: str) -> TwoCaptchaResult:
        """Solve hCaptcha."""
        import time
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            params = {
                "key": self.api_key,
                "method": "hcaptcha",
                "sitekey": sitekey,
                "pageurl": page_url,
                "json": 1
            }
            
            async with session.post(f"{self.BASE_URL}/in.php", data=params) as resp:
                result = await resp.json()
            
            if result.get("status") != 1:
                return TwoCaptchaResult(success=False, error=result.get("request"))
            
            task_id = result["request"]
            
            # Poll for result
            poll_params = {"key": self.api_key, "action": "get", "id": task_id, "json": 1}
            elapsed = 0
            
            while elapsed < self.timeout:
                await asyncio.sleep(5)
                elapsed += 5
                
                async with session.get(f"{self.BASE_URL}/res.php", params=poll_params) as resp:
                    result = await resp.json()
                
                if result.get("status") == 1:
                    return TwoCaptchaResult(
                        success=True,
                        token=result["request"],
                        solve_time_seconds=time.time() - start_time
                    )
                elif result.get("request") != "CAPCHA_NOT_READY":
                    return TwoCaptchaResult(success=False, error=result.get("request"))
            
            return TwoCaptchaResult(success=False, error="Timeout")
            
        except Exception as e:
            return TwoCaptchaResult(success=False, error=str(e))
    
    async def solve_turnstile(self, sitekey: str, page_url: str) -> TwoCaptchaResult:
        """Solve Cloudflare Turnstile."""
        import time
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            params = {
                "key": self.api_key,
                "method": "turnstile",
                "sitekey": sitekey,
                "pageurl": page_url,
                "json": 1
            }
            
            async with session.post(f"{self.BASE_URL}/in.php", data=params) as resp:
                result = await resp.json()
            
            if result.get("status") != 1:
                return TwoCaptchaResult(success=False, error=result.get("request"))
            
            task_id = result["request"]
            poll_params = {"key": self.api_key, "action": "get", "id": task_id, "json": 1}
            elapsed = 0
            
            while elapsed < self.timeout:
                await asyncio.sleep(5)
                elapsed += 5
                
                async with session.get(f"{self.BASE_URL}/res.php", params=poll_params) as resp:
                    result = await resp.json()
                
                if result.get("status") == 1:
                    return TwoCaptchaResult(
                        success=True,
                        token=result["request"],
                        solve_time_seconds=time.time() - start_time
                    )
                elif result.get("request") != "CAPCHA_NOT_READY":
                    return TwoCaptchaResult(success=False, error=result.get("request"))
            
            return TwoCaptchaResult(success=False, error="Timeout")
            
        except Exception as e:
            return TwoCaptchaResult(success=False, error=str(e))
    
    async def get_balance(self) -> float:
        """Get account balance."""
        try:
            session = await self._get_session()
            params = {"key": self.api_key, "action": "getbalance", "json": 1}
            async with session.get(f"{self.BASE_URL}/res.php", params=params) as resp:
                result = await resp.json()
            return float(result.get("request", 0))
        except:
            return 0.0
