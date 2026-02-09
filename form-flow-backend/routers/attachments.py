"""
Attachments Router - API Endpoints for File Form Fields

Provides REST API for:
- File upload
- File retrieval
- File deletion
"""

import os
import asyncio
import shutil
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/attachments", tags=["Attachments"])

# =============================================================================
# Persistent Disk Storage
# =============================================================================

STORAGE_DIR = Path("storage")
ATTACHMENTS_DIR = STORAGE_DIR / "attachments"

# Ensure directories exist
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)


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
    message: str = ""


# =============================================================================
# Helper Functions
# =============================================================================

def _get_file_path(file_id: str) -> Path:
    """Get the file path for a given file ID."""
    # We search for any file starting with file_id to handle extensions
    # But for simplicity, we will save files with their original extension appended to ID or keep a metadata map.
    # A simpler approach: save as `{file_id}_{filename}` to preserve extension and name.
    # However, to easily lookup by ID, we might just use ID and a sidecar metadata file, 
    # OR scan the directory (slower).
    #
    # Improved approach: Save as `file_id` (content) and `file_id.json` (metadata).
    return ATTACHMENTS_DIR / file_id


def _save_attachment(file_id: str, file: UploadFile) -> Path:
    """Save uploaded file to disk."""
    file_path = ATTACHMENTS_DIR / file_id
    
    # Save content
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to write file {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save file to storage")
        
    return file_path


def _save_metadata(file_id: str, metadata: Dict[str, Any]):
    """Save metadata to disk."""
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
    except Exception as e:
        logger.error(f"Failed to read metadata for {file_id}: {e}")
        return None


async def _cleanup_attachment(file_id: str):
    """Remove attachment from storage after timeout (e.g. 24 hours)."""
    try:
        await asyncio.sleep(86400)  # 24 hours
    except asyncio.CancelledError:
        return

    try:
        logger.info(f"🧹 Cleaning up attachment {file_id}")
        file_path = ATTACHMENTS_DIR / file_id
        meta_path = ATTACHMENTS_DIR / f"{file_id}.json"
        
        file_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
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
    
    Returns file ID and URL for retrieval.
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    file_id = str(uuid.uuid4())
    logger.info(f"📂 Uploading attachment: {file.filename} (ID: {file_id})")
    
    try:
        # Save file to disk
        file_path = _save_attachment(file_id, file)
        file_size = file_path.stat().st_size
        
        # Save metadata
        metadata = {
            "id": file_id,
            "original_filename": file.filename,
            "content_type": file.content_type,
            "size": file_size,
            "upload_time": str(uuid.uuid1().time), # simple timestamp proxy
        }
        _save_metadata(file_id, metadata)
        
        # Schedule cleanup
        if background_tasks:
            background_tasks.add_task(_cleanup_attachment, file_id)
            
        return AttachmentUploadResponse(
            success=True,
            file_id=file_id,
            file_name=file.filename,
            content_type=file.content_type or "application/octet-stream",
            size=file_size,
            url=f"/attachments/{file_id}",
            message="File uploaded successfully"
        )
        
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
        file_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        return {"success": True, "message": "Attachment deleted"}
    except Exception as e:
        logger.error(f"Failed to delete attachment {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete attachment")
