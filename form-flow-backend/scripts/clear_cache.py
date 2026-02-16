import sys
import os
import asyncio
import logging

# Setup path to include backend root
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

# Configure logging
logging.basicConfig(level=logging.INFO)

from utils.api_cache import invalidate_form_cache

async def main():
    target_url = "https://www.zensar.com/contact-us"
    
    print(f"🧹 Clearing cache for: {target_url}")
    
    # 1. Clear form schema cache
    await invalidate_form_cache(target_url)
    
    # 2. Also check if there are other related keys (e.g. smart prompts)
    # The prefix for form schema is "form_schema:"
    # We rely on invalidate_form_cache logic
    
    print("✅ Cache cleared successfully.")
    print("Please refresh the frontend to re-scrape.")

if __name__ == "__main__":
    asyncio.run(main())
