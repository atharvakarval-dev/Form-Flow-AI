"""
Vosk Offline Speech-to-Text Service
Uses local Vosk models for privacy-preserving, offline transcription.
"""

import os
import json
from typing import Dict, Any, Optional

try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False


class VoskService:
    def __init__(self, model_path: str = None):
        if not VOSK_AVAILABLE:
            print("⚠️ Vosk not installed. Basic transcription unavailable.")
            self.model = None
            return

        # Disable vosk logs
        SetLogLevel(-1)
        
        # Default model path relative to this file
        if not model_path:
            # Check for the model in the parent directory (project root)
            # User has: d:\Form-Flow-AI\vosk-model-en-in-0.5
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            
            possible_paths = [
                os.path.join(parent_dir, "vosk-model-small-en-in-0.4"),
                r"d:\Form-Flow-AI\vosk-model-small-en-in-0.4"  # Small model - faster for real-time
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    model_path = path
                    break
        
        if model_path and os.path.exists(model_path):
            print(f"🎤 Loading Vosk model from: {model_path}")
            try:
                self.model = Model(model_path)
                print("✅ Vosk model loaded successfully")
            except Exception as e:
                print(f"❌ Failed to load Vosk model: {e}")
                self.model = None
        else:
            print(f"⚠️ Vosk model not found at {model_path or possible_paths}")
            self.model = None

    def is_available(self) -> bool:
        return self.model is not None

    def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> Dict[str, Any]:
        """
        Transcribe raw audio data using Vosk.
        Expects PCM 16kHz mono audio by default.
        """
        if not self.model:
            return {
                "success": False,
                "error": "Vosk model not loaded",
                "transcript": ""
            }

        try:
            rec = KaldiRecognizer(self.model, sample_rate)
            rec.SetWords(True)
            
            # Vosk expects bytes, and processes chunks or whole stream
            if rec.AcceptWaveform(audio_data):
                res = json.loads(rec.Result())
            else:
                res = json.loads(rec.FinalResult())
                
            text = res.get("text", "")
            
            if text:
                return {
                    "success": True,
                    "transcript": text,
                    "confidence": 1.0, # Vosk doesn't provide overall confidence easily in simple mode
                    "provider": "vosk"
                }
            else:
                 return {
                    "success": False,
                    "error": "No speech detected",
                    "transcript": ""
                }
                
        except Exception as e:
            print(f"❌ Vosk transcription error: {e}")
            return {
                "success": False,
                "error": str(e),
                "transcript": ""
            }
