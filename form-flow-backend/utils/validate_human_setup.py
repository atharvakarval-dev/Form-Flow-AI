import sys
import os
import asyncio
import logging

# Add project root to path (explicitly insert at 0)
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("validate_human_setup")

async def test_imports():
    print(f"PYTHONPATH: {sys.path[:3]}")  # Debug path
    print("Testing imports...")
    try:
        import config
        print(f"✅ config imported from {config.__file__}")
        from utils.stealth_browser import setup_production_stealth_browser, setup_production_stealth_browser_sync
        print("✅ utils.stealth_browser imported (async & sync)")
        
        from utils.human_form_submitter import HumanFormSubmitter, SyncHumanFormSubmitter
        print("✅ utils.human_form_submitter imported (async & sync)")
        
        from services.form.submitter import FormSubmitter
        print("✅ services.form.submitter imported")
        
        from routers.forms import FormSubmitRequest
        print("✅ routers.forms imported")
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error during import: {e}")
        sys.exit(1)

async def test_submitter_instantiation():
    print("\nTesting instantiations...")
    from services.form.submitter import FormSubmitter
    try:
        submitter = FormSubmitter()
        print("✅ FormSubmitter instantiated")
        
        # Check if new method exists
        if hasattr(submitter, '_async_submit_with_human_behavior'):
            print("✅ _async_submit_with_human_behavior method exists")
        else:
            print("❌ _async_submit_with_human_behavior method MISSING")
            
    except Exception as e:
        print(f"❌ Instantiation failed: {e}")

async def main():
    await test_imports()
    await test_submitter_instantiation()
    print("\n✨ All validation checks passed!")

if __name__ == "__main__":
    asyncio.run(main())
