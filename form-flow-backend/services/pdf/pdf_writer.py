"""
PDF Writer - Form Filling Engine

Fills PDF forms with user data, handling:
- Text fields with dynamic sizing
- Checkboxes and radio buttons
- Dropdowns and listboxes
- Multi-line text wrapping
- Font size adjustment for space constraints

Uses reportlab for PDF generation and pypdf for form manipulation.
"""

import logging
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import tempfile
import shutil

logger = logging.getLogger(__name__)

# PDF Libraries
try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (
        NameObject, TextStringObject, ArrayObject, 
        DictionaryObject, BooleanObject, NumberObject
    )
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    PdfReader = None
    PdfWriter = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    canvas = None

from .text_fitter import TextFitter, FitResult


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class FieldFillResult:
    """Result of filling a single field."""
    field_name: str
    success: bool
    original_value: str
    filled_value: str
    error: Optional[str] = None
    fit_result: Optional[FitResult] = None


@dataclass
class FilledPdf:
    """Result of filling a PDF form."""
    success: bool
    output_path: Optional[str] = None
    output_bytes: Optional[bytes] = None
    field_results: List[FieldFillResult] = None
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.field_results is None:
            self.field_results = []
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
    
    @property
    def fields_filled(self) -> int:
        return sum(1 for r in self.field_results if r.success)
    
    @property
    def fields_failed(self) -> int:
        return sum(1 for r in self.field_results if not r.success)


# =============================================================================
# PDF Writer Class
# =============================================================================

class PdfFormWriter:
    """
    PDF form filling engine.
    
    Supports multiple strategies for form filling:
    1. Direct AcroForm field manipulation (preferred)
    2. Overlay text on specific coordinates (fallback)
    """
    
    def __init__(
        self,
        text_fitter: Optional[TextFitter] = None,
        default_font_size: float = 12.0,
        min_font_size: float = 6.0,
    ):
        """
        Initialize PDF writer.
        
        Args:
            text_fitter: TextFitter instance for text compression
            default_font_size: Default font size for text
            min_font_size: Minimum font size for auto-sizing
        """
        if not PYPDF_AVAILABLE:
            raise ImportError("pypdf is required. Install with: pip install pypdf")
        
        self.text_fitter = text_fitter or TextFitter()
        self.default_font_size = default_font_size
        self.min_font_size = min_font_size
    
    def fill(
        self,
        template_path: Union[str, Path, bytes],
        data: Dict[str, str],
        output_path: Optional[Union[str, Path]] = None,
        flatten: bool = False,
        fit_text: bool = True,
    ) -> FilledPdf:
        """
        Fill a PDF form with data.
        
        Args:
            template_path: Path to template PDF or PDF bytes
            data: Dictionary of {field_name: value}
            output_path: Path to save filled PDF (None for bytes output)
            flatten: Whether to flatten form fields (make non-editable)
            fit_text: Whether to apply text fitting
            
        Returns:
            FilledPdf with results
        """
        result = FilledPdf(success=True)
        
        try:
            # Open template
            if isinstance(template_path, bytes):
                reader = PdfReader(io.BytesIO(template_path))
            else:
                reader = PdfReader(str(template_path))
            
            writer = PdfWriter()
            
            # Get form fields
            fields = reader.get_fields() or {}
            
            if not fields:
                result.warnings.append("No AcroForm fields found. Attempting visual filling.")
                # Try visual overlay filling (modifies reader pages in-place)
                self._fill_overlay(reader, writer, data, result)
            
            # Add pages to writer (now that they might be modified)
            for page in reader.pages:
                writer.add_page(page)

            if fields:
                # Fill each AcroForm field
                for field_name, value in data.items():
                    field_result = self._fill_field(
                        writer=writer,
                        field_name=field_name,
                        value=value,
                        fields=fields,
                        fit_text=fit_text,
                    )
                    result.field_results.append(field_result)
                    
                    if not field_result.success:
                        result.warnings.append(
                            f"Field '{field_name}': {field_result.error}"
                        )
            
            # Flatten if requested
            if flatten:
                try:
                    # Create flattened version by removing form fields
                    # This is a simplified approach
                    for page in writer.pages:
                        if "/Annots" in page:
                            annots = page["/Annots"]
                            # Keep non-widget annotations
                            new_annots = []
                            for annot in annots:
                                annot_obj = annot.get_object() if hasattr(annot, 'get_object') else annot
                                if annot_obj.get("/Subtype") != "/Widget":
                                    new_annots.append(annot)
                            if new_annots:
                                page[NameObject("/Annots")] = ArrayObject(new_annots)
                            else:
                                del page["/Annots"]
                except Exception as e:
                    result.warnings.append(f"Flattening partially failed: {e}")
            
            # Output
            if output_path:
                with open(str(output_path), "wb") as f:
                    writer.write(f)
                result.output_path = str(output_path)
            else:
                output_buffer = io.BytesIO()
                writer.write(output_buffer)
                result.output_bytes = output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error filling PDF: {e}")
            result.success = False
            result.errors.append(str(e))
        
        return result

    def _fill_overlay(
        self,
        reader: PdfReader,
        writer: PdfWriter,
        data: Dict[str, str],
        result: FilledPdf,
    ):
        """Fill visual form by overlaying text."""
        import traceback
        if not REPORTLAB_AVAILABLE:
            result.warnings.append("ReportLab required for visual form filling")
            return

        try:
            logger.info("Starting visual overlay fill...")
            
            # Re-parse to get field coordinates
            from .pdf_parser import parse_pdf
            
            # Create a bytes buffer from the reader content for parsing
            pdf_bytes_io = io.BytesIO()
            tmp_writer = PdfWriter()
            for page in reader.pages:
                tmp_writer.add_page(page)
            tmp_writer.write(pdf_bytes_io)
            pdf_bytes = pdf_bytes_io.getvalue()
            
            logger.info("Re-parsing PDF for visual structure...")
            schema = parse_pdf(pdf_bytes, use_ocr=False)
            logger.info(f"Visual parser found {len(schema.fields)} fields")
            
            filled_fields = 0
            
            # Create overlay for specific pages
            for i, page in enumerate(reader.pages):
                # Check for matching fields on this page first to avoid empty work
                page_fields = [f for f in schema.fields if f.position.page == i]
                if not page_fields:
                    continue
                    
                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=(
                    float(page.mediabox.width), 
                    float(page.mediabox.height)
                ))
                
                logger.info(f"Processing Page {i+1} with {len(page_fields)} fields")
                
                has_content = False
                for field in page_fields:
                    # Strategy: Exact Match > Display Name > Label > Fuzzy Match
                    val = data.get(field.name) or data.get(field.display_name) or data.get(field.label)
                    
                    if not val:
                        # Clean matching
                        field_clean = re.sub(r'[^a-zA-Z0-9]', '', field.label.lower())
                        
                        for k, v in data.items():
                            k_clean = re.sub(r'[^a-zA-Z0-9]', '', k.lower())
                            if field_clean and k_clean and (field_clean == k_clean or field_clean in k_clean or k_clean in field_clean):
                                val = v
                                logger.info(f"Fuzzy matched '{k}' -> '{field.label}'")
                                break
                    
                    if val:
                        # Use field height to estimate font size if dynamic
                        # Simple heuristic: 70% of field height
                        font_size_to_use = self.default_font_size
                        if field.position.height > 5:
                            estimated_size = field.position.height * 0.7
                            font_size_to_use = max(self.min_font_size, min(estimated_size, 14.0))

                        # Coordinates
                        x = field.position.x
                        
                        # ReportLab Y is from bottom.
                        # Field Y from parser is from top to top-of-field.
                        # To align baseline: PageHeight - (y_from_top + height)
                        # We add a small padding for visual lift off the underline
                        y = float(page.mediabox.height) - (field.position.y + field.position.height) + 2.0
                        
                        try:
                            can.setFont("Helvetica", font_size_to_use)
                            can.drawString(x, y, str(val))
                            has_content = True
                            
                            result.field_results.append(FieldFillResult(
                                field_name=field.name,
                                success=True,
                                original_value=val,
                                filled_value=val
                            ))
                            filled_fields += 1
                        except Exception as e:
                             logger.error(f"Error drawing string for field {field.name}: {e}")
                
                can.save()
                
                if has_content:
                    # Merge overlay
                    packet.seek(0)
                    overlay_pdf = PdfReader(packet)
                    if len(overlay_pdf.pages) > 0:
                        page.merge_page(overlay_pdf.pages[0])
                        logger.info(f"Merged overlay onto Page {i+1}")
            
            if filled_fields == 0:
                result.warnings.append("No matching fields found for visual filling")
                logger.warning("Visual filling completed but no fields were filled.")
            else:
                logger.info(f"Visual filling completed. Filled {filled_fields} fields.")
                
        except Exception as e:
            logger.error(f"Error in overlay fill: {e}")
            logger.error(traceback.format_exc())
            result.warnings.append(f"Visual filling failed: {e}")
    
    def _fill_field(
        self,
        writer: PdfWriter,
        field_name: str,
        value: str,
        fields: Dict[str, Any],
        fit_text: bool = True,
    ) -> FieldFillResult:
        """Fill a single form field."""
        original_value = value
        fit_result = None
        
        try:
            # Check if field exists
            if field_name not in fields:
                # Try partial matching
                matched = None
                for fname in fields:
                    if field_name.lower() in fname.lower() or fname.lower() in field_name.lower():
                        matched = fname
                        break
                
                if not matched:
                    return FieldFillResult(
                        field_name=field_name,
                        success=False,
                        original_value=original_value,
                        filled_value="",
                        error=f"Field not found in PDF"
                    )
                field_name = matched
            
            field_info = fields[field_name]
            field_type = field_info.get("/FT", "")
            
            # Get field constraints
            max_length = field_info.get("/MaxLen")
            
            # Apply text fitting if needed
            if fit_text and field_type == "/Tx" and max_length:
                field_context = {
                    "name": field_name,
                    "type": "text",
                    "max_length": max_length,
                }
                fit_result = self.text_fitter.fit(
                    value, 
                    max_length, 
                    field_context
                )
                value = fit_result.fitted
            
            # Fill based on field type
            if field_type == "/Tx":  # Text field
                self._fill_text_field(writer, field_name, value)
            
            elif field_type == "/Btn":  # Button (checkbox/radio)
                flags = field_info.get("/Ff", 0)
                if flags & (1 << 15):  # Radio
                    self._fill_radio_button(writer, field_name, value, field_info)
                else:  # Checkbox
                    self._fill_checkbox(writer, field_name, value)
            
            elif field_type == "/Ch":  # Choice (dropdown/listbox)
                self._fill_choice_field(writer, field_name, value.strip(), field_info)
            
            else:
                # Generic fill attempt
                self._fill_text_field(writer, field_name, value)
            
            return FieldFillResult(
                field_name=field_name,
                success=True,
                original_value=original_value,
                filled_value=value,
                fit_result=fit_result,
            )
            
        except Exception as e:
            logger.error(f"Error filling field {field_name}: {e}")
            return FieldFillResult(
                field_name=field_name,
                success=False,
                original_value=original_value,
                filled_value="",
                error=str(e),
            )
    
    def _fill_text_field(
        self,
        writer: PdfWriter,
        field_name: str,
        value: str,
    ):
        """Fill a text field."""
        writer.update_page_form_field_values(
            writer.pages[0],  # Update all pages
            {field_name: value},
            auto_regenerate=True,
        )
    
    def _fill_checkbox(
        self,
        writer: PdfWriter,
        field_name: str,
        value: str,
    ):
        """Fill a checkbox field."""
        # Determine checked state
        checked = value.lower() in ('yes', 'true', '1', 'checked', 'on', 'x')
        check_value = "/Yes" if checked else "/Off"
        
        writer.update_page_form_field_values(
            writer.pages[0],
            {field_name: check_value},
        )
    
    def _fill_radio_button(
        self,
        writer: PdfWriter,
        field_name: str,
        value: str,
        field_info: Dict[str, Any],
    ):
        """Fill a radio button group."""
        # Find matching option
        kids = field_info.get("/Kids", [])
        for kid in kids:
            kid_obj = kid.get_object() if hasattr(kid, 'get_object') else kid
            ap = kid_obj.get("/AP", {})
            if "/N" in ap:
                # Get option names
                for opt_name in ap["/N"].keys():
                    if opt_name != "/Off" and value.lower() in str(opt_name).lower():
                        writer.update_page_form_field_values(
                            writer.pages[0],
                            {field_name: opt_name},
                        )
                        return
        
        # Fallback: try direct value
        writer.update_page_form_field_values(
            writer.pages[0],
            {field_name: f"/{value}"},
        )
    
    def _fill_choice_field(
        self,
        writer: PdfWriter,
        field_name: str,
        value: str,
        field_info: Dict[str, Any],
    ):
        """Fill a dropdown or listbox field."""
        # Get available options
        options = field_info.get("/Opt", [])
        
        # Find best matching option
        best_match = value
        for opt in options:
            if isinstance(opt, list) and len(opt) >= 2:
                opt_value = str(opt[1])
            else:
                opt_value = str(opt)
            
            if value.lower() == opt_value.lower():
                best_match = opt_value
                break
            elif value.lower() in opt_value.lower():
                best_match = opt_value
        
        writer.update_page_form_field_values(
            writer.pages[0],
            {field_name: best_match},
        )


# =============================================================================
# Main Functions
# =============================================================================

def fill_pdf(
    template_path: Union[str, Path, bytes],
    data: Dict[str, str],
    output_path: Optional[Union[str, Path]] = None,
    flatten: bool = False,
) -> FilledPdf:
    """
    Fill a PDF form with data.
    
    Args:
        template_path: Path to template PDF or PDF bytes
        data: Dictionary of {field_name: value}
        output_path: Path to save filled PDF (None for bytes output)
        flatten: Whether to flatten form fields
        
    Returns:
        FilledPdf with results
    """
    writer = PdfFormWriter()
    return writer.fill(template_path, data, output_path, flatten)


def preview_fill(
    template_path: Union[str, Path, bytes],
    data: Dict[str, str],
) -> Dict[str, Any]:
    """
    Preview how data would be filled without actually creating PDF.
    
    Returns what values would be used for each field after text fitting.
    """
    fitter = TextFitter()
    
    # Open template to get field info
    if isinstance(template_path, bytes):
        reader = PdfReader(io.BytesIO(template_path))
    else:
        reader = PdfReader(str(template_path))
    
    fields = reader.get_fields() or {}
    
    preview = {}
    for field_name, value in data.items():
        field_info = fields.get(field_name, {})
        max_length = field_info.get("/MaxLen")
        
        if max_length:
            fit_result = fitter.fit(value, max_length)
            preview[field_name] = {
                "original": value,
                "fitted": fit_result.fitted,
                "strategy": fit_result.strategy_used,
                "truncated": fit_result.truncated,
            }
        else:
            preview[field_name] = {
                "original": value,
                "fitted": value,
                "strategy": "direct_fit",
                "truncated": False,
            }
    
    return preview


def get_pdf_field_names(
    pdf_path: Union[str, Path, bytes],
) -> List[str]:
    """Get list of fillable field names from a PDF."""
    if isinstance(pdf_path, bytes):
        reader = PdfReader(io.BytesIO(pdf_path))
    else:
        reader = PdfReader(str(pdf_path))
    
    fields = reader.get_fields() or {}
    return list(fields.keys())
