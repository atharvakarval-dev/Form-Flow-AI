from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Any
from pydantic import BaseModel
import asyncio
import json

from services.form.parser import get_form_schema, create_template
from core.dependencies import (
    get_voice_processor, get_speech_service, get_form_submitter, 
    get_gemini_service, update_speech_data
)
from services.voice.processor import VoiceProcessor
from services.voice.speech import SpeechService
from services.form.submitter import FormSubmitter
from services.ai.gemini import GeminiService, SmartFormFillerChain
from services.form.conventions import get_form_schema as get_schema
from services.ai.smart_autofill import get_smart_autofill
from core import database, models
import auth
from config.settings import settings
from sqlalchemy.future import select
from services.ai.profile_service import generate_profile_background

# --- Pydantic Models ---
class ScrapeRequest(BaseModel):
    url: str

class VoiceProcessRequest(BaseModel):
    transcript: str
    field_info: Dict[str, Any]
    form_context: str

class FormFillRequest(BaseModel):
    url: str
    form_data: Dict[str, str]

class FormSubmitRequest(BaseModel):
    url: str
    form_data: Dict[str, str]
    form_schema: List[Dict[str, Any]]
    use_cdp: bool = False  # If True, connect to user's browser via Chrome DevTools Protocol

class ConversationalFlowRequest(BaseModel):
    extracted_fields: Dict[str, str]
    form_schema: List[Dict[str, Any]]

class ComprehensiveFormRequest(BaseModel):
    url: str
    auto_generate_flow: bool = True

class MagicFillRequest(BaseModel):
    form_schema: List[Dict[str, Any]]
    user_profile: Dict[str, Any] = {}  # Optional extra profile data

router = APIRouter(tags=["Forms & Automation"])

# --- Helper Logic ---
async def _process_scraped_form(
    url: str, 
    voice_processor: VoiceProcessor,
    speech_service: SpeechService,
    generate_speech: bool = True
):
    """Shared helper to scrape and prepare form data"""
    
    # Get form schema
    result = await get_form_schema(url, generate_speech=False)
    form_schema = result['forms']
    
    # Generate speech
    speech_data = {}
    if generate_speech:
        print("Generating speech for fields...")
        for form in form_schema:
            for field in form.get('fields', []):
                fname = field.get('name')
                if fname:
                    prompt = speech_service._create_field_prompt(field)
                    audio = speech_service.text_to_speech(prompt)
                    if audio:
                        speech_data[fname] = {'audio': audio}
        
        # Update global state
        if speech_data:
            update_speech_data(speech_data)
    
    # Generate form context for LLM
    form_context = voice_processor.analyze_form_context(form_schema)
    
    # Generate initial prompts for each field
    enhanced_schema = []
    for form in form_schema:
        enhanced_form = form.copy()
        enhanced_form['fields'] = []
        for field in form['fields']:
            enhanced_field = field.copy()
            enhanced_field['smart_prompt'] = voice_processor.generate_smart_prompt(form_context, field)
            enhanced_form['fields'].append(enhanced_field)
        enhanced_schema.append(enhanced_form)

    # Statistics
    total_fields = sum(len(form.get('fields', [])) for form in form_schema)
    non_hidden_fields = sum(
        1 for form in form_schema 
        for field in form.get('fields', []) 
        if not field.get('hidden', False) and field.get('type') != 'submit'
    )
    
    return {
        "form_schema": enhanced_schema,
        "form_template": create_template(form_schema),
        "form_context": form_context,
        "speech_available": len(speech_data) > 0,
        "speech_fields": list(speech_data.keys()),
        "statistics": {
            "total_fields": total_fields,
            "visible_fields": non_hidden_fields,
            "hidden_fields": total_fields - non_hidden_fields
        }
    }


@router.post("/scrape")
async def scrape_form(
    data: ScrapeRequest,
    voice_processor: VoiceProcessor = Depends(get_voice_processor),
    speech_service: SpeechService = Depends(get_speech_service),
    gemini_service: GeminiService = Depends(get_gemini_service)
):
    """Scrape form schema and prepare for voice interaction."""
    print(f"Received URL for scraping: {data.url}")
    try:
        # Validate and normalize URL
        url = data.url.strip()
        if not url:
            raise HTTPException(status_code=400, detail="URL cannot be empty")
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        if url in ('http://', 'https://'):
            raise HTTPException(status_code=400, detail="Please enter a valid URL")
        
        print(f"Normalized URL: {url}")
        
        # Use shared helper
        processed_data = await _process_scraped_form(url, voice_processor, speech_service)
        
        return {
            "message": "Form scraped and analyzed successfully",
            **processed_data,
            "gemini_ready": gemini_service is not None
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.post("/comprehensive-form-setup")
async def comprehensive_form_setup(
    data: ComprehensiveFormRequest,
    voice_processor: VoiceProcessor = Depends(get_voice_processor),
    speech_service: SpeechService = Depends(get_speech_service),
    gemini_service: GeminiService = Depends(get_gemini_service)
):
    """endpoint that scrapes form and generates conversational flow in one call."""
    try:
        # Step 1 & 2: Scrape and Process using shared helper
        processed_data = await _process_scraped_form(data.url, voice_processor, speech_service)
        
        if not processed_data["form_schema"]:
            raise HTTPException(status_code=404, detail="No forms found on the provided URL")
            
        # Step 3: Generate initial conversational flow if requested
        conversational_flow = None
        if data.auto_generate_flow and gemini_service:
            flow_result = gemini_service.generate_conversational_flow({}, processed_data["form_schema"])
            if flow_result["success"]:
                conversational_flow = flow_result["conversational_flow"]
        
        return {
            "message": "Form setup completed successfully",
            **processed_data,
            "conversational_flow": conversational_flow,
            "ready_for_interaction": True,
            "gemini_ready": gemini_service is not None
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Comprehensive setup failed: {str(e)}")


@router.post("/process-voice")
async def process_voice(
    data: VoiceProcessRequest,
    voice_processor: VoiceProcessor = Depends(get_voice_processor)
):
    """Process voice input with LLM enhancement and smart formatting."""
    try:
        # Process with LLM
        result = voice_processor.process_voice_input(
            data.transcript, 
            data.field_info, 
            data.form_context
        )
        
        # Format the processed value
        formatted_value = voice_processor.format_field_value(
            result['processed_text'],
            data.field_info
        )
        result['processed_text'] = formatted_value
        
        # Add pronunciation validation
        pronunciation_check = voice_processor.validate_pronunciation(
            data.transcript, 
            data.field_info
        )
        result['pronunciation_check'] = pronunciation_check
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {str(e)}")


@router.post("/generate-conversational-flow")
async def generate_conversational_flow(
    data: ConversationalFlowRequest,
    gemini_service: GeminiService = Depends(get_gemini_service)
):
    """Generate conversational flow based on extracted fields using Gemini API."""
    try:
        if not gemini_service:
            raise HTTPException(status_code=500, detail="Gemini API not configured")
        
        result = gemini_service.generate_conversational_flow(
            data.extracted_fields,
            data.form_schema
        )
        
        if result["success"]:
            return {
                "message": "Conversational flow generated successfully",
                "flow": result["conversational_flow"],
                "remaining_fields": result["remaining_fields"],
                "extracted_count": len(data.extracted_fields),
                "remaining_count": len(result["remaining_fields"])
            }
        else:
            raise HTTPException(status_code=500, detail=f"Flow generation failed: {result['error']}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversational flow generation failed: {str(e)}")


@router.post("/pause-suggestions")
async def get_pause_suggestions(
    field_info: Dict[str, Any], 
    form_context: str = "",
    voice_processor: VoiceProcessor = Depends(get_voice_processor)
):
    """Get helpful suggestions when user pauses."""
    try:
        suggestions = voice_processor.handle_pause_suggestions(field_info, form_context)
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate suggestions: {str(e)}")


@router.post("/analyze-extracted-fields")
async def analyze_extracted_fields(
    data: ConversationalFlowRequest,
    gemini_service: GeminiService = Depends(get_gemini_service)
):
    """Analyze extracted fields and provide insights before generating conversational flow."""
    try:
        if not gemini_service:
            raise HTTPException(status_code=500, detail="Gemini API not configured")
        
        remaining_fields = gemini_service._get_remaining_fields(
            data.extracted_fields, 
            data.form_schema
        )
        
        total_fields = sum(len(form.get('fields', [])) for form in data.form_schema)
        non_hidden_fields = sum(
            1 for form in data.form_schema 
            for field in form.get('fields', []) 
            if not field.get('hidden', False) and field.get('type') != 'submit'
        )
        extracted_count = len(data.extracted_fields)
        completion_percentage = (extracted_count / non_hidden_fields * 100) if non_hidden_fields > 0 else 0
        
        return {
            "message": "Field analysis completed",
            "extracted_fields": data.extracted_fields,
            "remaining_fields": remaining_fields,
            "statistics": {
                "total_fields": non_hidden_fields,
                "extracted_count": extracted_count,
                "remaining_count": len(remaining_fields),
                "completion_percentage": round(completion_percentage, 1)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Field analysis failed: {str(e)}")


@router.post("/fill-form")
async def fill_form(data: FormFillRequest):
    """Automate form filling with processed data."""
    try:
        return {
            "message": "Form filling completed successfully",
            "filled_data": data.form_data,
            "url": data.url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Form filling failed: {str(e)}")


@router.post("/magic-fill")
async def magic_fill(
    data: MagicFillRequest,
    request: Request,
    db: AsyncSession = Depends(database.get_db),
    gemini_service: GeminiService = Depends(get_gemini_service)
):
    """
    🪄 Magic Fill - Intelligently pre-fill entire form from user profile.
    
    Uses LangChain + Gemini to map user data to form fields.
    """
    try:
        # 1. Get user profile from database if authenticated
        user_profile = dict(data.user_profile)  # Start with request data
        
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
                payload = auth.decode_access_token(token)
                if payload:
                    email = payload.get("sub")
                    if email:
                        result = await db.execute(select(models.User).filter(models.User.email == email))
                        user = result.scalars().first()
                        if user:
                            # Merge DB profile with request profile (request takes precedence)
                            db_profile = {
                                "first_name": user.first_name,
                                "last_name": user.last_name,
                                "email": user.email,
                                "mobile": user.mobile,
                                "city": user.city,
                                "state": user.state,
                                "country": user.country,
                                "fullname": f"{user.first_name} {user.last_name}".strip()
                            }
                            user_profile = {**db_profile, **user_profile}

                            # 🧠 Merge with learned history (fills gaps like Company, Title, specific addresses)
                            try:
                                history_profile = await get_smart_autofill().get_profile_from_history(str(user.id))
                                if history_profile:
                                    print(f"🧠 Merging {len(history_profile)} learned fields from history")
                                    # Base = History, Overlay = Current Result (DB + Request)
                                    # We want History to fill gaps, so History is the base.
                                    # But wait, user_profile already has DB+Request.
                                    # So: final = {**history_profile, **user_profile}
                                    # This ensures DB/Request values (verified/explicit) override History.
                                    user_profile = {**history_profile, **user_profile}
                            except Exception as e:
                                print(f"⚠️ History merge failed: {e}")
            except Exception as e:
                print(f"⚠️ Auth lookup failed: {e}")
        
        if not user_profile:
            return {
                "success": False,
                "error": "No user profile available",
                "filled": {},
                "unfilled": [],
                "summary": "Please sign in to use Magic Fill"
            }
        
        # 2. Call Smart Form Filler Chain
        if not gemini_service:
            raise HTTPException(status_code=500, detail="Gemini service not available")
        
        filler = SmartFormFillerChain(gemini_service.llm)
        result = await filler.fill(
            user_profile=user_profile,
            form_schema=data.form_schema,
            min_confidence=0.5
        )
        
        print(f"✨ Magic Fill: {len(result.get('filled', {}))} fields filled")
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Magic Fill failed: {str(e)}")


@router.post("/submit-form")
async def submit_form(
    data: FormSubmitRequest, 
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(database.get_db),
    form_submitter: FormSubmitter = Depends(get_form_submitter)
):
    """Submit form data with dynamic schema validation and formatting."""
    try:
        print(f"Submitting form to: {data.url}")
        print(f"Raw form data: {data.form_data}")
        
        schema = get_schema(data.url, form_data=data.form_schema)
        formatted_data = data.form_data

        if schema:
            formatted_data = schema.format_all(data.form_data)
            valid, errors = schema.validate_all(formatted_data)
            if not valid:
                return {
                    "success": False,
                    "message": "Validation failed",
                    "errors": errors,
                    "submitted_data": formatted_data
                }
            
            result = await form_submitter.submit_form_data(
                url=data.url,
                form_data=formatted_data,
                form_schema=data.form_schema,
                use_cdp=data.use_cdp
            )
        else:
            result = await form_submitter.submit_form_data(
                url=data.url,
                form_data=data.form_data,
                form_schema=data.form_schema,
                use_cdp=data.use_cdp
            )
        
        # --- History Tracking ---
        try:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                try:
                    payload = auth.decode_access_token(token)
                    if payload is None:
                        raise Exception("Invalid token")
                    email: str = payload.get("sub")
                    
                    if email:
                        user_res = await db.execute(select(models.User).filter(models.User.email == email))
                        user = user_res.scalars().first()
                        
                        if user:
                            status_str = "Success" if result and result.get("success") else "Failed"
                            submission = models.FormSubmission(
                                user_id=user.id,
                                form_url=data.url,
                                status=status_str
                            )
                            db.add(submission)
                            await db.commit()
                            print(f"📝 Recorded submission history for user {user.email}")
                            
                            # Learn from submission for Smart Autofill
                            try:
                                await get_smart_autofill().learn_from_submission(
                                    user_id=str(user.id),
                                    form_data=formatted_data,
                                    form_id=data.url
                                )
                                print(f"🧠 Smart Autofill learned from submission")
                            except Exception as e:
                                print(f"⚠️ Autofill learning failed: {e}")
                            
                            # 🧠 Queue background profile generation (non-blocking)
                            try:
                                if user.profiling_enabled and len(formatted_data) >= 5:
                                    background_tasks.add_task(
                                        generate_profile_background,
                                        user_id=user.id,
                                        form_data=formatted_data,
                                        form_type="Web Form",
                                        form_purpose=f"Form at {data.url[:50]}"
                                    )
                                    print(f"🧠 Profile generation queued for user {user.id}")
                            except Exception as e:
                                print(f"⚠️ Profile generation queue failed: {e}")
                except Exception as e:
                    print(f"⚠️ Failed to record history (Auth error): {e}")
        except Exception as e:
            print(f"⚠️ History tracking error: {e}")

        return {
            "message": result.get("message", "Form submission completed"),
            "success": result["success"],
            "details": result,
            "submitted_data": formatted_data
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Form submission failed: {str(e)}")
