"""
Playwright Browser Pool

Provides browser instance reuse to reduce memory usage.
Instead of spawning a new browser for each operation (~300MB each),
we reuse a single browser instance with multiple contexts (~50MB each).

Usage:
    from services.form.browser_pool import get_browser_context, release_browser_context
    
    async with get_browser_context() as context:
        page = await context.new_page()
        await page.goto(url)
        ...
"""

import asyncio
from typing import Optional
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
MAX_CONTEXTS = 5  # Maximum concurrent browser contexts


async def _get_browser():
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
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',  # Prevents crashes in Docker
                    '--disable-gpu',
                    '--single-process',  # Reduces memory
                    '--no-zygote',
                ]
            )
            logger.info("✅ Browser launched and ready")
        
        return _browser


@asynccontextmanager
async def get_browser_context():
    """
    Get a browser context from the pool.
    
    Each context is isolated (like incognito) but shares the browser instance.
    Memory usage: ~50MB per context vs ~300MB per browser.
    
    Usage:
        async with get_browser_context() as context:
            page = await context.new_page()
            await page.goto("https://example.com")
            # ... do work
        # Context automatically closed
    """
    global _active_contexts
    
    # Wait if we're at max capacity
    while _active_contexts >= MAX_CONTEXTS:
        logger.debug(f"Browser pool full ({_active_contexts}/{MAX_CONTEXTS}), waiting...")
        await asyncio.sleep(0.5)
    
    browser = await _get_browser()
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    )
    
    _active_contexts += 1
    logger.debug(f"Context acquired ({_active_contexts}/{MAX_CONTEXTS} active)")
    
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
