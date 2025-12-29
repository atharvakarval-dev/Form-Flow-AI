"""
Test script for local LLM inference using Phi-2 (2.7B parameters)
Optimized for 8GB VRAM with 4-bit quantization
"""
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Microsoft Phi-2 - excellent for reasoning tasks, 2.7B params
MODEL_ID = "microsoft/phi-2"

print(f"Loading model: {MODEL_ID}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

# Load model optimized for CPU
if torch.cuda.is_available():
    # GPU path with quantization
    from transformers import BitsAndBytesConfig
    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        llm_int8_enable_fp32_cpu_offload=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        device_map="auto",
        quantization_config=quant_config,
        trust_remote_code=True,
        dtype=torch.float16
    )
else:
    # CPU path - no quantization, smaller precision
    print("⚠️ No GPU detected, loading on CPU (slower)...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        device_map="cpu",
        trust_remote_code=True,
        dtype=torch.float32,
        low_cpu_mem_usage=True
    )

print("\n✅ Model loaded successfully!")
print(f"Model size: ~{sum(p.numel() for p in model.parameters()) / 1e9:.2f}B parameters")

# Test inference - simulate a form-filling task
test_prompt = """Extract the field value from the user input.

Field: First Name
User said: "My name is John Smith"
Extracted value:"""

print(f"\n--- Test Prompt ---\n{test_prompt}")

inputs = tokenizer(test_prompt, return_tensors="pt").to(model.device)
outputs = model.generate(
    **inputs,
    max_new_tokens=32,
    temperature=0.1,
    do_sample=True,
    pad_token_id=tokenizer.eos_token_id
)

response = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(f"\n--- Model Response ---\n{response}")
print("\n✅ Local LLM test complete!")
