"""
Updated profiler: test with standard HTML forms since Google Forms blocks headless.
Also shows 2nd-run improvement (browser pool reuse).
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def profile_url(url: str, run_label: str = "Run"):
    print(f"\n{'='*60}")
    print(f"{run_label}: {url}")
    print(f"{'='*60}\n")
    
    total_start = time.time()
    
    # Stage 1: Playwright scrape
    print("━━━ STAGE 1: Playwright scrape ━━━")
    t1 = time.time()
    
    from services.form.parser import get_form_schema
    import asyncio
    
    result = asyncio.run(get_form_schema(url, generate_speech=False))
    t2 = time.time()
    
    form_schema = result.get('forms', [])
    total_fields = sum(len(f.get('fields', [])) for f in form_schema)
    print(f"⏱️  Stage 1 (Playwright): {t2 - t1:.2f}s")
    print(f"   Forms: {len(form_schema)}, Fields: {total_fields}")
    
    # Stage 2: Smart prompts
    print("\n━━━ STAGE 2: Smart prompts ━━━")
    t3 = time.time()
    
    from services.voice.processor import VoiceProcessor
    from config.settings import settings
    
    vp = VoiceProcessor(openrouter_key=settings.OPENROUTER_API_KEY)
    if form_schema:
        form_context = vp.analyze_form_context(form_schema)
        for form in form_schema:
            for field in form.get('fields', []):
                field['smart_prompt'] = vp.generate_smart_prompt(form_context, field)
    
    t4 = time.time()
    print(f"⏱️  Stage 2 (Prompts): {t4 - t3:.2f}s")
    
    # Summary (no TTS or Magic Fill — those are non-blocking now)
    total_end = time.time()
    print(f"\n{'='*60}")
    print(f"TIMING (scrape response time — Magic Fill would be background):")
    print(f"  Playwright scrape: {t2 - t1:.2f}s")
    print(f"  Smart prompts:     {t4 - t3:.2f}s")
    print(f"  RESPONSE TOTAL:    {total_end - total_start:.2f}s")
    print(f"  Forms: {len(form_schema)}, Fields: {total_fields}")
    print(f"{'='*60}")
    return total_end - total_start


if __name__ == "__main__":
    # Test with standard HTML forms
    test_urls = [
        "https://httpbin.org/forms/post",  # Simple HTML form
    ]
    
    url = sys.argv[1] if len(sys.argv) > 1 else test_urls[0]
    
    # First run (cold-start — includes browser launch)
    t1 = profile_url(url, "COLD START (1st run)")
    
    # Second run (warm — browser pool should be reused)
    t2 = profile_url(url, "WARM (2nd run)")
    
    print(f"\n🚀 SPEEDUP: {t1:.2f}s → {t2:.2f}s ({t1/t2:.1f}x faster on warm run)")
