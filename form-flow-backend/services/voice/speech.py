import os
import requests
from typing import Optional, Dict, Any

class SpeechService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Default voice ID (Rachel)
        self.default_voice_id = "21m00Tcm4TlvDq8ikWAM" 
        
    def text_to_speech(self, text: str, voice_id: str = None) -> Optional[bytes]:
        """Generate speech using ElevenLabs API"""
        if not self.api_key:
            print("ElevenLabs API key not configured")
            return None
            
        target_voice_id = voice_id or self.default_voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{target_voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        try:
            print(f"Generating speech via ElevenLabs for: '{text[:20]}...'")
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                return response.content
            else:
                print(f"ElevenLabs API Error ({response.status_code}): {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception calling ElevenLabs: {str(e)}")
            return None

    def _create_field_prompt(self, field_info: Dict[str, Any]) -> str:
        """Create a natural speech prompt for a form field"""
        label = field_info.get('label') or field_info.get('name') or "field"
        
        # Clean up label
        label = label.replace('*', '').strip()
        
        if field_info.get('type') == 'file':
            return f"Please upload the document for {label}"
        elif field_info.get('type') == 'submit':
            return ""
        
        return f"Please provide {label}"

    def get_streaming_response(self, text: str, voice_id: str = None):
        """Get streaming audio response"""
        if not self.api_key:
            yield b""
            return

        target_voice_id = voice_id or self.default_voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{target_voice_id}/stream"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        try:
            response = requests.post(url, json=data, headers=headers, stream=True)
            if response.status_code == 200:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        yield chunk
            else:
                print(f"ElevenLabs Stream Error: {response.text}")
                yield b""
        except Exception as e:
            print(f"Stream Exception: {e}")
            yield b""
