"""
Word Document Filler service.
"""
import io
import re
from typing import Dict, Any, Tuple
from docx import Document

from utils.logging import get_logger

logger = get_logger(__name__)

def fill_docx_template(content: bytes, data: Dict[str, str]) -> Tuple[bytes, int]:
    """
    Fill a Word document template with data.
    
    Args:
        content: Raw bytes of the docx file
        data: Dictionary of field_name -> value
        
    Returns:
        Tuple of (filled_content_bytes, count_of_filled_fields)
    """
    try:
        doc = Document(io.BytesIO(content))
        filled_count = 0
        
        # Replace placeholders in paragraphs
        for paragraph in doc.paragraphs:
            for field_name, value in data.items():
                # Replace bracket placeholders: [Name] or [name]
                pattern = re.compile(rf'\[{re.escape(field_name)}\]', re.IGNORECASE)
                if pattern.search(paragraph.text):
                    for run in paragraph.runs:
                        if pattern.search(run.text):
                            run.text = pattern.sub(value, run.text)
                            filled_count += 1
                        
                # Also try display name variations (underscores as spaces)
                display_name = field_name.replace("_", " ")
                display_pattern = re.compile(rf'\[{re.escape(display_name)}\]', re.IGNORECASE)
                if display_pattern.search(paragraph.text):
                    for run in paragraph.runs:
                        if display_pattern.search(run.text):
                            run.text = display_pattern.sub(value, run.text)
                            filled_count += 1
        
        # Save filled document
        output = io.BytesIO()
        doc.save(output)
        output.seek(0)
        
        return output.getvalue(), filled_count
        
    except Exception as e:
        logger.error(f"Error filling document in service: {e}", exc_info=True)
        raise e
