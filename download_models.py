"""
Download Local LLM Models

Script to download and setup local LLM models for Form Flow AI.
"""

import os
import sys
import shutil
from pathlib import Path

def download_phi2_model():
    """Download Phi-2 model to local models directory."""
    try:
        print("🔍 Checking dependencies...")
        try:
            import torch
            import transformers
            from transformers import AutoTokenizer, AutoModelForCausalLM
            print(f"✅ Transformers version: {transformers.__version__}")
            print(f"✅ PyTorch version: {torch.__version__}")
        except ImportError as e:
            print(f"❌ Missing dependencies: {e}")
            print("Please run: pip install transformers torch sentencepiece")
            sys.exit(1)

        model_id = "microsoft/phi-2"
        # Determine project root
        project_root = Path(__file__).parent
        models_dir = project_root / "models" / "phi-2"
        
        print(f"📂 Target directory: {models_dir}")
        models_dir.mkdir(parents=True, exist_ok=True)
        
        # Check disk space (need ~6GB)
        total, used, free = shutil.disk_usage(models_dir.parent)
        free_gb = free / (1024**3)
        print(f"💾 Free disk space: {free_gb:.2f} GB")
        if free_gb < 7:
            print("⚠️ WARNING: You have less than 7GB of free space. Download might fail.")
            confirm = input("Continue anyway? (y/n): ")
            if confirm.lower() != 'y':
                sys.exit(0)
        
        print(f"📥 Starting download of {model_id}...")
        print("   This may take 5-10 minutes depending on your internet connection.")
        
        # Download tokenizer
        print("⏳ Downloading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        tokenizer.save_pretrained(models_dir)
        print("✅ Tokenizer saved.")
        
        # Download model
        print("⏳ Downloading model (approx 5.6GB)...")
        # Use locally_files_only=False to ensure we check remote, but verify cache
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            torch_dtype="auto",
            device_map="auto" if torch.cuda.is_available() else "cpu"
        )
        model.save_pretrained(models_dir)
        
        print(f"✅ Model downloaded successfully to: {models_dir}")
        print("🎉 You can now run the backend with Local LLM enabled!")
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR during download:")
        print(f"{str(e)}")
        print("\nTroubleshooting:")
        print("1. Check your internet connection")
        print("2. Ensure you have enough disk space (~6GB)")
        print("3. Try running: pip install --upgrade transformers torch accelerat")
        sys.exit(1)

if __name__ == "__main__":
    download_phi2_model()