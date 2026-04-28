from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from io import BytesIO
from typing import List, Optional
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import FastAPI
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, EmailStr, Field, HttpUrl, ConfigDict, constr
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


class OperationNature(str, Enum):
    goods = "goods"
    services = "services"
    mixed = "mixed"


class Profile(str, Enum):
    BASIC = "BASIC"
    EN16931 = "EN16931"


SIREN = constr(pattern=r"^[0-9]{9}$")
SIRET = constr(pattern=r"^[0-9]{14}$")
CountryCode = constr(pattern=r"^[A-Z]{2}$")
CurrencyCode = constr(pattern=r"^[A-Z]{3}$")


class Address(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line1: str = Field(..., min_length=1)
    line2: Optional[str] = None
    postal_code: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    country_code: CountryCode = Field(default="FR")


class InvoiceHeader(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str = Field(..., min_length=1)
    issue_date: date
    supply_date: Optional[date] = None
    currency: CurrencyCode = Field(default="EUR")
    operation_nature: OperationNature
    tva_on_debits_option: bool = Field(default=False)
    payment_terms: Optional[str] = None
    due_date: Optional[date] = None


class Seller(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    siren: SIREN
    siret: Optional[SIRET] = None
    vat_number: Optional[str] = None
    naf_code: Optional[str] = None
    legal_form: Optional[str] = None
    share_capital: Optional[float] = None
    rcs_city: Optional[str] = None
    address: Address
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[HttpUrl] = None


class Buyer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    siren: SIREN
    siret: Optional[SIRET] = None
    vat_number: Optional[str] = None
    address_billing: Address
    address_shipping: Optional[Address] = None
    email: Optional[EmailStr] = None


class InvoiceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_number: int = Field(..., ge=1)
    description: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)
    unit: Optional[str] = None
    unit_price_ht: float = Field(..., ge=0)
    tva_rate: float = Field(..., ge=0)
    discount_rate: float = Field(default=0, ge=0, le=100)


class InvoiceTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_ht: Optional[float] = None
    total_discount: Optional[float] = None
    total_tva: Optional[float] = None
    total_ttc: Optional[float] = None


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(default="fr")
    profile: Profile = Field(default=Profile.BASIC)
    created_at: Optional[datetime] = None
    generation_tool: Optional[str] = None


class InvoicePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice: InvoiceHeader
    seller: Seller
    buyer: Buyer
    lines: List[InvoiceLine]
    totals: Optional[InvoiceTotals] = None
    meta: Optional[Meta] = None


class ComputedLine(BaseModel):
    line_number: int
    description: str
    quantity: float
    unit: Optional[str] = None
    unit_price_ht: float
    discount_rate: float
    tva_rate: float
    line_gross_ht: float
    line_discount: float
    line_net_ht: float
    line_tva: float
    line_ttc: float


class ComputationResult(BaseModel):
    totals: InvoiceTotals
    lines: List[ComputedLine]


def round2(value: float) -> float:
    return round(value + 1e-9, 2)


def compute_invoice(payload: InvoicePayload) -> ComputationResult:
    computed_lines: List[ComputedLine] = []
    total_ht = 0.0
    total_discount = 0.0
    total_tva = 0.0

    for line in payload.lines:
        gross = line.quantity * line.unit_price_ht
        discount = gross * (line.discount_rate / 100.0)
        net = gross - discount
        tva_amount = net * (line.tva_rate / 100.0)
        ttc = net + tva_amount

        computed = ComputedLine(
            line_number=line.line_number,
            description=line.description,
            quantity=line.quantity,
            unit=line.unit,
            unit_price_ht=round2(line.unit_price_ht),
            discount_rate=round2(line.discount_rate),
            tva_rate=round2(line.tva_rate),
            line_gross_ht=round2(gross),
            line_discount=round2(discount),
            line_net_ht=round2(net),
            line_tva=round2(tva_amount),
            line_ttc=round2(ttc),
        )
        computed_lines.append(computed)

        total_ht += net
        total_discount += discount
        total_tva += tva_amount

    totals = InvoiceTotals(
        total_ht=round2(total_ht),
        total_discount=round2(total_discount),
        total_tva=round2(total_tva),
        total_ttc=round2(total_ht + total_tva),
    )
    return ComputationResult(totals=totals, lines=computed_lines)


def add_address(parent: Element, tag_name: str, address: Address) -> None:
    node = SubElement(parent, tag_name)
    SubElement(node, "Line1").text = address.line1
    SubElement(node, "Line2").text = address.line2 or ""
    SubElement(node, "PostalCode").text = address.postal_code
    SubElement(node, "City").text = address.city
    SubElement(node, "CountryCode").text = address.country_code


def build_xml(payload: InvoicePayload, computed: ComputationResult) -> bytes:
    language = payload.meta.language if payload.meta else "fr"
    profile = payload.meta.profile.value if payload.meta else "BASIC"

    root = Element(
        "Invoice",
        attrib={
            "xmlns": "https://rennesdev.fr/schema/invoice/v2",
            "profile": profile,
            "currency": payload.invoice.currency,
            "language": language,
        },
    )

    header = SubElement(root, "InvoiceHeader")
    SubElement(header, "Number").text = payload.invoice.number
    issue_date_elem = SubElement(header, "IssueDate")
    issue_date_elem.text = payload.invoice.issue_date.isoformat()
    if payload.invoice.supply_date:
        supply_date_elem = SubElement(header, "SupplyDate")
        supply_date_elem.text = payload.invoice.supply_date.isoformat()
    op_nature_elem = SubElement(header, "OperationNature")
    op_nature_elem.text = payload.invoice.operation_nature.value
    SubElement(
        header,
        "TVAOnDebitsOption",
    ).text = "true" if payload.invoice.tva_on_debits_option else "false"
    if payload.invoice.payment_terms:
        SubElement(header, "PaymentTerms").text = (
            payload.invoice.payment_terms
        )
    if payload.invoice.due_date:
        SubElement(header, "DueDate").text = (
            payload.invoice.due_date.isoformat()
        )

    seller = SubElement(root, "Seller")
    SubElement(seller, "Name").text = payload.seller.name
    SubElement(seller, "SIREN").text = payload.seller.siren
    if payload.seller.siret:
        SubElement(seller, "SIRET").text = payload.seller.siret
    if payload.seller.vat_number:
        SubElement(seller, "VATNumber").text = payload.seller.vat_number
    if payload.seller.naf_code:
        SubElement(seller, "NAFCode").text = payload.seller.naf_code
    if payload.seller.legal_form:
        SubElement(seller, "LegalForm").text = payload.seller.legal_form
    if payload.seller.share_capital is not None:
        SubElement(seller, "ShareCapital").text = (
            f"{payload.seller.share_capital:.2f}"
        )
    if payload.seller.rcs_city:
        SubElement(seller, "RCSCity").text = payload.seller.rcs_city
    add_address(seller, "Address", payload.seller.address)
    if payload.seller.email:
        SubElement(seller, "Email").text = str(payload.seller.email)
    if payload.seller.phone:
        SubElement(seller, "Phone").text = payload.seller.phone
    if payload.seller.website:
        SubElement(seller, "Website").text = str(payload.seller.website)

    buyer = SubElement(root, "Buyer")
    SubElement(buyer, "Name").text = payload.buyer.name
    SubElement(buyer, "SIREN").text = payload.buyer.siren
    if payload.buyer.siret:
        SubElement(buyer, "SIRET").text = payload.buyer.siret
    if payload.buyer.vat_number:
        SubElement(buyer, "VATNumber").text = payload.buyer.vat_number
    add_address(buyer, "BillingAddress", payload.buyer.address_billing)
    if payload.buyer.address_shipping:
        add_address(buyer, "ShippingAddress", payload.buyer.address_shipping)
    if payload.buyer.email:
        SubElement(buyer, "Email").text = str(payload.buyer.email)

    lines_node = SubElement(root, "Lines")
    for line in computed.lines:
        line_el = SubElement(lines_node, "Line")
        SubElement(line_el, "LineNumber").text = str(line.line_number)
        SubElement(line_el, "Description").text = line.description
        quantity = SubElement(line_el, "Quantity")
        quantity.text = str(line.quantity)
        if line.unit:
            quantity.set("unit", line.unit)
        SubElement(line_el, "UnitPriceHT").text = f"{line.unit_price_ht:.2f}"
        SubElement(line_el, "DiscountRate").text = f"{line.discount_rate:.2f}"
        SubElement(line_el, "TVARate").text = f"{line.tva_rate:.2f}"
        SubElement(line_el, "LineGrossHT").text = f"{line.line_gross_ht:.2f}"
        SubElement(line_el, "LineDiscount").text = f"{line.line_discount:.2f}"
        SubElement(line_el, "LineTotalHT").text = f"{line.line_net_ht:.2f}"
        SubElement(line_el, "LineTotalTVA").text = f"{line.line_tva:.2f}"
        SubElement(line_el, "LineTotalTTC").text = f"{line.line_ttc:.2f}"

    totals_el = SubElement(root, "Totals")
    SubElement(totals_el, "TotalHT").text = f"{computed.totals.total_ht:.2f}"
    total_discount_text = f"{computed.totals.total_discount:.2f}"
    SubElement(totals_el, "TotalDiscount").text = total_discount_text
    SubElement(totals_el, "TotalTVA").text = f"{computed.totals.total_tva:.2f}"
    SubElement(totals_el, "TotalTTC").text = f"{computed.totals.total_ttc:.2f}"

    meta_el = SubElement(root, "Meta")
    if payload.meta and payload.meta.created_at:
        created_at = payload.meta.created_at
    else:
        created_at = datetime.now(timezone.utc)
    if payload.meta and payload.meta.generation_tool:
        generation_tool = payload.meta.generation_tool
    else:
        generation_tool = "rennesdev-invoice-v2"
    SubElement(meta_el, "CreatedAt").text = created_at.isoformat()
    SubElement(meta_el, "GenerationTool").text = generation_tool

    return tostring(root, encoding="utf-8", xml_declaration=True)


def draw_text_line(
    pdf: canvas.Canvas,
    text: str,
    x_mm: float,
    y_mm: float,
) -> None:
    pdf.drawString(x_mm * mm, y_mm * mm, text)


def build_pdf_stub(
    payload: InvoicePayload, computed: ComputationResult
) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle(f"Invoice {payload.invoice.number}")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(20 * mm, height - 20 * mm, "Invoice Stub V2")

    pdf.setFont("Helvetica", 10)
    y = 265
    lines = [
        f"Invoice number: {payload.invoice.number}",
        f"Issue date: {payload.invoice.issue_date.isoformat()}",
        f"Currency: {payload.invoice.currency}",
        f"Operation nature: {payload.invoice.operation_nature.value}",
        f"Seller: {payload.seller.name} (SIREN {payload.seller.siren})",
        f"Buyer: {payload.buyer.name} (SIREN {payload.buyer.siren})",
        "",
        "Invoice lines:",
    ]

    for item in lines:
        draw_text_line(pdf, item, 20, y)
        y -= 6

    for line in computed.lines:
        line_text = (
            f"[{line.line_number}] {line.description} | qty {line.quantity} | "
            f"unit HT {line.unit_price_ht:.2f} | TVA {line.tva_rate:.2f}% | "
            f"TTC {line.line_ttc:.2f}"
        )
        draw_text_line(pdf, line_text, 20, y)
        y -= 6
        if y < 30:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = 270

    y -= 4
    currency = payload.invoice.currency
    summary = [
        f"Total discount: {computed.totals.total_discount:.2f} {currency}",
        f"Total HT: {computed.totals.total_ht:.2f} {currency}",
        f"Total TVA: {computed.totals.total_tva:.2f} {currency}",
        f"Total TTC: {computed.totals.total_ttc:.2f} {currency}",
    ]
    for item in summary:
        draw_text_line(pdf, item, 20, y)
        y -= 6

    if payload.invoice.tva_on_debits_option:
        y -= 3
        mention = "VAT mention: Option for payment of VAT on debits"
        draw_text_line(pdf, mention, 20, y)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()


app = FastAPI(title="RennesDev Invoice API V2")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/invoice/xml")
def generate_invoice_xml(payload: InvoicePayload) -> Response:
    computed = compute_invoice(payload)
    xml_bytes = build_xml(payload, computed)
    filename = f"invoice_{payload.invoice.number}.xml"
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/invoice/pdf")
def generate_invoice_pdf(payload: InvoicePayload) -> StreamingResponse:
    computed = compute_invoice(payload)
    pdf_bytes = build_pdf_stub(payload, computed)
    filename = f"invoice_{payload.invoice.number}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )