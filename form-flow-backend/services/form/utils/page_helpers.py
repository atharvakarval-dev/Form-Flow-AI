"""
Page helper utilities for form parsing.
Handles DOM stability, scrolling, section expansion, etc.
"""

import asyncio
import json
from typing import Dict, Any

from .constants import EXPANDABLE_SECTION_SELECTORS


async def wait_for_dom_stability(page, timeout_ms: int = 10000, stability_ms: int = 500) -> str:
    """
    Wait for DOM to stabilize - no mutations for stability_ms.
    Essential for SPA/React/Vue/Angular forms that render dynamically.
    
    Returns: 'stable' if DOM stabilized, 'timeout' if max timeout reached
    """
    try:
        return await page.evaluate(f"""
            () => new Promise((resolve) => {{
                let timeout;
                let stabilityTimeout = {stability_ms};
                let maxTimeout = {timeout_ms};
                
                const observer = new MutationObserver(() => {{
                    clearTimeout(timeout);
                    timeout = setTimeout(() => {{
                        observer.disconnect();
                        resolve('stable');
                    }}, stabilityTimeout);
                }});
                
                observer.observe(document.body, {{ 
                    childList: true, 
                    subtree: true, 
                    attributes: true,
                    characterData: true
                }});
                
                // Max timeout fallback
                setTimeout(() => {{ 
                    observer.disconnect(); 
                    resolve('timeout'); 
                }}, maxTimeout);
                
                // Initial stability check
                timeout = setTimeout(() => {{ 
                    observer.disconnect(); 
                    resolve('stable'); 
                }}, stabilityTimeout);
            }})
        """)
    except Exception as e:
        print(f"  ⚠️ DOM stability wait error: {e}")
        await asyncio.sleep(2)
        return 'error'


async def expand_hidden_sections(page) -> int:
    """
    Click on accordions, tabs, and expandable sections to reveal hidden form fields.
    Returns: number of sections expanded
    """
    try:
        selectors_js = json.dumps(EXPANDABLE_SECTION_SELECTORS)
        expanded = await page.evaluate(f"""
            () => {{
                const expandSelectors = {selectors_js};
                let expanded = 0;
                
                expandSelectors.forEach(selector => {{
                    try {{
                        document.querySelectorAll(selector).forEach(el => {{
                            // Only click if it might contain form elements
                            const text = el.textContent || '';
                            const relevantKeywords = /form|contact|apply|register|sign|submit|info|detail|personal|account/i;
                            if (relevantKeywords.test(text) || expanded < 5) {{
                                el.click();
                                expanded++;
                            }}
                        }});
                    }} catch(e) {{}}
                }});
                
                return expanded;
            }}
        """)
        await asyncio.sleep(0.5)  # Wait for animations
        return expanded
    except Exception as e:
        print(f"  ⚠️ Section expansion error: {e}")
        return 0


async def scroll_and_detect_lazy_fields(page) -> int:
    """
    Scroll through page to trigger lazy-loaded fields.
    Detects when new fields appear and waits for them.
    
    Returns: number of new fields detected during scroll
    """
    try:
        return await page.evaluate("""
            async () => {
                const getFieldCount = () => document.querySelectorAll(
                    'input, select, textarea, [role="combobox"], [role="listbox"], ' +
                    '.ant-select, .MuiSelect-root, .v-select, .el-select'
                ).length;
                
                const initialCount = getFieldCount();
                let previousCount = initialCount;
                const scrollStep = Math.min(window.innerHeight * 0.7, 500);
                const maxScrolls = 20;
                let scrolls = 0;
                
                while (scrolls < maxScrolls && window.scrollY + window.innerHeight < document.body.scrollHeight) {
                    window.scrollBy(0, scrollStep);
                    await new Promise(r => setTimeout(r, 200));
                    
                    const newCount = getFieldCount();
                    if (newCount > previousCount) {
                        // New fields appeared, wait longer for them to fully render
                        await new Promise(r => setTimeout(r, 500));
                        previousCount = newCount;
                    }
                    scrolls++;
                }
                
                // Scroll back to top
                window.scrollTo({ top: 0, behavior: 'instant' });
                await new Promise(r => setTimeout(r, 300));
                
                return getFieldCount() - initialCount;
            }
        """)
    except Exception as e:
        print(f"  ⚠️ Scroll detection error: {e}")
        return 0


async def get_page_info(page) -> Dict[str, Any]:
    """
    Get basic information about the page.
    """
    try:
        return await page.evaluate("""
            () => ({
                title: document.title,
                url: window.location.href,
                formCount: document.querySelectorAll('form').length,
                inputCount: document.querySelectorAll('input, select, textarea').length,
                hasFrames: window.frames.length > 0,
                language: document.documentElement.lang || 'en'
            })
        """)
    except:
        return {}
