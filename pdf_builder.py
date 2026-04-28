from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models import InvoicePayload, ComputationResult


def _draw_text_line(pdf: canvas.Canvas, text: str, x_mm: float, y_mm: float) -> None:
    pdf.drawString(x_mm * mm, y_mm * mm, text)


def build_pdf_stub(payload: InvoicePayload, computed: ComputationResult) -> bytes:
    """
    Construit un PDF simple et lisible pour le dev.

    Ce n’est pas encore du PDF/A‑3 ni un vrai Factur‑X, mais ça donne
    une représentation claire du contenu de la facture pour tests/démos.
    """
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle(f"Invoice {payload.invoice.number}")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(20 * mm, height - 20 * mm, "Invoice Stub V2")

    pdf.setFont("Helvetica", 10)
    y = (height / mm) - 35

    header_lines = [
        f"Invoice number: {payload.invoice.number}",
        f"Issue date: {payload.invoice.issue_date.isoformat()}",
        f"Currency: {payload.invoice.currency}",
        f"Operation nature: {payload.invoice.operation_nature.value}",
        f"Seller: {payload.seller.name} (SIREN {payload.seller.siren})",
        f"Buyer: {payload.buyer.name} (SIREN {payload.buyer.siren})",
        "",
        "Invoice lines:",
    ]

    for line in header_lines:
        _draw_text_line(pdf, line, 20, y)
        y -= 6

    for line in computed.lines:
        text = (
            f"[{line.line_number}] {line.description} | qty {line.quantity} "
            f"| unit HT {line.unit_price_ht:.2f} | TVA {line.tva_rate:.2f}% "
            f"| TTC {line.line_ttc:.2f}"
        )
        _draw_text_line(pdf, text, 20, y)
        y -= 6
        if y < 30:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = (height / mm) - 20

    y -= 4
    summary_lines = [
        f"Total discount: {computed.totals.total_discount:.2f} {payload.invoice.currency}",
        f"Total HT: {computed.totals.total_ht:.2f} {payload.invoice.currency}",
        f"Total TVA: {computed.totals.total_tva:.2f} {payload.invoice.currency}",
        f"Total TTC: {computed.totals.total_ttc:.2f} {payload.invoice.currency}",
    ]
    for line in summary_lines:
        _draw_text_line(pdf, line, 20, y)
        y -= 6

    if payload.invoice.tva_on_debits_option:
        y -= 3
        _draw_text_line(pdf, "VAT mention: Option for payment of VAT on debits", 20, y)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()