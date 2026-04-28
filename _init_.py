"""
Service layer for the e-invoicing demo backend.

This package contains:
- compute: core pricing / VAT computation logic
- xml_builder: XML representation of the invoice
- pdf_builder: simple human‑readable PDF output
"""

from .compute import compute_invoice  # noqa: F401
from .xml_builder import build_xml  # noqa: F401
from .pdf_builder import build_pdf_stub  # noqa: F401