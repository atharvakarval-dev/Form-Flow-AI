import random
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

async def setup_production_stealth_browser(page, context=None):
    """
    Configure browser to avoid detection with 8-tier protection.
    
    1. Remove webdriver flag
    2. Randomize viewport
    3. Inject navigator overrides (plugins, languages, hardwareConcurrency)
    4. Spoof chrome.runtime
    5. Mask permissions
    6. Randomize canvas fingerprint (noise)
    7. Randomize WebGL fingerprint (noise)
    8. Mock standardized path for headless checks
    """
    
    # 1. Remove webdriver property (Critical)
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)
    
    # 2. Randomize viewport is handled at context creation, but we ensure window.outerWidth/Height matches
    if context:
        # Get actual viewport size
        viewport = page.viewport_size
        if viewport:
            width = viewport['width']
            height = viewport['height']
            await page.add_init_script(f"""
                Object.defineProperty(window, 'outerWidth', {{ get: () => {width} }});
                Object.defineProperty(window, 'outerHeight', {{ get: () => {height} }});
                Object.defineProperty(window, 'innerWidth', {{ get: () => {width} }});
                Object.defineProperty(window, 'innerHeight', {{ get: () => {height} }});
            """)

    # 3. Enhanced Navigator Overrides
    await page.add_init_script("""
        // Pass standard bot tests
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                ];
                return plugins;
            }
        });
        
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        // Randomize hardware concurrency to realistic values
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 4 + Math.floor(Math.random() * 4) * 2 // 4, 6, 8, 12
        });
        
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8
        });
    """)
    
    # 4. Spoof chrome.runtime
    await page.add_init_script("""
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
    """)
    
    # 5. Mask Permissions Query
    await page.add_init_script("""
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: 'denied', onchange: null }) :
            originalQuery(parameters)
        );
    """)
    
    # 6 & 7. Canvas & WebGL Noise (Fingerprint randomization)
    # Adds subtle noise to canvas readouts so they are unique but consistent for session
    await page.add_init_script("""
        const shift = {
            'r': Math.floor(Math.random() * 10) - 5,
            'g': Math.floor(Math.random() * 10) - 5,
            'b': Math.floor(Math.random() * 10) - 5
        };
        
        // Canvas noise
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function() {
            const context = this.getContext('2d');
            if (context) {
                const imageData = context.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] = imageData.data[i] + shift.r;
                    imageData.data[i+1] = imageData.data[i+1] + shift.g;
                    imageData.data[i+2] = imageData.data[i+2] + shift.b;
                }
                context.putImageData(imageData, 0, 0);
            }
            return originalToDataURL.apply(this, arguments);
        };
        
        // WebGL noise
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            // Spoof renderer to look like real GPU
            if (parameter === 37445) {
                return 'Intel Open Source Technology Center';
            }
            if (parameter === 37446) {
                return 'Mesa DRI Intel(R) HD Graphics 620 (Kaby Lake GT2)';
            }
            return getParameter(this, parameter);
        };
    """)
    
    # 8. Hide automation traces
    await page.add_init_script("""
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
    """)
    
    logger.info("🕵️  Production stealth mode enabled (8-tier protection)")

def get_random_viewport() -> Dict[str, int]:
    """Return a random realistic viewport resolution."""
    viewports = [
        {'width': 1920, 'height': 1080},
        {'width': 1366, 'height': 768},
        {'width': 1440, 'height': 900},
        {'width': 1536, 'height': 864},
        {'width': 2560, 'height': 1440}
    ]
    return random.choice(viewports)

def get_random_user_agent() -> str:
    """Return a random recent user agent string."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
    ]
    return random.choice(user_agents)

def get_random_timezone() -> str:
    """Return a random US/Europe timezone."""
    timezones = [
        'America/New_York', 'America/Chicago', 'America/Los_Angeles', 
        'America/Denver', 'Europe/London', 'Europe/Paris', 'Europe/Berlin'
    ]
    return random.choice(timezones)

def setup_production_stealth_browser_sync(page, context=None):
    """
    Synchronous version of stealth setup for Windows compatibility.
    """
    # 1. Remove webdriver property (Critical)
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)
    
    # 2. Randomize viewport
    if context:
        viewport = page.viewport_size
        if viewport:
            width = viewport['width']
            height = viewport['height']
            page.add_init_script(f"""
                Object.defineProperty(window, 'outerWidth', {{ get: () => {width} }});
                Object.defineProperty(window, 'outerHeight', {{ get: () => {height} }});
                Object.defineProperty(window, 'innerWidth', {{ get: () => {width} }});
                Object.defineProperty(window, 'innerHeight', {{ get: () => {height} }});
            """)

    # 3. Enhanced Navigator Overrides
    page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                ];
                return plugins;
            }
        });
        
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 4 + Math.floor(Math.random() * 4) * 2
        });
        
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8
        });
    """)
    
    # 4. Spoof chrome.runtime
    page.add_init_script("""
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
    """)
    
    # 5. Mask Permissions Query
    page.add_init_script("""
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: 'denied', onchange: null }) :
            originalQuery(parameters)
        );
    """)
    
    # 6 & 7. Canvas & WebGL Noise
    page.add_init_script("""
        const shift = {
            'r': Math.floor(Math.random() * 10) - 5,
            'g': Math.floor(Math.random() * 10) - 5,
            'b': Math.floor(Math.random() * 10) - 5
        };
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function() {
            const context = this.getContext('2d');
            if (context) {
                const imageData = context.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] = imageData.data[i] + shift.r;
                    imageData.data[i+1] = imageData.data[i+1] + shift.g;
                    imageData.data[i+2] = imageData.data[i+2] + shift.b;
                }
                context.putImageData(imageData, 0, 0);
            }
            return originalToDataURL.apply(this, arguments);
        };
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Open Source Technology Center';
            if (parameter === 37446) return 'Mesa DRI Intel(R) HD Graphics 620 (Kaby Lake GT2)';
            return getParameter(this, parameter);
        };
    """)
    
    # 8. Hide automation traces
    page.add_init_script("""
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
    """)
    
    logger.info("🕵️  Production stealth mode enabled (8-tier protection) [SYNC]")
