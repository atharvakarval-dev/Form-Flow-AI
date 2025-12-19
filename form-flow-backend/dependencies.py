import os
from dotenv import load_dotenv
from typing import Optional

from gemini_service import GeminiService
from voice_processor import VoiceProcessor
from speech_service import SpeechService
from vosk_service import VoskService
from form_submitter import FormSubmitter

load_dotenv()

# --- Configuration ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")

if not GOOGLE_API_KEY:
    print("WARNING: GOOGLE_API_KEY not found. LLM integration will not work until this is set.")
if not ELEVENLABS_API_KEY:
    print("WARNING: ELEVENLABS_API_KEY not found. Speech generation will not work until this is set.")

# --- Singleton Instances ---
# We instantiate these once to reuse connections/models
_voice_processor = VoiceProcessor(openai_key=OPENAI_API_KEY, gemini_key=GOOGLE_API_KEY)
_speech_service = SpeechService(api_key=ELEVENLABS_API_KEY)
_form_submitter = FormSubmitter()
_gemini_service = GeminiService(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None
_vosk_service = VoskService()

# Global state for speech data (could be moved to a cache like Redis in production)
global_speech_data = {}

# --- Dependency Providers ---

def get_voice_processor() -> VoiceProcessor:
    return _voice_processor

def get_speech_service() -> SpeechService:
    return _speech_service

def get_form_submitter() -> FormSubmitter:
    return _form_submitter

def get_gemini_service() -> Optional[GeminiService]:
    return _gemini_service

def get_vosk_service() -> VoskService:
    return _vosk_service

def get_speech_data() -> dict:
    return global_speech_data

def update_speech_data(new_data: dict):
    global global_speech_data
    global_speech_data.update(new_data)
