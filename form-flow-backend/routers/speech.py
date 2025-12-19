from fastapi import APIRouter, HTTPException, Depends, Response, UploadFile, File
from typing import Dict, Any

from speech_service import SpeechService
from vosk_service import VoskService
from dependencies import get_speech_service, get_vosk_service, get_speech_data

router = APIRouter(tags=["Speech & Audio"])

@router.get("/speech/{field_name}")
async def get_field_speech_audio(
    field_name: str,
    speech_service: SpeechService = Depends(get_speech_service),
    speech_data: dict = Depends(get_speech_data)
):
    """Get speech audio for a specific form field"""
    try:
        print(f"Requesting speech for field: {field_name}")
        
        # Check if we have pre-generated speech data in the global cache
        if field_name in speech_data:
            audio_data = speech_data[field_name].get('audio')
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

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    vosk_service: VoskService = Depends(get_vosk_service)
):
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
