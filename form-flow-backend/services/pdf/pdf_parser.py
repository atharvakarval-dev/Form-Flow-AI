"""
PDF Parser - Form Field Extraction

Extracts form fields from PDF files with support for:
- AcroForms (standard PDF forms)
- XFA forms (Adobe XML Forms)
- Scanned PDFs via OCR (optional, requires tesseract)

Key Features:
- Field type detection (text, checkbox, radio, dropdown, signature)
- Field constraint extraction (max length, font size, coordinates)
- Text capacity calculation for space-constrained fields
- Label-field relationship detection via proximity analysis
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import io
import re

# PDF Libraries
try:
    import pdfplumber
    from pypdf import PdfReader
    from pypdf.generic import DictionaryObject, ArrayObject
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    pdfplumber = None
    PdfReader = None

# OCR Libraries (optional)
try:
    import pytesseract
    from pdf2image import convert_from_path, convert_from_bytes
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    pytesseract = None
    convert_from_path = None

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

class FieldType(Enum):
    """PDF form field types."""
    TEXT = "text"
    TEXTAREA = "textarea"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    DROPDOWN = "dropdown"
    LISTBOX = "listbox"
    SIGNATURE = "signature"
    DATE = "date"
    NUMBER = "number"
    EMAIL = "email"
    PHONE = "phone"
    BUTTON = "button"
    UNKNOWN = "unknown"


@dataclass
class FieldConstraints:
    """Constraints for a form field."""
    max_length: Optional[int] = None
    min_length: Optional[int] = None
    pattern: Optional[str] = None  # Regex pattern
    required: bool = False
    read_only: bool = False
    multiline: bool = False
    comb: bool = False  # Fixed character spacing
    password: bool = False


@dataclass
class FieldPosition:
    """Position and dimensions of a field on the page."""
    page: int
    x: float
    y: float
    width: float
    height: float
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    def contains_point(self, px: float, py: float) -> bool:
        return (self.x <= px <= self.x + self.width and
                self.y <= py <= self.y + self.height)


@dataclass
class PdfField:
    """Represents a single PDF form field."""
    id: str
    name: str
    field_type: FieldType
    label: str
    position: FieldPosition
    constraints: FieldConstraints
    options: List[str] = field(default_factory=list)  # For dropdown/radio
    default_value: Optional[str] = None
    current_value: Optional[str] = None
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    text_capacity: Optional[int] = None  # Estimated chars that fit
    tab_order: int = 0
    group_name: Optional[str] = None  # For radio button groups
    display_name: Optional[str] = None  # User-friendly label
    purpose: Optional[str] = None  # Semantic purpose (email, phone, etc.)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.field_type.value,
            "label": self.label,
            "display_name": self.display_name or self.label or self.name,
            "page": self.position.page,
            "position": {
                "x": self.position.x,
                "y": self.position.y,
                "width": self.position.width,
                "height": self.position.height,
            },
            "constraints": {
                "max_length": self.constraints.max_length,
                "required": self.constraints.required,
                "multiline": self.constraints.multiline,
                "pattern": self.constraints.pattern,
            },
            "options": self.options,
            "default_value": self.default_value,
            "current_value": self.current_value,
            "font_size": self.font_size,
            "text_capacity": self.text_capacity,
            "purpose": self.purpose,
        }


@dataclass
class PdfFormSchema:
    """Complete schema for a PDF form."""
    file_path: str
    file_name: str
    total_pages: int
    fields: List[PdfField]
    is_xfa: bool = False
    is_scanned: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_fields(self) -> int:
        return len(self.fields)
    
    @property
    def required_fields(self) -> List[PdfField]:
        return [f for f in self.fields if f.constraints.required]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary matching web form schema format."""
        return {
            "source": "pdf",
            "file_path": self.file_path,
            "file_name": self.file_name,
            "total_pages": self.total_pages,
            "total_fields": self.total_fields,
            "is_xfa": self.is_xfa,
            "is_scanned": self.is_scanned,
            "fields": [f.to_dict() for f in self.fields],
            "metadata": self.metadata,
        }


# =============================================================================
# PDF Type Detection
# =============================================================================

def _detect_pdf_type(pdf_path: Union[str, Path, bytes]) -> Tuple[bool, bool]:
    """
    Detect PDF form type.
    
    Returns:
        Tuple of (is_xfa, is_scanned)
    """
    is_xfa = False
    is_scanned = False
    
    try:
        if isinstance(pdf_path, bytes):
            reader = PdfReader(io.BytesIO(pdf_path))
        else:
            reader = PdfReader(str(pdf_path))
        
        # Check for XFA
        if "/AcroForm" in reader.trailer.get("/Root", {}):
            acro_form = reader.trailer["/Root"].get("/AcroForm", {})
            if isinstance(acro_form, DictionaryObject) and "/XFA" in acro_form:
                is_xfa = True
        
        # Check if scanned (no text, just images)
        has_text = False
        for page in reader.pages[:3]:  # Check first 3 pages
            text = page.extract_text() or ""
            if len(text.strip()) > 50:
                has_text = True
                break
        
        # Check for form fields
        has_fields = len(reader.get_fields() or {}) > 0
        
        # If no text and no fields, likely scanned
        is_scanned = not has_text and not has_fields
        
    except Exception as e:
        logger.warning(f"Error detecting PDF type: {e}")
    
    return is_xfa, is_scanned


# =============================================================================
# Field Type Detection
# =============================================================================

def _detect_field_type(field_info: Dict[str, Any], field_name: str) -> FieldType:
    """Detect field type from PDF field dictionary."""
    ft = field_info.get("/FT", "")
    
    if ft == "/Tx":  # Text field
        flags = field_info.get("/Ff", 0)
        if flags & (1 << 12):  # Multiline flag
            return FieldType.TEXTAREA
        if flags & (1 << 13):  # Password flag
            return FieldType.TEXT
        
        # Try to detect semantic type from name/label
        name_lower = field_name.lower()
        if any(x in name_lower for x in ["email", "e-mail"]):
            return FieldType.EMAIL
        if any(x in name_lower for x in ["phone", "tel", "mobile"]):
            return FieldType.PHONE
        if any(x in name_lower for x in ["date", "dob", "birth"]):
            return FieldType.DATE
        if any(x in name_lower for x in ["amount", "price", "total", "number", "age", "zip", "postal"]):
            return FieldType.NUMBER
        
        return FieldType.TEXT
    
    elif ft == "/Btn":  # Button
        flags = field_info.get("/Ff", 0)
        if flags & (1 << 15):  # Radio button
            return FieldType.RADIO
        if flags & (1 << 16):  # Push button
            return FieldType.BUTTON
        return FieldType.CHECKBOX
    
    elif ft == "/Ch":  # Choice field
        flags = field_info.get("/Ff", 0)
        if flags & (1 << 17):  # Combo box (dropdown)
            return FieldType.DROPDOWN
        return FieldType.LISTBOX
    
    elif ft == "/Sig":
        return FieldType.SIGNATURE
    
    return FieldType.UNKNOWN


def _extract_constraints(field_info: Dict[str, Any]) -> FieldConstraints:
    """Extract field constraints from PDF field dictionary."""
    flags = field_info.get("/Ff", 0)
    
    return FieldConstraints(
        max_length=field_info.get("/MaxLen"),
        required=bool(flags & (1 << 1)),  # Required flag
        read_only=bool(flags & (1 << 0)),  # ReadOnly flag
        multiline=bool(flags & (1 << 12)),  # Multiline flag
        comb=bool(flags & (1 << 24)),  # Comb flag
        password=bool(flags & (1 << 13)),  # Password flag
    )


def _extract_options(field_info: Dict[str, Any]) -> List[str]:
    """Extract options from dropdown/listbox fields."""
    options = []
    opt = field_info.get("/Opt", [])
    
    if isinstance(opt, ArrayObject):
        for item in opt:
            if isinstance(item, ArrayObject) and len(item) >= 2:
                options.append(str(item[1]))
            else:
                options.append(str(item))
    
    return options


def _calculate_text_capacity(
    width: float, 
    height: float, 
    font_size: float = 12,
    multiline: bool = False
) -> int:
    """
    Estimate how many characters can fit in a field.
    
    Uses average character width approximation.
    """
    # Average char width is roughly 0.5 * font_size for proportional fonts
    avg_char_width = font_size * 0.5
    chars_per_line = int(width / avg_char_width) if avg_char_width > 0 else 50
    
    if multiline:
        line_height = font_size * 1.2
        num_lines = int(height / line_height) if line_height > 0 else 1
        return chars_per_line * max(1, num_lines)
    
    return max(1, chars_per_line)


def _extract_field_position(field_info: Dict[str, Any], page_num: int) -> FieldPosition:
    """Extract field position from PDF field dictionary."""
    rect = field_info.get("/Rect", [0, 0, 100, 20])
    if isinstance(rect, ArrayObject):
        rect = [float(r) for r in rect]
    
    x1, y1, x2, y2 = rect[:4] if len(rect) >= 4 else [0, 0, 100, 20]
    
    return FieldPosition(
        page=page_num,
        x=min(x1, x2),
        y=min(y1, y2),
        width=abs(x2 - x1),
        height=abs(y2 - y1),
    )


def _find_label_for_field(
    field_pos: FieldPosition, 
    page_text_blocks: List[Dict[str, Any]],
    search_radius: float = 100
) -> str:
    """
    Find label text near a field using proximity analysis.
    
    Looks for text to the left of or above the field.
    """
    best_label = ""
    best_distance = float("inf")
    
    for block in page_text_blocks:
        block_x = block.get("x0", 0)
        block_y = block.get("top", 0)
        block_x2 = block.get("x1", 0)
        block_text = block.get("text", "").strip()
        
        if not block_text or len(block_text) > 100:  # Skip empty or too long
            continue
        
        # Check if text is to the left of field (same row)
        if (block_y >= field_pos.y - 10 and 
            block_y <= field_pos.y + field_pos.height + 10 and
            block_x2 < field_pos.x + 20):
            distance = field_pos.x - block_x2
            if 0 < distance < search_radius and distance < best_distance:
                best_distance = distance
                best_label = block_text
        
        # Check if text is above the field
        elif (block_x >= field_pos.x - 20 and
              block_x <= field_pos.x + field_pos.width + 20 and
              block_y < field_pos.y):
            distance = field_pos.y - block_y
            if 0 < distance < search_radius / 2 and distance < best_distance:
                best_distance = distance
                best_label = block_text
    
    return best_label


def _detect_purpose(field_name: str, label: str) -> Optional[str]:
    """Detect semantic purpose of a field."""
    combined = f"{field_name} {label}".lower()
    
    purpose_patterns = {
        "email": r"e[-_]?mail",
        "phone": r"(phone|tel|mobile|cell)",
        "name": r"(^name$|full.?name|your.?name)",
        "first_name": r"(first.?name|given.?name|fname)",
        "last_name": r"(last.?name|sur.?name|family.?name|lname)",
        "address": r"(address|street|addr)",
        "city": r"(city|town)",
        "state": r"(state|province)",
        "zip": r"(zip|postal|post.?code)",
        "country": r"country",
        "date": r"(date|dob|birth)",
        "ssn": r"(ssn|social.?sec|tax.?id)",
        "gender": r"(gender|sex)",
        "company": r"(company|organization|employer)",
        "title": r"(title|position|job)",
        "website": r"(website|url|web)",
        "signature": r"(signature|sign)",
    }
    
    for purpose, pattern in purpose_patterns.items():
        if re.search(pattern, combined):
            return purpose
    
    return None


# =============================================================================
# Main Parsing Functions
# =============================================================================

def _parse_acroform(pdf_path: Union[str, Path, bytes]) -> List[PdfField]:
    """Parse AcroForm fields from PDF."""
    fields = []
    
    try:
        if isinstance(pdf_path, bytes):
            reader = PdfReader(io.BytesIO(pdf_path))
            plumber_pdf = pdfplumber.open(io.BytesIO(pdf_path))
        else:
            reader = PdfReader(str(pdf_path))
            plumber_pdf = pdfplumber.open(str(pdf_path))
        
        # Get text blocks for label detection
        page_texts = {}
        for i, page in enumerate(plumber_pdf.pages):
            words = page.extract_words() or []
            page_texts[i] = words
        
        # Extract form fields
        pdf_fields = reader.get_fields() or {}
        
        for field_name, field_info in pdf_fields.items():
            if not isinstance(field_info, dict):
                continue
            
            # Determine page
            page_num = 0
            if "/P" in field_info:
                # Try to find page index
                for i, page in enumerate(reader.pages):
                    if page.get_object() == field_info["/P"]:
                        page_num = i
                        break
            
            # Extract field type
            field_type = _detect_field_type(field_info, field_name)
            if field_type == FieldType.BUTTON:
                continue  # Skip push buttons
            
            # Extract position
            position = _extract_field_position(field_info, page_num)
            
            # Extract constraints
            constraints = _extract_constraints(field_info)
            
            # Extract options for choice fields
            options = []
            if field_type in (FieldType.DROPDOWN, FieldType.LISTBOX, FieldType.RADIO):
                options = _extract_options(field_info)
            
            # Find label
            page_blocks = page_texts.get(page_num, [])
            label = _find_label_for_field(position, page_blocks)
            
            # Get tooltip/alternate name as fallback label
            tooltip = field_info.get("/TU", "") or field_info.get("/T", "")
            if not label and tooltip:
                label = str(tooltip)
            
            # Get current value
            current_value = field_info.get("/V")
            if current_value:
                current_value = str(current_value)
            
            # Get default value
            default_value = field_info.get("/DV")
            if default_value:
                default_value = str(default_value)
            
            # Calculate text capacity
            font_size = 12  # Default
            text_capacity = _calculate_text_capacity(
                position.width, 
                position.height, 
                font_size,
                constraints.multiline
            )
            if constraints.max_length:
                text_capacity = min(text_capacity, constraints.max_length)
            
            # Detect purpose
            purpose = _detect_purpose(field_name, label)
            
            # Generate display name
            display_name = label or field_name
            display_name = re.sub(r"[_\-]+", " ", display_name).strip().title()
            
            pdf_field = PdfField(
                id=field_name,
                name=field_name,
                field_type=field_type,
                label=label,
                position=position,
                constraints=constraints,
                options=options,
                default_value=default_value,
                current_value=current_value,
                font_size=font_size,
                text_capacity=text_capacity,
                purpose=purpose,
                display_name=display_name,
            )
            
            fields.append(pdf_field)
        
        plumber_pdf.close()
        
    except Exception as e:
        logger.error(f"Error parsing AcroForm: {e}")
        raise
    
    # Sort by tab order / position
    fields.sort(key=lambda f: (f.position.page, f.position.y, f.position.x))
    
    return fields


def _parse_scanned_pdf(pdf_path: Union[str, Path, bytes]) -> List[PdfField]:
    """
    Parse scanned PDF using OCR to detect form fields.
    
    Uses image processing to identify blank areas that might be form fields.
    """
    if not OCR_AVAILABLE:
        logger.warning("OCR not available. Install pytesseract and pdf2image.")
        return []
    
    fields = []
    
    try:
        # Convert PDF to images
        if isinstance(pdf_path, bytes):
            images = convert_from_bytes(pdf_path)
        else:
            images = convert_from_path(str(pdf_path))
        
        for page_num, image in enumerate(images):
            # Use OCR to get text and bounding boxes
            ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            
            # Find potential labels (text followed by blank space)
            # This is a simplified approach - production would use ML
            for i, text in enumerate(ocr_data["text"]):
                if not text.strip():
                    continue
                
                # Check if this looks like a label (ends with colon, or short text)
                text = text.strip()
                if text.endswith(":") or (len(text) < 30 and not any(c.isdigit() for c in text)):
                    x = ocr_data["left"][i]
                    y = ocr_data["top"][i]
                    w = ocr_data["width"][i]
                    h = ocr_data["height"][i]
                    
                    # Create a field to the right of the label
                    field = PdfField(
                        id=f"ocr_field_{page_num}_{i}",
                        name=f"ocr_field_{page_num}_{i}",
                        field_type=FieldType.TEXT,
                        label=text.rstrip(":"),
                        position=FieldPosition(
                            page=page_num,
                            x=x + w + 10,
                            y=y,
                            width=200,
                            height=h,
                        ),
                        constraints=FieldConstraints(),
                        display_name=text.rstrip(":").title(),
                        purpose=_detect_purpose(text, ""),
                    )
                    fields.append(field)
        
    except Exception as e:
        logger.error(f"Error parsing scanned PDF with OCR: {e}")
    
    return fields


def parse_pdf(
    pdf_source: Union[str, Path, bytes],
    use_ocr: bool = True,
    extract_metadata: bool = True,
) -> PdfFormSchema:
    """
    Parse a PDF file and extract form fields.
    
    Args:
        pdf_source: Path to PDF file or PDF bytes
        use_ocr: Whether to use OCR for scanned PDFs
        extract_metadata: Whether to extract PDF metadata
        
    Returns:
        PdfFormSchema with all extracted fields
    """
    if not PDFPLUMBER_AVAILABLE:
        raise ImportError("pdfplumber and pypdf are required. Install with: pip install pdfplumber pypdf")
    
    # Get file info
    if isinstance(pdf_source, bytes):
        file_path = "uploaded_pdf"
        file_name = "uploaded.pdf"
        pdf_bytes = pdf_source
    else:
        file_path = str(pdf_source)
        file_name = Path(pdf_source).name
        pdf_bytes = None
    
    # Detect PDF type
    is_xfa, is_scanned = _detect_pdf_type(pdf_source)
    
    logger.info(f"Parsing PDF: {file_name} (XFA: {is_xfa}, Scanned: {is_scanned})")
    
    # Get page count
    if pdf_bytes:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    else:
        reader = PdfReader(file_path)
    total_pages = len(reader.pages)
    
    # Extract metadata
    metadata = {}
    if extract_metadata:
        md = reader.metadata or {}
        metadata = {
            "title": md.get("/Title", ""),
            "author": md.get("/Author", ""),
            "creator": md.get("/Creator", ""),
            "producer": md.get("/Producer", ""),
        }
    
    # Parse fields
    fields = []
    
    if is_scanned and use_ocr:
        fields = _parse_scanned_pdf(pdf_source)
    elif is_xfa:
        # XFA parsing would require additional XML handling
        # For now, try AcroForm as fallback
        logger.warning("XFA forms have limited support. Attempting AcroForm extraction.")
        fields = _parse_acroform(pdf_source)
    else:
        fields = _parse_acroform(pdf_source)
    
    return PdfFormSchema(
        file_path=file_path,
        file_name=file_name,
        total_pages=total_pages,
        fields=fields,
        is_xfa=is_xfa,
        is_scanned=is_scanned,
        metadata=metadata,
    )


# =============================================================================
# Utility Functions
# =============================================================================

def get_pdf_summary(schema: PdfFormSchema) -> Dict[str, Any]:
    """Get a summary of the PDF form."""
    field_types = {}
    for field in schema.fields:
        ft = field.field_type.value
        field_types[ft] = field_types.get(ft, 0) + 1
    
    return {
        "file_name": schema.file_name,
        "total_pages": schema.total_pages,
        "total_fields": schema.total_fields,
        "required_fields": len(schema.required_fields),
        "field_types": field_types,
        "is_xfa": schema.is_xfa,
        "is_scanned": schema.is_scanned,
    }


def get_fillable_fields(schema: PdfFormSchema) -> List[Dict[str, Any]]:
    """
    Get list of fillable fields in format compatible with conversation agent.
    
    This matches the web form field format for unified processing.
    """
    return [
        {
            "name": f.name,
            "id": f.id,
            "type": f.field_type.value,
            "label": f.display_name or f.label or f.name,
            "required": f.constraints.required,
            "options": f.options,
            "max_length": f.constraints.max_length,
            "text_capacity": f.text_capacity,
            "purpose": f.purpose,
            "page": f.position.page,
        }
        for f in schema.fields
        if f.field_type not in (FieldType.BUTTON, FieldType.SIGNATURE)
    ]
