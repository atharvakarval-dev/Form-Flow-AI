"""
PDF Services Module

Provides PDF form parsing, filling, and text fitting capabilities.
"""

from .pdf_parser import (
    parse_pdf,
    PdfFormSchema,
    PdfField,
    FieldType,
)
from .pdf_writer import (
    fill_pdf,
    FilledPdf,
)
from .text_fitter import (
    TextFitter,
    FitResult,
)

__all__ = [
    # Parser
    "parse_pdf",
    "PdfFormSchema",
    "PdfField",
    "FieldType",
    # Writer
    "fill_pdf",
    "FilledPdf",
    # Text Fitter
    "TextFitter",
    "FitResult",
]
