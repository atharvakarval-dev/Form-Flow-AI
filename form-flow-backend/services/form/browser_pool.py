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
from typing import Optional, Dict, List
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


# Default browser args optimized for stability and low-memory servers
BROWSER_ARGS = [
    # Core Stability Flags
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--no-zygote',
    
    # Anti-Detection
    '--disable-blink-features=AutomationControlled',
    
    # Process & Networking Management
    '--disable-background-networking',
    '--disable-default-apps',
    '--disable-extensions',
    '--disable-sync',
    '--disable-translate',
    '--mute-audio',
    '--no-first-run',
    
    # Background Throttling
    '--disable-background-timer-throttling',
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',
    
    # Hardware Compatibility
    '--disable-software-rasterizer',
    '--disable-gl-drawing-for-tests',
    
    # Network Stability (prevents ERR_HTTP2_PROTOCOL_ERROR)
    '--disable-http2',
]


async def _get_browser(headless: bool = True):
    """
    Get or create the shared browser instance.
    
    Uses a lock to prevent multiple simultaneous browser launches.
    Will relaunch if browser becomes disconnected.
    """
    global _browser, _playwright
    
    async with _browser_lock:
        # Force reconnection if browser is disconnected
        if _browser is not None:
            try:
                if not _browser.is_connected():
                    logger.warning("Browser disconnected, relaunching...")
                    _browser = None
            except Exception:
                _browser = None
        
        if _browser is None:
            logger.info("🌐 Launching shared browser instance...")
            
            from playwright.async_api import async_playwright
            
            if _playwright is None:
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
    
    ROBUST: Will retry context creation if browser crashes during the operation.
    """
    global _active_contexts, _browser, _playwright
    
    semaphore = _get_semaphore()
    context = None
    
    # Default configurations
    default_viewport = {'width': 1920, 'height': 1080}
    default_user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )
    
    async with semaphore:
        _active_contexts += 1
        logger.debug(f"Context acquired ({_active_contexts}/{MAX_CONTEXTS} active)")
        
        # Retry loop for robust browser/context creation
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                browser = await _get_browser(headless=headless)
                
                # Create context - this is where crashes often happen
                context = await browser.new_context(
                    viewport=viewport or default_viewport,
                    user_agent=user_agent or default_user_agent,
                    locale=locale,
                )
                
                # Inject stealth script if provided
                if stealth_script:
                    await context.add_init_script(stealth_script)
                
                # Set up resource blocking at context level
                if block_resources:
                    await context.route(
                        "**/*", 
                        lambda route: route.abort() if route.request.resource_type in set(block_resources) else route.continue_()
                    )
                
                # Success - break out of retry loop
                break
                
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                if "Target" in error_str or "closed" in error_str or "disconnected" in error_str:
                    logger.warning(f"Browser crashed during context creation (attempt {attempt+1}/{max_retries}), relaunching...")
                    
                    # Force browser restart
                    async with _browser_lock:
                        try:
                            if _browser:
                                await _browser.close()
                        except:
                            pass
                        _browser = None
                        
                        try:
                            if _playwright:
                                await _playwright.stop()
                        except:
                            pass
                        _playwright = None
                    
                    # Small delay before retry
                    await asyncio.sleep(1)
                else:
                    # Unknown error, don't retry
                    raise
        
        if context is None:
            _active_contexts -= 1
            raise last_error or Exception("Failed to create browser context after retries")
        
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
        "sync_browser_running": _sync_browser is not None,
    }


# =============================================================================
# SYNC Browser Pool (for Windows sync_playwright path)
# =============================================================================

import threading
from contextlib import contextmanager

_sync_browser = None
_sync_playwright_instance = None
_sync_lock = threading.Lock()


def _get_sync_browser(headless: bool = True):
    """Get or create the shared SYNC browser instance (thread-safe)."""
    global _sync_browser, _sync_playwright_instance
    
    with _sync_lock:
        if _sync_browser is not None:
            try:
                if _sync_browser.is_connected():
                    return _sync_browser
            except Exception:
                pass
            # Browser died, clean up
            _sync_browser = None
        
        logger.info("🚀 Launching shared SYNC browser instance...")
        
        from playwright.sync_api import sync_playwright
        
        if _sync_playwright_instance is None:
            _sync_playwright_instance = sync_playwright().start()
        
        _sync_browser = _sync_playwright_instance.chromium.launch(
            headless=headless,
            args=BROWSER_ARGS
        )
        logger.info("✅ Sync browser launched and ready")
        return _sync_browser


def _force_sync_cleanup():
    """Force cleanup of stale sync browser (e.g. after greenlet error)."""
    global _sync_browser, _sync_playwright_instance
    with _sync_lock:
        try:
            if _sync_browser:
                _sync_browser.close()
        except Exception:
            pass
        _sync_browser = None
        try:
            if _sync_playwright_instance:
                _sync_playwright_instance.stop()
        except Exception:
            pass
        _sync_playwright_instance = None


@contextmanager
def get_sync_browser_context(
    viewport=None,
    user_agent=None,
    stealth_script=None,
    block_resources=None,
    locale="en-US",
    headless=True,
):
    """
    Get a sync browser context from the pool.
    
    Auto-recovers from greenlet errors (stale browser from dead thread)
    by tearing down and re-launching.
    """
    default_viewport = {'width': 1920, 'height': 1080}
    default_user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )
    
    context = None
    for attempt in range(2):
        browser = _get_sync_browser(headless=headless)
        try:
            context = browser.new_context(
                viewport=viewport or default_viewport,
                user_agent=user_agent or default_user_agent,
                locale=locale,
            )
            break  # Success
        except Exception as e:
            if "greenlet" in str(e).lower() or "different thread" in str(e).lower() or "exited" in str(e).lower():
                logger.info(f"🔄 Browser context stale (attempt {attempt+1}/2), re-launching...")
                _force_sync_cleanup()
                if attempt == 1:
                    raise
            else:
                raise
    
    if stealth_script:
        context.add_init_script(stealth_script)
    
    if block_resources:
        blocked = set(block_resources)
        context.route("**/*", lambda r: r.abort() if r.request.resource_type in blocked else r.continue_())
    
    try:
        yield context
    finally:
        try:
            context.close()
        except Exception:
            pass


def close_sync_browser_pool():
    """Close the sync browser pool."""
    global _sync_browser, _sync_playwright_instance
    
    with _sync_lock:
        if _sync_browser:
            try:
                _sync_browser.close()
            except Exception:
                pass
            _sync_browser = None
        
        if _sync_playwright_instance:
            try:
                _sync_playwright_instance.stop()
            except Exception:
                pass
            _sync_playwright_instance = None
    
    logger.info("🛑 Sync browser pool closed")
