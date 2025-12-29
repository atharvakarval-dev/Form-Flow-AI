"""
Local LLM Test Router

Provides endpoints to test local LLM functionality.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from services.ai.local_llm import get_local_llm_service, is_local_llm_available
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/local-llm", tags=["Local LLM"])


class ExtractRequest(BaseModel):
    user_input: str
    field_name: str


class ExtractResponse(BaseModel):
    value: str
    confidence: float
    source: str
    error: Optional[str] = None


class StatusResponse(BaseModel):
    available: bool
    model_loaded: bool
    device: str


@router.get("/status", response_model=StatusResponse)
async def get_local_llm_status():
    """Check if local LLM is available and loaded."""
    try:
        available = is_local_llm_available()
        service = get_local_llm_service() if available else None
        
        device = "unknown"
        model_loaded = False
        
        if service:
            model_loaded = service._initialized
            if service._initialized:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
        
        return StatusResponse(
            available=available,
            model_loaded=model_loaded,
            device=device
        )
    except Exception as e:
        logger.error(f"Error checking local LLM status: {e}")
        return StatusResponse(
            available=False,
            model_loaded=False,
            device="error"
        )


@router.post("/extract", response_model=ExtractResponse)
async def extract_field_value(request: ExtractRequest):
    """Extract field value using local LLM."""
    try:
        service = get_local_llm_service()
        if not service:
            raise HTTPException(
                status_code=503, 
                detail="Local LLM service not available"
            )
        
        result = service.extract_field_value(
            user_input=request.user_input,
            field_name=request.field_name
        )
        
        return ExtractResponse(**result)
        
    except Exception as e:
        logger.error(f"Local LLM extraction error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}"
        )


@router.post("/test")
async def test_local_llm():
    """Quick test of local LLM functionality."""
    try:
        service = get_local_llm_service()
        if not service:
            return {"status": "error", "message": "Local LLM not available"}
        
        # Test extraction
        result = service.extract_field_value(
            user_input="My name is John Smith",
            field_name="First Name"
        )
        
        return {
            "status": "success",
            "test_result": result,
            "message": "Local LLM is working"
        }
        
    except Exception as e:
        logger.error(f"Local LLM test error: {e}")
        return {
            "status": "error", 
            "message": f"Test failed: {str(e)}"
        }