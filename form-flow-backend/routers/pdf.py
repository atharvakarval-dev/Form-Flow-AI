"""
PDF Router - API Endpoints for PDF Form Operations

Provides REST API for:
- PDF upload and parsing
- Form field extraction
- PDF filling with user data
- Filled PDF download

Integrates with existing conversation agent for voice-powered filling.
"""

import logging
import tempfile
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
import io
import uuid

from config.settings import settings
from utils.logging import get_logger
from services.pdf import parse_pdf, fill_pdf, PdfFormSchema, TextFitter

logger = get_logger(__name__)

router = APIRouter(prefix="/pdf", tags=["PDF"])


# =============================================================================
# Request/Response Models
# =============================================================================

class PdfUploadResponse(BaseModel):
    """Response from PDF upload."""
    success: bool
    pdf_id: str
    file_name: str
    total_pages: int
    total_fields: int
    fields: List[Dict[str, Any]]
    is_scanned: bool = False
    message: str = ""


class FillPdfRequest(BaseModel):
    """Request to fill a PDF."""
    pdf_id: str = Field(..., description="ID from upload response")
    data: Dict[str, str] = Field(..., description="Field name to value mapping")
    flatten: bool = Field(False, description="Make form fields non-editable")


class FillPdfResponse(BaseModel):
    """Response from PDF fill operation."""
    success: bool
    download_id: str
    fields_filled: int
    fields_failed: int
    warnings: List[str] = []
    preview: Dict[str, Any] = {}


class PreviewFillRequest(BaseModel):
    """Request to preview fill without creating PDF."""
    pdf_id: str
    data: Dict[str, str]


# =============================================================================
# In-Memory Storage (Replace with Redis/DB in production)
# =============================================================================

# Store uploaded PDFs temporarily
_pdf_storage: Dict[str, bytes] = {}
_pdf_metadata: Dict[str, Dict[str, Any]] = {}
_filled_pdfs: Dict[str, bytes] = {}


def _cleanup_pdf(pdf_id: str):
    """Remove PDF from storage after timeout."""
    _pdf_storage.pop(pdf_id, None)
    _pdf_metadata.pop(pdf_id, None)


def _cleanup_filled(download_id: str):
    """Remove filled PDF after timeout."""
    _filled_pdfs.pop(download_id, None)


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/upload", response_model=PdfUploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Upload a PDF form for parsing.
    
    Returns extracted form fields ready for filling.
    """
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted"
        )
    
    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"Error reading uploaded file: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Error reading file: {str(e)}"
        )
    
    # Parse PDF
    try:
        schema = parse_pdf(content)
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="PDF parsing libraries not installed. Run: pip install pdfplumber pypdf"
        )
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Error parsing PDF: {str(e)}"
        )
    
    # Generate ID and store
    pdf_id = str(uuid.uuid4())
    _pdf_storage[pdf_id] = content
    _pdf_metadata[pdf_id] = {
        "file_name": file.filename,
        "schema": schema.to_dict(),
    }
    
    # Schedule cleanup after 1 hour
    if background_tasks:
        background_tasks.add_task(
            lambda: _cleanup_pdf(pdf_id),
        )
    
    # Format fields for response
    fields = [f.to_dict() for f in schema.fields]
    
    return PdfUploadResponse(
        success=True,
        pdf_id=pdf_id,
        file_name=file.filename,
        total_pages=schema.total_pages,
        total_fields=schema.total_fields,
        fields=fields,
        is_scanned=schema.is_scanned,
        message=f"Found {schema.total_fields} fillable fields",
    )


@router.get("/schema/{pdf_id}")
async def get_pdf_schema(pdf_id: str):
    """
    Get the parsed schema for an uploaded PDF.
    
    Returns field information in format compatible with conversation agent.
    """
    if pdf_id not in _pdf_metadata:
        raise HTTPException(
            status_code=404,
            detail="PDF not found. Upload again."
        )
    
    metadata = _pdf_metadata[pdf_id]
    schema = metadata["schema"]
    
    # Convert to conversation-agent compatible format
    fields = []
    for field in schema.get("fields", []):
        fields.append({
            "name": field.get("name"),
            "id": field.get("id"),
            "type": field.get("type", "text"),
            "label": field.get("display_name") or field.get("label") or field.get("name"),
            "required": field.get("constraints", {}).get("required", False),
            "options": field.get("options", []),
            "max_length": field.get("constraints", {}).get("max_length"),
            "purpose": field.get("purpose"),
        })
    
    return {
        "pdf_id": pdf_id,
        "file_name": metadata["file_name"],
        "total_pages": schema.get("total_pages", 1),
        "fields": fields,
        "source": "pdf",
    }


@router.post("/preview")
async def preview_fill(request: PreviewFillRequest):
    """
    Preview how data would be filled into PDF fields.
    
    Shows text fitting results without creating actual PDF.
    """
    if request.pdf_id not in _pdf_storage:
        raise HTTPException(
            status_code=404,
            detail="PDF not found. Upload again."
        )
    
    pdf_bytes = _pdf_storage[request.pdf_id]
    fitter = TextFitter()
    
    # Get schema
    metadata = _pdf_metadata[request.pdf_id]
    fields_dict = {f["name"]: f for f in metadata["schema"]["fields"]}
    
    preview = {}
    for field_name, value in request.data.items():
        field_info = fields_dict.get(field_name, {})
        max_length = field_info.get("constraints", {}).get("max_length")
        text_capacity = field_info.get("text_capacity")
        
        effective_max = max_length or text_capacity or 100
        
        fit_result = fitter.fit(
            value,
            effective_max,
            {"purpose": field_info.get("purpose"), "name": field_name}
        )
        
        preview[field_name] = {
            "original": value,
            "fitted": fit_result.fitted,
            "strategy": fit_result.strategy_used,
            "truncated": fit_result.truncated,
            "changes": fit_result.changes_made,
        }
    
    return {
        "success": True,
        "preview": preview,
    }


@router.post("/fill", response_model=FillPdfResponse)
async def fill_pdf_endpoint(
    request: FillPdfRequest,
    background_tasks: BackgroundTasks,
):
    """
    Fill PDF form with provided data.
    
    Returns download ID for retrieving filled PDF.
    """
    if request.pdf_id not in _pdf_storage:
        raise HTTPException(
            status_code=404,
            detail="PDF not found. Upload again."
        )
    
    pdf_bytes = _pdf_storage[request.pdf_id]
    
    try:
        result = fill_pdf(
            template_path=pdf_bytes,
            data=request.data,
            flatten=request.flatten,
        )
    except Exception as e:
        logger.error(f"Error filling PDF: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error filling PDF: {str(e)}"
        )
    
    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fill PDF: {', '.join(result.errors)}"
        )
    
    # Store filled PDF
    download_id = str(uuid.uuid4())
    _filled_pdfs[download_id] = result.output_bytes
    
    # Cleanup after 30 minutes
    background_tasks.add_task(lambda: _cleanup_filled(download_id))
    
    # Build preview from results
    preview = {}
    for fr in result.field_results:
        preview[fr.field_name] = {
            "success": fr.success,
            "value": fr.filled_value,
            "error": fr.error,
        }
    
    return FillPdfResponse(
        success=True,
        download_id=download_id,
        fields_filled=result.fields_filled,
        fields_failed=result.fields_failed,
        warnings=result.warnings,
        preview=preview,
    )


@router.get("/download/{download_id}")
async def download_filled_pdf(download_id: str):
    """
    Download a filled PDF.
    
    The download_id is returned from the /fill endpoint.
    """
    if download_id not in _filled_pdfs:
        raise HTTPException(
            status_code=404,
            detail="Filled PDF not found or expired. Fill again."
        )
    
    pdf_bytes = _filled_pdfs[download_id]
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=filled_form_{download_id[:8]}.pdf"
        }
    )


@router.delete("/cleanup/{pdf_id}")
async def cleanup_pdf(pdf_id: str):
    """
    Manually cleanup an uploaded PDF.
    
    Use when done with form filling to free resources.
    """
    removed = False
    
    if pdf_id in _pdf_storage:
        del _pdf_storage[pdf_id]
        removed = True
    
    if pdf_id in _pdf_metadata:
        del _pdf_metadata[pdf_id]
        removed = True
    
    return {
        "success": removed,
        "message": "PDF cleaned up" if removed else "PDF not found",
    }


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def pdf_health():
    """Check PDF service health and dependencies."""
    # Check dependencies
    try:
        from services.pdf import parse_pdf, fill_pdf
        pdf_available = True
    except ImportError:
        pdf_available = False
    
    try:
        from services.ai.rag_service import get_rag_service
        rag = get_rag_service()
        rag_stats = rag.get_stats()
    except:
        rag_stats = {"available": False}
    
    return {
        "status": "healthy" if pdf_available else "degraded",
        "pdf_parsing": pdf_available,
        "rag_service": rag_stats,
        "pdfs_in_memory": len(_pdf_storage),
        "filled_pdfs_in_memory": len(_filled_pdfs),
    }
