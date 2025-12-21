"""
Playwright Browser Pool

Provides browser instance reuse to reduce memory usage.
Instead of spawning a new browser for each operation (~300MB each),
we reuse a single browser instance with multiple contexts (~50MB each).

Usage:
    from services.form.browser_pool import get_browser_context
    
    async with get_browser_context() as context:
        page = await context.new_page()
        await page.goto(url)
        ...

For parser/submitter with custom options:
    async with get_browser_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='...',
        stealth_script='...',
        block_resources=['media', 'font']
    ) as context:
        page = await context.new_page()
        ...
"""

import asyncio
import os
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from utils.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# Browser Pool Configuration
# =============================================================================

# Singleton browser instance (shared across requests)
_browser = None
_playwright = None
_browser_lock = asyncio.Lock()

# Track active contexts for cleanup
_active_contexts = 0
MAX_CONTEXTS = int(os.getenv("BROWSER_POOL_MAX_CONTEXTS", "5"))

# Semaphore for strict concurrency control
_context_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    """Get or create the context semaphore."""
    global _context_semaphore
    if _context_semaphore is None:
        _context_semaphore = asyncio.Semaphore(MAX_CONTEXTS)
    return _context_semaphore


# Default browser args optimized for low-memory servers
BROWSER_ARGS = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',  # Prevents crashes in Docker
    '--disable-gpu',
    '--single-process',  # Reduces memory
    '--no-zygote',
    '--disable-background-networking',
    '--disable-default-apps',
    '--disable-extensions',
    '--disable-sync',
    '--disable-translate',
    '--mute-audio',
    '--no-first-run',
    '--disable-background-timer-throttling',
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',
]


async def _get_browser(headless: bool = True):
    """
    Get or create the shared browser instance.
    
    Uses a lock to prevent multiple simultaneous browser launches.
    """
    global _browser, _playwright
    
    async with _browser_lock:
        if _browser is None or not _browser.is_connected():
            logger.info("🌐 Launching shared browser instance...")
            
            from playwright.async_api import async_playwright
            
            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=headless,
                args=BROWSER_ARGS
            )
            logger.info("✅ Browser launched and ready")
        
        return _browser


@asynccontextmanager
async def get_browser_context(
    viewport: Optional[Dict[str, int]] = None,
    user_agent: Optional[str] = None,
    stealth_script: Optional[str] = None,
    block_resources: Optional[List[str]] = None,
    locale: str = "en-US",
    headless: bool = True,
):
    """
    Get a browser context from the pool with optional customization.
    
    Each context is isolated (like incognito) but shares the browser instance.
    Memory usage: ~50MB per context vs ~300MB per browser.
    
    Args:
        viewport: Custom viewport size (default: 1920x1080)
        user_agent: Custom user agent string
        stealth_script: JavaScript to inject for stealth/anti-bot
        block_resources: List of resource types to block (e.g., ['media', 'font'])
        locale: Browser locale (default: en-US)
        headless: Whether to run in headless mode (default: True)
    
    Usage:
        async with get_browser_context() as context:
            page = await context.new_page()
            await page.goto("https://example.com")
            # ... do work
        # Context automatically closed
    """
    global _active_contexts
    
    semaphore = _get_semaphore()
    
    # Use semaphore for strict concurrency control
    async with semaphore:
        _active_contexts += 1
        logger.debug(f"Context acquired ({_active_contexts}/{MAX_CONTEXTS} active)")
        
        browser = await _get_browser(headless=headless)
        
        # Default configurations
        default_viewport = {'width': 1920, 'height': 1080}
        default_user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        
        context = await browser.new_context(
            viewport=viewport or default_viewport,
            user_agent=user_agent or default_user_agent,
            locale=locale,
        )
        
        # Inject stealth script if provided
        if stealth_script:
            await context.add_init_script(stealth_script)
        
        # Create page and set up resource blocking if needed
        page = None
        if block_resources:
            page = await context.new_page()
            await page.route(
                "**/*", 
                lambda route: route.abort() if route.request.resource_type in set(block_resources) else route.continue_()
            )
        
        try:
            yield context
        finally:
            _active_contexts -= 1
            try:
                await context.close()
                logger.debug(f"Context released ({_active_contexts}/{MAX_CONTEXTS} active)")
            except Exception:
                pass


async def close_browser_pool():
    """
    Close the browser pool.
    
    Called on application shutdown.
    """
    global _browser, _playwright
    
    if _browser:
        try:
            await _browser.close()
            logger.info("Browser pool closed")
        except Exception:
            pass
        _browser = None
    
    if _playwright:
        try:
            await _playwright.stop()
        except Exception:
            pass
        _playwright = None


def get_pool_status() -> dict:
    """Get current browser pool status."""
    return {
        "browser_running": _browser is not None and _browser.is_connected() if _browser else False,
        "active_contexts": _active_contexts,
        "max_contexts": MAX_CONTEXTS,
    }
