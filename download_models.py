"""
Download Local LLM Models

Script to download and setup local LLM models for Form Flow AI.
"""

import os
import sys
from pathlib import Path

def download_phi2_model():
    """Download Phi-2 model to local models directory."""
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        
        model_id = "microsoft/phi-2"
        models_dir = Path(__file__).parent / "models" / "phi-2"
        models_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📥 Downloading {model_id} to {models_dir}")
        
        # Download tokenizer
        print("Downloading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        tokenizer.save_pretrained(models_dir)
        
        # Download model
        print("Downloading model (this may take a while)...")
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            torch_dtype="auto"
        )
        model.save_pretrained(models_dir)
        
        print(f"✅ Model downloaded successfully to {models_dir}")
        print(f"📊 Model size: ~5.6GB")
        
    except ImportError:
        print("❌ transformers not installed. Run: pip install transformers torch")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Download failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_phi2_model()