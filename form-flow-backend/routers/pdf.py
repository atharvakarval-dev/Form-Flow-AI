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
import asyncio
import tempfile
import os
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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
# Persistent Disk Storage
# =============================================================================

STORAGE_DIR = Path("storage")
UPLOAD_DIR = STORAGE_DIR / "uploads"
FILLED_DIR = STORAGE_DIR / "filled"

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FILLED_DIR.mkdir(parents=True, exist_ok=True)

def _save_upload(pdf_id: str, content: bytes, metadata: Dict[str, Any]):
    """Save uploaded PDF and metadata to disk."""
    logger.info(f"💾 SAVING upload {pdf_id} to {UPLOAD_DIR}")
    # Save PDF
    pdf_path = UPLOAD_DIR / f"{pdf_id}.pdf"
    pdf_path.write_bytes(content)
    
    # Save Metadata
    meta_path = UPLOAD_DIR / f"{pdf_id}.json"
    import json
    with open(meta_path, "w") as f:
        json.dump(metadata, f)

def _get_upload(pdf_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
    """Retrieve uploaded PDF and metadata from disk."""
    logger.info(f"🔍 SEARCHING for upload {pdf_id} in {UPLOAD_DIR}")
    pdf_path = UPLOAD_DIR / f"{pdf_id}.pdf"
    meta_path = UPLOAD_DIR / f"{pdf_id}.json"
    
    if not pdf_path.exists() or not meta_path.exists():
        logger.warning(f"❌ Upload {pdf_id} NOT FOUND at {pdf_path}")
        return None
        
    content = pdf_path.read_bytes()
    import json
    with open(meta_path, "r") as f:
        metadata = json.load(f)
        
    return content, metadata

def _save_filled(download_id: str, content: bytes):
    """Save filled PDF to disk."""
    path = FILLED_DIR / f"{download_id}.pdf"
    path.write_bytes(content)

def _get_filled(download_id: str) -> Optional[bytes]:
    """Retrieve filled PDF from disk."""
    path = FILLED_DIR / f"{download_id}.pdf"
    if not path.exists():
        return None
    return path.read_bytes()

async def _cleanup_pdf(pdf_id: str):
    """Remove PDF from storage after timeout."""
    await asyncio.sleep(3600)  # 1 hour delay
    try:
        logger.info(f"🧹 Cleaning up upload {pdf_id}")
        (UPLOAD_DIR / f"{pdf_id}.pdf").unlink(missing_ok=True)
        (UPLOAD_DIR / f"{pdf_id}.json").unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Cleanup failed for {pdf_id}: {e}")


async def _cleanup_filled(download_id: str):
    """Remove filled PDF after timeout."""
    await asyncio.sleep(1800)  # 30 mins delay
    try:
        logger.info(f"🧹 Cleaning up download {download_id}")
        (FILLED_DIR / f"{download_id}.pdf").unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Cleanup filled failed for {download_id}: {e}")


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
        logger.info(f"Read PDF file: {file.filename}, size: {len(content)} bytes")
    except Exception as e:
        logger.error(f"Error reading uploaded file: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Error reading file: {str(e)}"
        )
    
    # Parse PDF
    try:
        logger.info(f"Parsing PDF: {file.filename}")
        loop = asyncio.get_event_loop()
        schema = await loop.run_in_executor(None, lambda: parse_pdf(content, use_ocr=False))
        logger.info(f"Parsed {schema.total_fields} fields from {file.filename}")
    except ImportError as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(
            status_code=500,
            detail="PDF parsing libraries not installed. Run: pip install pdfplumber pypdf"
        )
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=400,
            detail=f"Error parsing PDF: {str(e)}"
        )
    
    # Generate ID and store
    pdf_id = str(uuid.uuid4())
    
    try:
        schema_dict = schema.to_dict()
        _save_upload(pdf_id, content, {
            "file_name": file.filename,
            "schema": schema_dict,
        })
    except Exception as e:
        logger.error(f"Error converting schema to dict: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF schema: {str(e)}"
        )
    
    # Schedule cleanup after 1 hour
    if background_tasks:
        background_tasks.add_task(_cleanup_pdf, pdf_id)
    
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
    upload_data = _get_upload(pdf_id)
    if not upload_data:
        raise HTTPException(
            status_code=404,
            detail="PDF not found. Upload again."
        )
    
    _, metadata = upload_data
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
    upload_data = _get_upload(request.pdf_id)
    if not upload_data:
        raise HTTPException(
            status_code=404,
            detail="PDF not found. Upload again."
        )
    
    pdf_bytes, metadata = upload_data
    fields_dict = {f["name"]: f for f in metadata["schema"]["fields"]}
    
    fitter = TextFitter()
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
    upload_data = _get_upload(request.pdf_id)
    if not upload_data:
        raise HTTPException(
            status_code=404,
            detail="PDF not found. Upload again."
        )
    
    pdf_bytes, _ = upload_data
    
    try:
        result = fill_pdf(
            template_path=pdf_bytes,
            data=request.data,
            flatten=request.flatten,
        )
    except Exception as e:
        logger.error(f"Error filling PDF: {e}")
        logger.error(traceback.format_exc())
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
    _save_filled(download_id, result.output_bytes)
    
    # Cleanup after 30 minutes
    background_tasks.add_task(_cleanup_filled, download_id)
    
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


@router.get("/debug/files")
async def debug_pdf_storage():
    """Debug endpoint to check stored files."""
    try:
        uploads = [f.name for f in UPLOAD_DIR.glob("*") if f.is_file()]
        filled = [f.name for f in FILLED_DIR.glob("*") if f.is_file()]
        
        return {
            "status": "ok",
            "cwd": str(Path.cwd()),
            "storage_dir": str(STORAGE_DIR.absolute()),
            "uploads_count": len(uploads),
            "uploads": uploads,
            "filled_count": len(filled),
            "filled": filled,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/download/{download_id}")
async def download_filled_pdf(download_id: str):
    """
    Download a filled PDF.
    
    The download_id is returned from the /fill endpoint.
    """
    pdf_bytes = _get_filled(download_id)
    if not pdf_bytes:
        raise HTTPException(
            status_code=404,
            detail="Filled PDF not found or expired. Fill again."
        )
    
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
    
    # Clean up disk files
    try:
        (UPLOAD_DIR / f"{pdf_id}.pdf").unlink(missing_ok=True)
        (UPLOAD_DIR / f"{pdf_id}.json").unlink(missing_ok=True)
        removed = True
    except Exception as e:
        logger.warning(f"Manual cleanup failed for {pdf_id}: {e}")
    
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
        "uploads_on_disk": len(list(UPLOAD_DIR.glob("*.pdf"))),
        "filled_on_disk": len(list(FILLED_DIR.glob("*.pdf"))),
    }
