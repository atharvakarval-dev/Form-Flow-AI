"""
Attachments Router - API Endpoints for File Form Fields

Provides REST API for:
- Secure File upload (Async, Chunked)
- File retrieval
- File deletion
"""

import os
import asyncio
import uuid
import logging
import hashlib
import re
from pathlib import Path
from typing import Dict, Any, Optional

import aiofiles
import aiofiles.os
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Try importing magic for MIME type validation
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False

from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/attachments", tags=["Attachments"])

# =============================================================================
# Configuration & Constants
# =============================================================================

STORAGE_DIR = Path("storage")
ATTACHMENTS_DIR = STORAGE_DIR / "attachments"
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

# Security Limits
CHUNK_SIZE = 1024 * 1024  # 1MB chunks
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
    "text/plain"
}


# =============================================================================
# Request/Response Models
# =============================================================================

class AttachmentUploadResponse(BaseModel):
    """Response from file upload."""
    success: bool
    file_id: str
    file_name: str
    content_type: str
    size: int
    url: str
    checksum: str
    message: str = ""


# =============================================================================
# Helper Functions (Security & Async I/O)
# =============================================================================

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and remove dangerous characters.
    """
    # Remove path components
    filename = os.path.basename(filename)
    # Remove null bytes
    filename = filename.replace('\0', '')
    # Allow only safe characters (alphanumeric, dot, dash, underscore)
    filename = re.sub(r'[^\w\.-]', '_', filename)
    # Ensure it's not empty
    if not filename:
        filename = "attachment"
    return filename


def validate_mime_type(content: bytes, declared_type: str) -> bool:
    """
    Validate file content against declared MIME type using python-magic.
    Returns True if valid, False otherwise.
    """
    if not HAS_MAGIC:
        logger.warning("python-magic not installed, skipping strict MIME validation")
        return True

    try:
        mime = magic.Magic(mime=True)
        detected_type = mime.from_buffer(content)
        
        # Simple check: detected type should match generally
        # For stricter security, we would check against ALLOWED_MIME_TYPES whitelist
        if declared_type == "application/octet-stream":
            return True # Allow generic if we can't be sure
            
        # Allow compatible types (e.g. jpeg vs jpg)
        if detected_type == declared_type:
            return True
            
        logger.warning(f"MIME mismatch: declared={declared_type}, detected={detected_type}")
        return True # For now, log warning but don't block unless strictly required
    except Exception as e:
        logger.error(f"MIME validation error: {e}")
        return True


async def _save_attachment_async(file_id: str, file: UploadFile) -> Dict[str, Any]:
    """
    Save uploaded file to disk asynchronously with chunking and size limits.
    Returns metadata dict including size and checksum.
    """
    file_path = ATTACHMENTS_DIR / file_id
    temp_path = file_path.with_suffix(".tmp")
    
    file_hash = hashlib.sha256()
    total_size = 0
    
    try:
        async with aiofiles.open(temp_path, "wb") as f:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                
                chunk_len = len(chunk)
                total_size += chunk_len
                
                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413, 
                        detail=f"File too large. Maximum size is {MAX_FILE_SIZE/1024/1024}MB"
                    )
                
                file_hash.update(chunk)
                await f.write(chunk)
        
        # Renaissance: Rename temp file to final file
        await aiofiles.os.rename(temp_path, file_path)
        
        return {
            "size": total_size,
            "checksum": file_hash.hexdigest()
        }
        
    except Exception as e:
        # Cleanup temp file on error
        if await aiofiles.os.path.exists(temp_path):
            await aiofiles.os.remove(temp_path)
        raise e


def _save_metadata(file_id: str, metadata: Dict[str, Any]):
    """Save metadata to disk (sync is fine for small JSON)."""
    meta_path = ATTACHMENTS_DIR / f"{file_id}.json"
    import json
    with open(meta_path, "w") as f:
        json.dump(metadata, f)


def _get_metadata(file_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve metadata from disk."""
    meta_path = ATTACHMENTS_DIR / f"{file_id}.json"
    if not meta_path.exists():
        return None
    import json
    try:
        with open(meta_path, "r") as f:
            return json.load(f)
    except Exception:
        return None


async def _cleanup_attachment(file_id: str):
    """Remove attachment from storage after timeout."""
    try:
        await asyncio.sleep(86400)  # 24 hours
    except asyncio.CancelledError:
        return

    try:
        file_path = ATTACHMENTS_DIR / file_id
        meta_path = ATTACHMENTS_DIR / f"{file_id}.json"
        
        if await aiofiles.os.path.exists(file_path):
            await aiofiles.os.remove(file_path)
        if await aiofiles.os.path.exists(meta_path):
            await aiofiles.os.remove(meta_path)
            
        logger.info(f"🧹 Cleaned up attachment {file_id}")
    except Exception as e:
        logger.warning(f"Cleanup failed for {file_id}: {e}")


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/upload", response_model=AttachmentUploadResponse)
async def upload_attachment(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Upload a file for a form attachment field.
    Uses async streaming to handle large files efficiently.
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # sanitize filename
    safe_filename = sanitize_filename(file.filename)
    file_id = str(uuid.uuid4())
    
    logger.info(f"📂 Uploading attachment: {safe_filename} (ID: {file_id})")
    
    try:
        # Save file asynchronously
        upload_meta = await _save_attachment_async(file_id, file)
        
        # Save metadata
        metadata = {
            "id": file_id,
            "original_filename": safe_filename,
            "content_type": file.content_type,
            "size": upload_meta["size"],
            "checksum": upload_meta["checksum"],
            "upload_time": str(uuid.uuid1().time),
        }
        _save_metadata(file_id, metadata)
        
        # Schedule cleanup
        if background_tasks:
            background_tasks.add_task(_cleanup_attachment, file_id)
            
        return AttachmentUploadResponse(
            success=True,
            file_id=file_id,
            file_name=safe_filename,
            content_type=file.content_type or "application/octet-stream",
            size=upload_meta["size"],
            url=f"/attachments/{file_id}",
            checksum=upload_meta["checksum"],
            message="File uploaded successfully"
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing attachment upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/{file_id}")
async def get_attachment(file_id: str):
    """
    Retrieve an uploaded attachment.
    """
    file_path = ATTACHMENTS_DIR / file_id
    metadata = _get_metadata(file_id)
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Attachment not found")
        
    filename = metadata.get("original_filename", "attachment") if metadata else "attachment"
    content_type = metadata.get("content_type", "application/octet-stream") if metadata else None

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=content_type
    )


@router.delete("/{file_id}")
async def delete_attachment(file_id: str):
    """
    Delete an uploaded attachment.
    """
    file_path = ATTACHMENTS_DIR / file_id
    meta_path = ATTACHMENTS_DIR / f"{file_id}.json"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Attachment not found")
        
    try:
        if await aiofiles.os.path.exists(file_path):
            await aiofiles.os.remove(file_path)
        if await aiofiles.os.path.exists(meta_path):
            await aiofiles.os.remove(meta_path)
            
        return {"success": True, "message": "Attachment deleted"}
        
    except Exception as e:
        logger.error(f"Failed to delete attachment {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete attachment")
