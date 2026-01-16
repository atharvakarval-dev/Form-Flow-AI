@echo off
echo Installing dependencies for Form Flow AI...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install transformers sentencepiece accelerate bitsandbytes
echo.
echo Dependencies installed! You can now run:
echo python download_models.py
pause
