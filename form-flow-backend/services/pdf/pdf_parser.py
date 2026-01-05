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

# Enterprise Infrastructure
from .exceptions import PdfParsingError, PdfResourceError
from .utils import get_logger, benchmark, PerformanceTimer
from .domain import FieldContext, FieldGroup, GroupType, ValidationReport
from .xfa_parser import parse_xfa_fields, XfaField

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

logger = get_logger(__name__)


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
    context: Optional[FieldContext] = None  # Rich context from surroundings
    section: Optional[str] = None  # Form section (e.g., "Income", "Filing Status")
    form_line: Optional[str] = None  # Form line number (e.g., "1a", "2b")
    
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
            "section": self.section,
            "form_line": self.form_line,
        }


@dataclass
class PdfFormSchema:
    """Complete schema for a PDF form."""
    file_path: str
    file_name: str
    total_pages: int
    fields: List[PdfField]
    groups: List[FieldGroup] = field(default_factory=list)
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
            "groups": [g.to_dict() for g in self.groups],  # Use to_dict for proper enum serialization
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
        
        # Check for XFA - need to handle pypdf object types
        try:
            root = reader.trailer.get("/Root")
            if root is not None:
                # Resolve indirect object if needed
                if hasattr(root, 'get_object'):
                    root = root.get_object()
                if isinstance(root, dict) and "/AcroForm" in root:
                    acro_form = root.get("/AcroForm")
                    if hasattr(acro_form, 'get_object'):
                        acro_form = acro_form.get_object()
                    if isinstance(acro_form, dict) and "/XFA" in acro_form:
                        is_xfa = True
        except Exception as e:
            logger.debug(f"XFA detection skipped: {e}")
        
        # Check if scanned (no text, just images)
        has_text = False
        for page in reader.pages[:3]:  # Check first 3 pages
            text = page.extract_text() or ""
            if len(text.strip()) > 50:
                has_text = True
                break
        
        # Check for form fields
        try:
            fields = reader.get_fields()
            has_fields = len(fields) > 0 if fields else False
        except Exception:
            has_fields = False
        
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


def _detect_field_type_enhanced(
    field_info: Dict[str, Any], 
    field_name: str, 
    context: Optional[FieldContext] = None
) -> FieldType:
    """
    Enhanced field type detection using PDF metadata and context.
    
    Args:
        field_info: Raw dictionary from PDF
        field_name: Internal field name
        context: Rich context (nearby text, label, etc.)
        
    Returns:
        Detected FieldType
    """
    # 1. Start with technical type from PDF structure
    base_type = _detect_field_type(field_info, field_name)
    
    if base_type != FieldType.TEXT and base_type != FieldType.UNKNOWN:
        return base_type
        
    # 2. Use context to refine TEXT fields into semantic types
    text_to_analyze = [field_name]
    if context:
        if context.nearby_text: text_to_analyze.append(context.nearby_text)
        if context.instructions: text_to_analyze.append(context.instructions)
        # Also check label if explicitly extracted beforehand (though often in nearby_text)
        
    combined_text = " ".join(text_to_analyze).lower()
    
    # 3. Pattern Matching
    if any(x in combined_text for x in ["date", "dob", "birth", "mm/dd", "dd/mm", "xxxx-xx-xx"]):
        return FieldType.DATE
        
    if any(x in combined_text for x in ["email", "e-mail"]):
        return FieldType.EMAIL
        
    if any(x in combined_text for x in ["phone", "cell", "mobile", "tel", "fax", "contact no"]):
        return FieldType.PHONE
        
    if any(x in combined_text for x in ["ssn", "social security", "tax id", "ein"]):
        return FieldType.TEXT  # Keep as TEXT but maybe flag as sensitive? Or regex pattern later.
        
    if any(x in combined_text for x in ["zip", "postal code", "pincode"]):
        return FieldType.TEXT # Specialized text
        
    if any(x in combined_text for x in ["amount", "price", "total", "cost", "fee", "$", "€", "£"]):
        return FieldType.NUMBER
        
    if any(x in combined_text for x in ["signature", "sign here", "signed"]):
        return FieldType.SIGNATURE
        
    return base_type


def _extract_validation_rules(
    field_info: Dict[str, Any], 
    context: Optional[FieldContext] = None
) -> FieldConstraints:
    """
    Extract validation rules from PDF constraints and context instructions.
    """
    # Base constraints from PDF flags (MaxLen, Required, etc.)
    constraints = _extract_constraints(field_info)
    
    if not context:
        return constraints
        
    combined_text = (context.instructions + " " + context.nearby_text).lower()
    
    # 1. Detect Required (visual cues like *)
    if "*" in combined_text or "required" in combined_text or context.is_required_visually:
        constraints.required = True
        
    # 2. Detect Date Format
    if "mm/dd/yyyy" in combined_text:
        constraints.pattern = r"^\d{2}/\d{2}/\d{4}$"
    elif "dd/mm/yyyy" in combined_text:
        constraints.pattern = r"^\d{2}/\d{2}/\d{4}$"
    elif "yyyy-mm-dd" in combined_text:
        constraints.pattern = r"^\d{4}-\d{2}-\d{2}$"
        
    # 3. Detect Phone Format
    if "phone" in combined_text or "tel" in combined_text:
        # Generic loose phone match
        if not constraints.pattern:
            constraints.pattern = r"^[\d\+\-\(\)\s\.]+$"
            
    # 4. Detect Email
    if "email" in combined_text:
        constraints.pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        
    return constraints


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



def _clean_label(label: str) -> str:
    """
    Clean up field labels by removing noise and technical artifacts.
    """
    if not label:
        return ""
        
    # 1. Remove common instructional noise
    noise_patterns = [
        r'see instructions.*',
        r'if required.*',
        r'attach schedule.*',
        r'go to www.*',
        r'don\'t write in.*',
        r'for office use.*',
        r'paperwork reduction.*',
        r'privacy act.*',
        r'ommision of.*',
        r'\(optional\)', 
        r'\(if any\)',
    ]
    
    cleaned = label
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
    # 2. Remove internal ID patterns if they leaked into the label
    # E.g. "topmostSubform[0]..."
    if re.match(r'^topmostSubform\[\d+\].*', cleaned):
        return ""
        
    # 3. Cleanup whitespace and punctuation
    cleaned = cleaned.strip()
    cleaned = cleaned.rstrip('.:,;-')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()


def _is_technical_id(label: str) -> bool:
    """
    Check if a label looks like a technical ID/variable name rather than human text.
    """
    if not label: 
        return False
        
    # Patterns that look like code/IDs
    # e.g. "c1_1[0]", "f1_01", "Group1", "TextField1"
    technical_patterns = [
        r'^[a-z][0-9]+_[0-9]+(\[\d+\])?$',  # c1_1[0]
        r'^[a-z]+[0-9]+(\[\d+\])?$',        # f1[0]
        r'^topmostSubform.*',               # XFA paths
        r'^Group\d+$',
        r'^TextField\d+$',
        r'^CheckBox\d+$',
        r'^[Ff]\d+\s\d+(\[\d+\])?$',        # F1 01[0] or f1 01
        r'^[A-Za-z]+\d+(\[\d+\])?$',        # Generic Alphanumeric + Number
    ]
    
    for pattern in technical_patterns:
        if re.match(pattern, label, re.IGNORECASE):
            return True
            
    return False


def _find_label_for_field(
    field_pos: FieldPosition, 
    page_text_blocks: List[Dict[str, Any]],
    field_type: FieldType = FieldType.TEXT,
    search_radius: float = 100
) -> str:
    """
    Find label text near a field using proximity analysis.
    
    Strategies vary by field type:
    - Checkboxes/Radios: Look Right (primary), then Left/Top.
    - Text: Look Left (primary), then Top.
    """
    best_label = ""
    best_distance = float("inf")
    
    # Define search zones based on field type
    # (x_offset, y_offset, search_dist_factor)
    # distance logic: we want minimal distance
    
    for block in page_text_blocks:
        block_x = block.get("x0", 0)
        block_y = block.get("top", 0)
        block_x2 = block.get("x1", 0)
        block_text = block.get("text", "").strip()
        
        if not block_text or len(block_text) > 100:
            continue
            
        # 1. RIGHT SIDE SEARCH (Best for Checkboxes)
        # Check if text is to the right of field
        if field_type in (FieldType.CHECKBOX, FieldType.RADIO):
            # Relaxed Y-tolerance (often text baseline is offset from box)
            if (block_y >= field_pos.y - 12 and 
                block_y <= field_pos.y + field_pos.height + 12 and
                block_x >= field_pos.x + field_pos.width - 5): # Allow 5px overlap
                
                distance = block_x - (field_pos.x + field_pos.width)
                if 0 < distance < 150 and distance < best_distance: # Increased range to 150
                    best_distance = distance
                    best_label = block_text
                    continue # Found a good right-side candidate, keep looking for closer one
        
        # 2. LEFT SIDE SEARCH (Good for Text inputs)
        if (block_y >= field_pos.y - 10 and 
            block_y <= field_pos.y + field_pos.height + 10 and
            block_x2 <= field_pos.x):
            
            distance = field_pos.x - block_x2
            # Penalize Left side for checkboxes slightly to prefer Right side if distances are similar
            penalty = 20 if field_type in (FieldType.CHECKBOX, FieldType.RADIO) else 0
            
            if 0 < distance < search_radius and (distance + penalty) < best_distance:
                best_distance = distance + penalty
                best_label = block_text
        
        # 3. TOP SEARCH (Fallback for Text inputs)
        elif (block_x >= field_pos.x - 20 and
              block_x <= field_pos.x + field_pos.width + 20 and
              block_y < field_pos.y):
            
            distance = field_pos.y - block_y
            # Big penalty for checkboxes (usually not labeled from above)
            penalty = 50 if field_type in (FieldType.CHECKBOX, FieldType.RADIO) else 0

            if 0 < distance < (search_radius / 2) and (distance + penalty) < best_distance:
                best_distance = distance + penalty
                best_label = block_text
    
    return best_label


def _detect_purpose(field_name: str, label: str) -> Optional[str]:
    """Detect semantic purpose of a field."""
    combined = f"{field_name} {label}".lower()
    
    purpose_patterns = {
        "email": r"e[-_]?mail",
        # Improved phone pattern to catch "Contact Number" but avoid "Emergency Contact Name"
        "phone": r"(phone|tel|mobile|cell|contact\s*(number|no\.?|#)|primary\s*contact|alternate\s*contact)",
        "name": r"(^name$|full.?name|your.?name|applicant.?name|contact.?name)",
        "first_name": r"(first.?name|given.?name|fname)",
        "last_name": r"(last.?name|sur.?name|family.?name|lname)",
        "address": r"(address|street|addr|residence)",
        "city": r"(city|town)",
        "state": r"(state|province)",
        "zip": r"(zip|postal|post.?code|pincode)",
        "country": r"country",
        "date": r"(date|dob|birth|year|day|month)",
        "ssn": r"(ssn|social.?sec|tax.?id|pan\s*card|aadhaar)", # Added Indian context (PAN/Aadhaar) generically
        "gender": r"(gender|sex|male|female)",
        "company": r"(company|organization|employer|business)",
        "title": r"(title|position|job|designation)",
        "website": r"(website|url|web)",
        "signature": r"(signature|sign)",
        "amount": r"(amount|fee|cost|price|total|salary|stipend)",
    }
    
    for purpose, pattern in purpose_patterns.items():
        if re.search(pattern, combined):
            return purpose
    
    return None

# =============================================================================
# Field Grouping Logic
# =============================================================================

def _group_fields(fields: List[PdfField]) -> List[FieldGroup]:
    """
    Analyze fields and organize them into logical groups.
    
    Strategies:
    1. Radio Button Groups (Same Name)
    2. Address Blocks (Semantic Proximity)
    3. Repeating Sections (Name patterns)
    """
    groups = []
    
    # 1. Radio Groups
    radio_map: Dict[str, List[PdfField]] = {}
    for f in fields:
        if f.field_type == FieldType.RADIO:
            if f.name not in radio_map:
                radio_map[f.name] = []
            radio_map[f.name].append(f)
            
    for name, radio_fields in radio_map.items():
        if len(radio_fields) > 1:
            group = FieldGroup(
                id=f"group_radio_{name}",
                group_type=GroupType.LOGICAL,
                fields=[f.id for f in radio_fields],
                label=radio_fields[0].label or name,
            )
            groups.append(group)
            
    # 2. Address Grouping
    # Find clusters of address-related fields
    address_fields = [f for f in fields if f.purpose in ("address", "city", "state", "zip", "country")]
    # Simple strategy: if we perceive address fields on the same page within reasonable Y distance
    
    # TODO: Advanced spatial clustering for addresses
    # For now, if we have explicit address fields, group them
    if address_fields:
        # Check if they look like they belong to the same entity (e.g. valid single address block)
        # Verify mostly unique types (1 city, 1 state, etc.) or clear separation
        has_addr = any(f.purpose == "address" for f in address_fields)
        has_zip = any(f.purpose == "zip" for f in address_fields)
        
        if has_addr and has_zip:
             # Create a naive single address group for now
             # Improvement: Detect multiple address blocks
            groups.append(FieldGroup(
                id="group_address_primary",
                group_type=GroupType.ADDRESS,
                fields=[f.id for f in address_fields],
                label="Primary Address"
            ))
            
    return groups

# =============================================================================
# Main Parsing Functions
# =============================================================================

def _is_xfa_container(field_name: str, field_info: Dict[str, Any]) -> bool:
    """
    Check if a field is an XFA structural container (not a fillable field).
    
    XFA containers are parent nodes like 'topmostSubform[0]', 'Page1[0]', 'Table_Dependents[0]'
    that should not be shown to users.
    """
    # No field type = likely a container
    field_type = field_info.get("/FT")
    if field_type is None:
        return True
    
    # Pattern for container names: parent[index] without a field-like suffix (f1_, c1_, etc)
    container_patterns = [
        r'^topmostSubform\[\d+\]$',  # Root container
        r'^topmostSubform\[\d+\]\.Page\d+\[\d+\]$',  # Page containers
        r'_ReadOrder\[\d+\]$',  # Read order containers
        r'^.*Row\d+\[\d+\]$',  # Table row containers
        r'^.*Table_.*\[\d+\]$',  # Table containers
        r'^.*Dependent\d+\[\d+\]$',  # Dependent containers (if no field type)
    ]
    
    for pattern in container_patterns:
        if re.match(pattern, field_name):
            return True
    
    return False


def _extract_form_line(field_name: str, label: str) -> Optional[str]:
    """
    Extract form line number (e.g., '1a', '2b') from field name or label.
    
    IRS forms use patterns like 'Line 1a', 'f1_01' (field 01 on page 1).
    """
    # Try to extract from label first: "Line 1a", "1a.", etc.
    line_match = re.search(r'[Ll]ine\s*(\d+[a-z]?)|^(\d+[a-z]?)[\.\s]', label)
    if line_match:
        return line_match.group(1) or line_match.group(2)
    
    # Try field name patterns: f1_01, f2_15 -> "1", "15"
    # Format: f{page}_{field_number}
    field_match = re.search(r'f(\d)_(\d{2})\[\d+\]$', field_name)
    if field_match:
        page = field_match.group(1)
        num = field_match.group(2).lstrip('0') or '0'
        return f"{num}" if page == '1' else f"{page}-{num}"
    
    return None


def _detect_section(field_name: str, label: str, page_texts: List[Dict]) -> Optional[str]:
    """
    Detect which section a field belongs to based on nearby text.
    
    Common sections: Personal Information, Filing Status, Income, Deductions, etc.
    """
    combined = f"{field_name} {label}".lower()
    
    section_keywords = {
        "Personal Information": ["first name", "last name", "ssn", "social security", "address", "city", "state", "zip"],
        "Filing Status": ["filing status", "single", "married", "head of household", "qualifying", "spouse"],
        "Dependents": ["dependent", "child", "relationship"],
        "Income": ["income", "w-2", "wages", "interest", "dividend", "ira", "pension", "social security benefits", "capital gain"],
        "Adjustments": ["adjustment", "deduction", "ira contribution", "student loan"],
        "Tax and Credits": ["tax", "credit", "child tax", "earned income"],
        "Payments": ["payment", "withheld", "estimated tax"],
        "Refund": ["refund", "overpaid", "routing", "account number"],
        "Amount You Owe": ["amount you owe", "penalty"],
        "Signature": ["signature", "sign here", "occupation", "preparer"],
    }
    
    for section, keywords in section_keywords.items():
        for kw in keywords:
            if kw in combined:
                return section
    
    return None


@benchmark("parse_acroform")
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
        
        # GENERIC XFA LABEL EXTRACTION
        # Parse XFA template to get labels directly from PDF (no hardcoded mappings!)
        xfa_labels = {}
        try:
            xfa_fields = parse_xfa_fields(pdf_path)
            for xf in xfa_fields:
                if xf.label:
                    xfa_labels[xf.name] = xf
            logger.info(f"XFA parser extracted {len(xfa_labels)} field labels")
        except Exception as e:
            logger.debug(f"XFA parsing skipped: {e}")
        
        # Get text blocks for label detection (fallback for non-XFA)
        page_texts = {}
        for i, page in enumerate(plumber_pdf.pages):
            words = page.extract_words() or []
            page_texts[i] = words
        
        # Extract form fields
        pdf_fields = reader.get_fields() or {}
        
        for field_name, field_info in pdf_fields.items():
            if not isinstance(field_info, dict):
                continue
            
            # Skip XFA container/structural fields
            if _is_xfa_container(field_name, field_info):
                continue

            
            # Determine page
            page_num = 0
            if "/P" in field_info:
                # Try to find page index
                for i, page in enumerate(reader.pages):
                    if page.get_object() == field_info["/P"]:
                        page_num = i
                        break
            
            # Extract position
            position = _extract_field_position(field_info, page_num)
            

            # GENERIC: Use XFA-extracted labels (from PDF itself, not hardcoded!)
            # Extract leaf name for lookup (e.g., "f1_01" from "topmostSubform[0].Page1[0].f1_01[0]")
            import re as re_local
            leaf_name = re_local.sub(r'\[\d+\]', '', field_name.split('.')[-1])
            xfa_field = xfa_labels.get(leaf_name)
            
            # Extract field type (ENHANCED) - Moved up for proximity search context
            # We need the type to know if we should look Right (checkbox) or Left/Top (text)
            temp_context = FieldContext(nearby_text="", instructions="")
            field_type = _detect_field_type_enhanced(field_info, field_name, temp_context)
            if field_type == FieldType.BUTTON:
                continue  # Skip push buttons
            
            # Find label strategies:
            # 1. XFA Label (best if real human text)
            # 2. Proximity Label (visual fallback)
            # 3. Tooltip (fallback)
            
            label_candidates = []
            
            # Strategy A: XFA Label
            if xfa_field and xfa_field.label:
                label_candidates.append(xfa_field.label)
                
            # Strategy B: Tooltip
            tooltip = field_info.get("/TU", "") or field_info.get("/T", "")
            if tooltip:
                label_candidates.append(str(tooltip))
                
            # Strategy C: Visual Proximity
            page_blocks = page_texts.get(page_num, [])
            visual_label = _find_label_for_field(position, page_blocks, field_type=field_type)
            
            # SELECTION LOGIC
            label = ""
            
            # First, check if XFA/Tooltip are "junk" (technical IDs)
            candidate_labels = [l for l in label_candidates if l]
            valid_candidates = [l for l in candidate_labels if not _is_technical_id(l)]
            
            if valid_candidates:
                label = valid_candidates[0]
            elif visual_label:
                # If digital labels were junk (IDs), fallback to visual
                label = visual_label
            else:
                # Last resort: use the junk label but clean it up
                label = candidate_labels[0] if candidate_labels else ""
                
            # Final Cleaning
            label = _clean_label(label)
            
            # BUILD CONTEXT
            context = FieldContext(
                nearby_text=label + (" " + visual_label if visual_label and visual_label != label else ""),
                instructions=xfa_field.speak_text if xfa_field and xfa_field.speak_text else str(tooltip) if tooltip else "",
                is_required_visually=("*" in label) if label else False
            )

            # Re-detect type with full context
            field_type = _detect_field_type_enhanced(field_info, field_name, context)

            # Extract constraints (ENHANCED)
            constraints = _extract_validation_rules(field_info, context)
            
            # Extract options for choice fields
            options = []
            if field_type in (FieldType.DROPDOWN, FieldType.LISTBOX, FieldType.RADIO):
                options = _extract_options(field_info)
            
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
            
            # Detect section and form_line using label-based detection
            # (XFA doesn't provide section info, so we use keyword detection)
            section = _detect_section(field_name, label, page_blocks)
            form_line = _extract_form_line(field_name, label)
            
            # Generate display name - prefer label, fall back to cleaned field name leaf
            if label:
                display_name = label
            else:
                # Extract leaf node from XFA path for cleaner display
                leaf_name = field_name.split('.')[-1]
                # Remove [index] and clean up
                leaf_name = re.sub(r'\[\d+\]', '', leaf_name)
                display_name = leaf_name
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
                context=context,
                section=section,
                form_line=form_line,
            )
            
            fields.append(pdf_field)
        
        plumber_pdf.close()
        
    except Exception as e:
        logger.error(f"Error parsing AcroForm: {e}")
        raise PdfParsingError(f"AcroForm parsing failed: {str(e)}", original_error=e)
    
    # Sort by tab order / position
    fields.sort(key=lambda f: (f.position.page, f.position.y, f.position.x))
    
    return fields


@benchmark("parse_visual_form")
def _parse_visual_form(pdf_path: Union[str, Path, bytes]) -> List[PdfField]:
    """
    Parse visual form patterns from text-based PDFs.
    
    Detects form fields by looking for patterns like:
    - "Label: _______________"
    - "Label: " followed by blank space
    - "Label (DD/MM/YYYY):" date patterns
    - Lines ending with colons
    
    This is useful for PDFs that don't have AcroForm fields but
    have visual form layouts.
    Uses precise coordinate extraction via pdfplumber.extract_words().
    """
    fields = []
    
    try:
        if isinstance(pdf_path, bytes):
            plumber_pdf = pdfplumber.open(io.BytesIO(pdf_path))
        else:
            plumber_pdf = pdfplumber.open(str(pdf_path))
        
        # Generalized structural patterns that indicate form fields
        field_patterns = [
            (r'^(.+?):\s*_{2,}\s*$', 'text'), # "Label: ____"
            (r'^(.+?)\s*\([^)]+\):\s*_{2,}\s*$', 'text'), # "Label (Hint): ____"
            (r'^([A-Za-z][A-Za-z\s&/-]{2,50}):\s*$', 'text'), # "Label: "
            (r'^([A-Za-z][A-Za-z\s]{2,50})\s+_{3,}\s*$', 'text'), # "Label ____"
            (r'^(.+?)\s*\.{4,}\s*$', 'text'), # "Label ...."
        ]
        
        field_id = 0
        seen_labels = set()
        
        logger.info("Using coordinate-aware visual parsing.")
        
        for page_num, page in enumerate(plumber_pdf.pages):
            # Extract words with coordinates
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            if not words:
                continue
            
            # Group words into lines based on Y-coordinate (top)
            # 1. Sort by top, then x
            words.sort(key=lambda w: (float(w['top']), float(w['x0'])))
            
            lines = []
            if words:
                current_line = [words[0]]
                last_top = float(words[0]['top'])
                
                for word in words[1:]:
                    word_top = float(word['top'])
                    # If words are roughly on same line (within 4px)
                    if abs(word_top - last_top) < 4:
                        current_line.append(word)
                    else:
                        lines.append(current_line)
                        current_line = [word]
                        last_top = word_top
                lines.append(current_line)
            
            page_height = float(page.height)
            page_width = float(page.width)

            for line_words in lines:
                # Reconstruct text line
                line_text = " ".join([w['text'] for w in line_words])
                
                matched = False
                for pattern, _ in field_patterns:
                    match = re.match(pattern, line_text, re.IGNORECASE)
                    if match:
                        label = match.group(1).strip()
                        
                        # Cleanup Label
                        label = re.sub(r'\s+', ' ', label)
                        label = label.rstrip(':').strip()
                        label = label.rstrip('.').strip()
                        
                        # Basic Validations
                        if len(label) < 2 or len(label) > 100: continue # Increased max length slightly
                        if len(label.split()) > 15: continue # Increased max words
                        if label.lower() in seen_labels: continue
                        
                        # Skip Patterns - simplified to common non-field items
                        skip_patterns = [
                            'page of', 'page :', 'terms and conditions', 'instructions:', 
                            'form no', 'version:', 'revised:', 'office use only'
                        ]
                        is_skip = False
                        for sp in skip_patterns:
                            if label.lower().startswith(sp):
                                is_skip = True; break
                        if is_skip: continue
                        
                        seen_labels.add(label.lower())
                        field_id += 1
                        
                        # Purpose Inference
                        purpose = _detect_purpose(label, "")
                        detected_type = 'text'
                        if purpose in ['email']: detected_type = 'email'
                        elif purpose in ['phone', 'mobile']: detected_type = 'phone'
                        elif purpose in ['date', 'dob']: detected_type = 'date'
                        elif purpose in ['number', 'zip', 'postal', 'amount', 'salary']: detected_type = 'number'
                        if 'signature' in label.lower(): detected_type = 'signature'

                        # --- COORDINATE CALCULATION ---
                        
                        # Find valid tokens for coordinate calculation
                        underscore_word = next((w for w in line_words if '_' in w['text']), None)
                        colon_word = next((w for w in reversed(line_words) if ':' in w['text']), None)

                        # Precise Baseline Alignment
                        if underscore_word:
                             max_bottom = float(underscore_word['bottom'])
                        else:
                             # Average bottom of line words
                             max_bottom = float(sum(float(w['bottom']) for w in line_words) / len(line_words))
                        
                        # Dynamic field height based on approximate font height
                        # height = bottom - top
                        # We avg the heights of words in the line
                        avg_line_height = sum(float(w['bottom']) - float(w['top']) for w in line_words) / len(line_words)
                        field_height = max(14.0, avg_line_height + 2) # At least 14, or line height + padding
                        
                        # Calculate 'y' (top) such that 'y + height' equals the baseline 'bottom'
                        pdf_y = max_bottom - field_height
                        
                        # X: Try to find start of input area.
                        if underscore_word:
                             start_x = float(underscore_word['x0'])
                        elif colon_word:
                             start_x = float(colon_word['x1']) + 5 # Small padding after colon
                        else:
                             # Use end of last word + gap
                             start_x = float(line_words[-1]['x1']) + 10
                        
                        # Ensure X is within page bounds
                        if start_x > page_width - 20: 
                            start_x = page_width - 100 # Fallback if calculated X is off-page
                            
                        # Calculate available width
                        available_width = page_width - start_x - 40 # 40px right margin
                        field_width = max(100.0, available_width) # Min 100px
                        
                        logger.info(f"Field '{label}' detected at Page {page_num+1} Baseline={max_bottom:.2f} X={start_x:.2f}")

                        field = PdfField(
                            id=f"visual_field_{field_id}",
                            name=f"field_{field_id}_{label.lower().replace(' ', '_')[:30]}",
                            field_type=FieldType(detected_type) if detected_type in [e.value for e in FieldType] else FieldType.TEXT,
                            label=label,
                            position=FieldPosition(
                                page=page_num,
                                x=start_x,
                                y=pdf_y, 
                                width=field_width,
                                height=field_height,
                            ),
                            constraints=FieldConstraints(),
                            display_name=label.title(),
                            purpose=purpose,
                        )
                        fields.append(field)
                        matched = True
                        break # Stop patterns for this line
                
                if matched: continue # Next line

        plumber_pdf.close()
        logger.info(f"Visual form parsing found {len(fields)} fields")
        
    except Exception as e:
        logger.error(f"Error parsing visual form: {e}")
        # Non-critical failure, return what we found
    
    return fields

@benchmark("parse_scanned_pdf")
def _parse_scanned_pdf(pdf_path: Union[str, Path, bytes]) -> List[PdfField]:
    """
    Parse scanned PDF using OCR.
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
                            height=20,
                        ),
                        constraints=FieldConstraints(),
                        display_name=text.rstrip(":").title(),
                        purpose=_detect_purpose(text, ""),
                    )
                    fields.append(field)
        
    except Exception as e:
        logger.warning(f"Error during OCR parsing: {e}")

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
        try:
            md = reader.metadata
            if md:
                # pypdf metadata is accessed via attributes, not dict keys
                metadata = {
                    "title": getattr(md, 'title', '') or '',
                    "author": getattr(md, 'author', '') or '',
                    "creator": getattr(md, 'creator', '') or '',
                    "producer": getattr(md, 'producer', '') or '',
                }
        except Exception as e:
            logger.debug(f"Could not extract metadata: {e}")
    
    # Parse fields
    fields = []
    parsing_method = "unknown"
    
    # Strategy 1: AcroForm (Standard)
    # Even if XFA, we try AcroForm extraction first as many XFAs have AcroForm wrappers
    if not is_scanned:
        try:
            fields = _parse_acroform(pdf_source)
            if fields:
                parsing_method = "acroform"
                logger.info(f"AcroForm parsing successful: found {len(fields)} fields")
        except Exception as e:
            logger.warning(f"AcroForm parsing failed: {e}")

    # Strategy 2: Visual Form (Fallback)
    # If AcroForm yielded nothing, or if it failed, try Visual Parsing
    if not fields and not is_scanned:
        logger.info("No AcroForm fields found, attempting visual form pattern detection...")
        fields = _parse_visual_form(pdf_source)
        if fields:
            parsing_method = "visual"
            logger.info(f"Visual form parsing successful: found {len(fields)} fields")

    # Strategy 3: OCR (Last Resort)
    # If still no fields, and OCR is allowed, try it.
    # This handles "Scanned" files or just image-heavy PDFs that failed detection.
    if not fields and use_ocr:
        logger.info("No text fields found. Attempting OCR extraction...")
        fields = _parse_scanned_pdf(pdf_source)
        if fields:
            parsing_method = "ocr"
            logger.info(f"OCR parsing successful: found {len(fields)} fields")
            
    # Metadata update
    if parsing_method == "visual" or parsing_method == "ocr":
        # Mark as scanned/visual in schema if fallback was used
        is_scanned = True 

    # Generate groups
    groups = _group_fields(fields)

    return PdfFormSchema(
        file_path=file_path,
        file_name=file_name,
        total_pages=total_pages,
        fields=fields,
        groups=groups,
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
