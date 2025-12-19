from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, HttpUrl
import uvicorn
import os
from dotenv import load_dotenv
import google.generativeai as genai
import time
import asyncio
import json
from typing import Dict, List, Any

from form_parser import get_form_schema, create_template, get_field_speech
from voice_processor import VoiceProcessor
from speech_service import SpeechService
from form_submitter import FormSubmitter
from gemini_service import GeminiService
from vosk_service import VoskService
from form_conventions import get_form_schema as get_schema, FormSchema

# Auth & DB Imports
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import models, schemas, auth, database

# Load environment variables from .env file
load_dotenv()


# --- API Configuration ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not GOOGLE_API_KEY:
    print("WARNING: GOOGLE_API_KEY not found. LLM integration will not work until this is set.")

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
global_speech_data = {}

if not ELEVENLABS_API_KEY:
    print("WARNING: ELEVENLABS_API_KEY not found. Speech generation will not work until this is set.")

# Initialize Voice Processor, Speech Service, Form Submitter, and Gemini Service
voice_processor = VoiceProcessor(openai_key=OPENAI_API_KEY, gemini_key=GOOGLE_API_KEY)
speech_service = SpeechService(api_key=ELEVENLABS_API_KEY)

form_submitter = FormSubmitter()
gemini_service = GeminiService(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None
vosk_service = VoskService()

app = FastAPI()

# Configure CORS to allow requests from your React frontend
origins = [
    "http://localhost:5173", # Default port for Vite/React development server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Initialization ---
@app.on_event("startup")
async def startup_event():
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

# --- User & Auth Endpoints ---

@app.post("/register", response_model=schemas.UserResponse)
async def register(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    # Check if email exists
    result = await db.execute(select(models.User).filter(models.User.email == user.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        password_hash=hashed_password,
        first_name=user.first_name,
        last_name=user.last_name,
        mobile=user.mobile,
        country=user.country,
        state=user.state,
        city=user.city,
        pincode=user.pincode
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@app.post("/login", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(database.get_db)):
    # Authenticate user
    result = await db.execute(select(models.User).filter(models.User.email == form_data.username))
    user = result.scalars().first()
    
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = auth.timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=schemas.UserResponse)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@app.get("/history", response_model=List[schemas.FormSubmissionResponse])
async def get_history(current_user: models.User = Depends(auth.get_current_user), db: AsyncSession = Depends(database.get_db)):
    result = await db.execute(
        select(models.FormSubmission)
        .filter(models.FormSubmission.user_id == current_user.id)
        .order_by(models.FormSubmission.timestamp.desc())
    )
    return result.scalars().all()


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

class SpeechRequest(BaseModel):
    field_name: str

class StreamSpeechRequest(BaseModel):
    text: str
    voice_id: str = None

class ConversationalFlowRequest(BaseModel):
    extracted_fields: Dict[str, str]
    form_schema: List[Dict[str, Any]]

class SmartFormRequest(BaseModel):
    url: str
    extracted_fields: Dict[str, str] = {}

class ComprehensiveFormRequest(BaseModel):
    url: str
    auto_generate_flow: bool = True



@app.post("/scrape")
async def scrape_form(data: ScrapeRequest):
    """Scrape form schema and prepare for voice interaction."""
    global global_speech_data
    print(f"Received URL for scraping: {data.url}")
    try:
        # Validate and normalize URL
        url = data.url.strip()
        if not url:
            raise HTTPException(status_code=400, detail="URL cannot be empty")
        
        # Add https:// if no scheme present
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Validate URL has domain
        if url in ('http://', 'https://'):
            raise HTTPException(status_code=400, detail="Please enter a valid URL")
        
        print(f"Normalized URL: {url}")
        
        # Get form schema
        result = await get_form_schema(url, generate_speech=False)
        form_schema = result['forms']
        
        # Generate speech
        speech_data = {}
        print("Generating speech for fields...")
        for form in form_schema:
            for field in form.get('fields', []):
                fname = field.get('name')
                if fname:
                    prompt = speech_service._create_field_prompt(field)
                    audio = speech_service.text_to_speech(prompt)
                    if audio:
                        speech_data[fname] = {'audio': audio}
        
        # Store speech data globally
        global_speech_data = speech_data
        
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

        # Prepare response with Gemini integration readiness
        response_data = {
            "message": "Form scraped and analyzed successfully",
            "form_schema": enhanced_schema,
            "form_template": template,
            "form_context": form_context,
            "speech_available": len(speech_data) > 0,
            "speech_fields": list(speech_data.keys()),
            "gemini_ready": gemini_service is not None
        }
        
        # Add field statistics
        total_fields = sum(len(form.get('fields', [])) for form in form_schema)
        non_hidden_fields = sum(
            1 for form in form_schema 
            for field in form.get('fields', []) 
            if not field.get('hidden', False) and field.get('type') != 'submit'
        )
        
        response_data["field_statistics"] = {
            "total_fields": total_fields,
            "visible_fields": non_hidden_fields,
            "hidden_fields": total_fields - non_hidden_fields
        }

        return response_data

    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@app.post("/process-voice")
async def process_voice(data: VoiceProcessRequest):
    """Process voice input with LLM enhancement and smart formatting."""
    try:
        # Process with LLM
        result = voice_processor.process_voice_input(
            data.transcript, 
            data.field_info, 
            data.form_context
        )
        
        # Format the processed value (fix STT errors, strengthen passwords, etc.)
        formatted_value = voice_processor.format_field_value(
            result['processed_text'],
            data.field_info
        )
        
        result['processed_text'] = formatted_value
        
        # Add pronunciation validation for sensitive fields
        pronunciation_check = voice_processor.validate_pronunciation(
            data.transcript, 
            data.field_info
        )
        
        result['pronunciation_check'] = pronunciation_check
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {str(e)}")


@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio using local Vosk model (Indian English).
    Note: Requires generic WAV or PCM format. Browser WebM might fail without transcoding.
    """
    try:
        if not vosk_service or not vosk_service.is_available():
            return {
                "success": False,
                "error": "Vosk model not loaded. Check backend logs.",
                "transcript": "",
                "use_browser_fallback": True
            }
        
        # Read audio data
        audio_data = await audio.read()
        content_type = audio.content_type or "audio/wav"
        
        print(f"🎤 Received audio for Vosk: {len(audio_data)} bytes, type: {content_type}")
        
        # Determine likely sample rate based on header (simple heuristic)
        # Using 16000 default as Vosk model expects 16k usually
        result = vosk_service.transcribe_audio(audio_data, sample_rate=16000)
            
        if result["success"]:
            print(f"✅ Vosk transcription: {result['transcript'][:100]}...")
            return {
                "success": True,
                "transcript": result["transcript"],
                "confidence": result.get("confidence", 1.0),
                "provider": "vosk",
                "words": []
            }
        else:
            print(f"⚠️ Vosk transcription failed: {result.get('error')}")
            return {
                "success": False,
                "error": result.get("error", "Transcription failed"),
                "transcript": "",
                "use_browser_fallback": True
            }
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "transcript": "",
            "use_browser_fallback": True
        }


@app.post("/generate-conversational-flow")
async def generate_conversational_flow(data: ConversationalFlowRequest):
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

@app.post("/pause-suggestions")
async def get_pause_suggestions(field_info: Dict[str, Any], form_context: str = ""):
    """Get helpful suggestions when user pauses."""
    try:
        suggestions = voice_processor.handle_pause_suggestions(field_info, form_context)
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate suggestions: {str(e)}")

@app.post("/analyze-extracted-fields")
async def analyze_extracted_fields(data: ConversationalFlowRequest):
    """Analyze extracted fields and provide insights before generating conversational flow."""
    try:
        if not gemini_service:
            raise HTTPException(status_code=500, detail="Gemini API not configured")
        
        # Get remaining fields
        remaining_fields = gemini_service._get_remaining_fields(
            data.extracted_fields, 
            data.form_schema
        )
        
        # Calculate completion percentage
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




@app.get("/speech/{field_name}")
async def get_field_speech_audio(field_name: str):
    """Get speech audio for a specific form field"""
    try:
        print(f"Requesting speech for field: {field_name}")
        
        # Check if we have pre-generated speech data
        if field_name in global_speech_data:
            audio_data = global_speech_data[field_name].get('audio')
            if audio_data:
                return Response(content=audio_data, media_type="audio/mpeg")
        
        # Generate on demand if not found
        print(f"Generating speech on demand for {field_name}")
        field_info = {'name': field_name, 'type': 'text', 'label': field_name}
        prompt_text = speech_service._create_field_prompt(field_info)
        audio_data = speech_service.text_to_speech(prompt_text)
        
        if audio_data:
            return Response(content=audio_data, media_type="audio/mpeg")
        else:
            raise HTTPException(status_code=500, detail="Failed to generate speech")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech generation failed: {str(e)}")

@app.post("/fill-form")
async def fill_form(data: FormFillRequest):
    """Automate form filling with processed data."""
    try:
        # This would integrate with Playwright to actually fill the form
        # For now, return success with the data that would be filled
        return {
            "message": "Form filling completed successfully",
            "filled_data": data.form_data,
            "url": data.url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Form filling failed: {str(e)}")

@app.post("/submit-form")
async def submit_form(
    data: FormSubmitRequest, 
    request: Request,
    db: AsyncSession = Depends(database.get_db)
):
    """Submit form data with dynamic schema validation and formatting."""
    try:
        print(f"Submitting form to: {data.url}")
        print(f"Raw form data: {data.form_data}")
        
        # Build schema dynamically from scraped form_schema
        schema = get_schema(data.url, form_data=data.form_schema)
        
        result = None
        formatted_data = data.form_data

        if schema:
            print(f"✅ Built schema with {len(schema.fields)} fields")
            
            # Apply formatting according to schema
            formatted_data = schema.format_all(data.form_data)
            print(f"✨ Formatted data: {formatted_data}")
            
            # Validate all fields
            valid, errors = schema.validate_all(formatted_data)
            if not valid:
                print(f"⚠️ Validation errors: {errors}")
                return {
                    "success": False,
                    "message": "Validation failed",
                    "errors": errors,
                    "submitted_data": formatted_data
                }
            
            # Submit with formatted data
            result = await form_submitter.submit_form_data(
                url=data.url,
                form_data=formatted_data,  # Use formatted data
                form_schema=data.form_schema
            )
        else:
            # No schema available, use raw data
            print("⚠️ No schema built, using raw data")
            result = await form_submitter.submit_form_data(
                url=data.url,
                form_data=data.form_data,
                form_schema=data.form_schema
            )
        
        # --- History Tracking ---
        try:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                try:
                    # Manually verify to avoid failing the whole request on invalid token
                    payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
                    email: str = payload.get("sub")
                    
                    if email:
                        # Find user
                        user_res = await db.execute(select(models.User).filter(models.User.email == email))
                        user = user_res.scalars().first()
                        
                        if user:
                            # Record submission
                            status_str = "Success" if result and result.get("success") else "Failed"
                            submission = models.FormSubmission(
                                user_id=user.id,
                                form_url=data.url,
                                status=status_str
                            )
                            db.add(submission)
                            await db.commit()
                            print(f"📝 Recorded submission history for user {user.email}")
                except Exception as e:
                    print(f"⚠️ Failed to record history (Auth error): {e}")
        except Exception as e:
            print(f"⚠️ History tracking error: {e}")

        return {
            "message": "Form submission completed",
            "success": result["success"],
            "details": result,
            "submitted_data": formatted_data
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Form submission failed: {str(e)}")




@app.post("/comprehensive-form-setup")
async def comprehensive_form_setup(data: ComprehensiveFormRequest):
    """Comprehensive endpoint that scrapes form and generates conversational flow in one call."""
    global global_speech_data
    try:
        # Step 1: Scrape form schema without speech generation
        result = await get_form_schema(str(data.url), generate_speech=False)
        form_schema = result['forms']
        
        if not form_schema:
            raise HTTPException(status_code=404, detail="No forms found on the provided URL")
            
        # Generate speech
        speech_data = {}
        for form in form_schema:
            for field in form.get('fields', []):
                fname = field.get('name')
                if fname:
                    prompt = speech_service._create_field_prompt(field)
                    audio = speech_service.text_to_speech(prompt)
                    if audio:
                        speech_data[fname] = {'audio': audio}
        
        # Store speech data globally
        global_speech_data = speech_data
        
        # Step 2: Generate form context and enhanced schema
        form_context = voice_processor.analyze_form_context(form_schema)
        enhanced_schema = []
        
        for form in form_schema:
            enhanced_form = form.copy()
            enhanced_form['fields'] = []
            for field in form['fields']:
                enhanced_field = field.copy()
                enhanced_field['smart_prompt'] = voice_processor.generate_smart_prompt(form_context, field)
                enhanced_form['fields'].append(enhanced_field)
            enhanced_schema.append(enhanced_form)
        
        # Step 3: Generate initial conversational flow if requested
        conversational_flow = None
        if data.auto_generate_flow and gemini_service:
            flow_result = gemini_service.generate_conversational_flow({}, enhanced_schema)
            if flow_result["success"]:
                conversational_flow = flow_result["conversational_flow"]
        
        # Step 4: Calculate statistics
        total_fields = sum(len(form.get('fields', [])) for form in form_schema)
        non_hidden_fields = sum(
            1 for form in form_schema 
            for field in form.get('fields', []) 
            if not field.get('hidden', False) and field.get('type') != 'submit'
        )
        
        return {
            "message": "Form setup completed successfully",
            "form_schema": enhanced_schema,
            "form_template": create_template(form_schema),
            "form_context": form_context,
            "conversational_flow": conversational_flow,
            "speech_available": len(speech_data) > 0,
            "speech_fields": list(speech_data.keys()),
            "statistics": {
                "total_fields": total_fields,
                "visible_fields": non_hidden_fields,
                "hidden_fields": total_fields - non_hidden_fields,
                "completion_percentage": 0
            },
            "ready_for_interaction": True,
            "gemini_ready": gemini_service is not None
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Comprehensive setup failed: {str(e)}")

@app.get("/")
def read_root():
    return {"Hello": "Form Wizard Pro Backend is running"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


